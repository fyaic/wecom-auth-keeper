#!/usr/bin/env python3
"""WeCom permission inspection and recovery. --help/--doctor never operate the GUI."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timedelta
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import time
import urllib.request
from urllib.parse import parse_qs, urlsplit

from keeper_bootstrap import authorization_url
from keeper_common import KeeperError, atomic_json, emit_error, executable, gui_lock_path, load_config, process_lock

ZW = re.compile(r"[\u200b\u200c\u200d\ufeff\ufffc]")
from keeper_capabilities import CAPABILITY_LABELS


def clean(value):
    return ZW.sub("", str(value or "")).strip()


def permission_page_error(texts):
    """Classify fixed official-page failures, never nicknames or chat text.

    The caller must first bind the WebArea to both Bot identifiers. A title or
    an empty/loading body is not a successful permission response.
    """
    text = ''.join(clean(value) for value in texts)
    if '当前账号非机器人所属企业' in text:
        return 'authorization_organization_mismatch'
    if '暂无法授权' in text and '仅限机器人创建者可进行授权' in text:
        return 'authorization_creator_required'
    if '暂无法授权，机器人已删除' in text:
        return 'authorization_bot_deleted'
    return None


PAGE_ERROR_MESSAGES = {
    'authorization_creator_required': 'The official page requires the Bot creator in the current desktop context; verify the existing profile, desktop identity and organization without rebinding the CLI',
    'authorization_organization_mismatch': 'The official page reports that the current account is outside the Bot organization; verify the native organization and existing desktop identity',
    'authorization_bot_deleted': 'The official page reports that this Bot was deleted; preserve the existing CLI configuration and resolve the business target',
}


def parse_expiry(text, now=None):
    now = now or datetime.now()
    match = re.search(r"(\d{1,2})/(\d{1,2})\s+(\d{1,2}):(\d{2})", text)
    if not match:
        return None
    values = [int(v) for v in match.groups()]
    candidates = []
    for year in (now.year - 1, now.year, now.year + 1):
        try:
            candidates.append(datetime(year, *values))
        except ValueError:
            pass
    return min(candidates, key=lambda dt: abs(dt - now)) if candidates else None


def target_url(value, cfg):
    try:
        url = urlsplit(str(value))
        query = parse_qs(url.query)
        return (url.scheme == "https" and url.hostname == "work.weixin.qq.com"
                and url.port in (None, 443) and not url.username and not url.password
                and url.path == "/ai/aiHelper/authorizationList"
                and query.get("aibotid") == [cfg["aibotid"]]
                and query.get("str_aibotid") == [cfg["str_aibotid"]])
    except (TypeError, ValueError):
        return False


def bridge_request(cfg, method, path, body=None):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    req = urllib.request.Request(cfg["bridge_url"].rstrip("/") + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"})
    with opener.open(req, timeout=30) as response:
        result = json.load(response)
    if not isinstance(result, dict):
        raise KeeperError("bridge_error", "Invalid bridge response")
    return result


def check_bridge_coordination(cfg):
    if cfg.get("bridge_coordination") == "shared-lock-v1":
        try:
            response = bridge_request(cfg, "GET", "/wecom/desktop/coordination")
            info = gui_lock_path().stat()
            import os
            if (response.get("protocol") != "wecom-desktop-flock-v1"
                    or response.get("scope") != "bridge-ui"
                    or response.get("handoff_refresh") is not True
                    or response.get("lock_path") != str(gui_lock_path())
                    or response.get("device") != info.st_dev
                    or response.get("inode") != info.st_ino
                    or response.get("uid") != os.getuid()):
                raise ValueError("coordination_contract_mismatch")
        except Exception as exc:
            raise KeeperError("desktop_coordination_unknown", "Bridge does not share the verified desktop lock") from exc
        return
    # Observe disables message handling, not the independent organization
    # rotator. A running rotator can dismiss our menus or change enterprises.
    # Reject this known conflict before any GUI work or monitor mutation.
    try:
        rotator = bridge_request(cfg, "GET", "/wecom/orgs/rotator/status")
    except Exception as exc:
        raise KeeperError("desktop_coordination_unknown", "Cannot verify Bridge organization rotator state") from exc
    if not isinstance(rotator.get("enabled"), bool) or not isinstance(rotator.get("running"), bool):
        raise KeeperError("desktop_coordination_unknown", "Bridge did not provide an explicit organization rotator state")
    if rotator["enabled"] or rotator["running"]:
        raise KeeperError("desktop_coordination_required", "Bridge organization rotation requires shared desktop coordination; observe mode is insufficient")


@contextmanager
def monitor_guard(cfg):
    enabled = cfg.get("bridge_monitor", cfg.get("bridge_send_link", False))
    if not enabled:
        yield
        return
    check_bridge_coordination(cfg)
    if cfg.get("bridge_coordination") == "shared-lock-v1":
        # The public caller holds EX through cleanup. Bridge's SH activities
        # cannot start; don't alter modes or call its blocked mutation routes.
        yield
        return
    original = bridge_request(cfg, "GET", "/wecom/monitor/mode").get("mode")
    if original not in {"active", "observe"}:
        raise KeeperError("monitor_unknown", "Cannot establish the original bridge monitor mode")
    try:
        changed = bridge_request(cfg, "POST", "/wecom/monitor/mode", {"mode": "observe"})
        if changed.get("mode") != "observe":
            raise KeeperError("monitor_pause_failed", "Bridge monitor did not enter observe mode")
        yield
    finally:
        restored = bridge_request(cfg, "POST", "/wecom/monitor/mode", {"mode": original})
        if restored.get("mode") != original:
            raise KeeperError("monitor_restore_failed", "Could not restore the original monitor mode")


class Renewal:
    def __init__(self, cfg, ax, *, clock=time.monotonic, sleep=time.sleep):
        self.cfg, self.ax, self.clock, self.sleep = cfg, ax, clock, sleep
        self.rows = cfg["target_rows"]
        self.app = None
        self.journal = Path(cfg["state_file"] + ".pending.json")
        self.identity = hashlib.sha256((cfg["aibotid"] + ":" + cfg["str_aibotid"]).encode()).hexdigest()

    def text(self, node):
        return clean(self.ax.ax_get(node, "AXTitle")) or clean(self.ax.ax_get(node, "AXValue"))

    def walk(self, root):
        stack, total = [(root, 0)], 0
        while stack:
            node, depth = stack.pop()
            total += 1
            if total > 5000 or depth > 40:
                raise KeeperError("tree_incomplete", "Accessibility tree exceeds inspection limits")
            yield node
            stack.extend((n, depth + 1) for n in reversed(self.ax.ax_get(node, "AXChildren") or []))

    def matches(self, node):
        return any(target_url(self.ax.ax_get(node, key), self.cfg) for key in ("AXURL", "AXValue", "AXTitle"))

    def bound(self, window):
        if self.app is not None and window not in (self.ax.ax_get(self.app, "AXWindows") or []):
            raise KeeperError("identity_unverified", "Target permission window is no longer live")
        matches = [n for n in self.walk(window) if self.ax.ax_get(n, "AXRole") == "AXWebArea" and self.matches(n)]
        if len(matches) != 1:
            raise KeeperError("identity_unverified", "Expected one authorization page matching both configured bot identifiers")
        return matches[0]

    def select_window(self):
        valid = []
        for window in self.ax.ax_get(self.app, "AXWindows") or []:
            try:
                self.bound(window)
            except KeeperError:
                continue
            valid.append(window)
        if len(valid) > 1:
            raise KeeperError("ambiguous_window", "Close duplicate authorization windows first")
        return valid[0] if valid else None

    def focus_window(self, native, window, error="link_not_visible"):
        self.ax.activate(native)
        if self.ax.ax_perform(window, "AXRaise") != 0:
            raise KeeperError(error, "Could not raise the target native window")
        self.wait(lambda: self.ax.ax_get(self.app, "AXFocusedWindow"), lambda focused: focused == window,
                  error, timeout=3)

    def contains(self, outer, inner):
        if not outer or not inner:
            return False
        x, y, w, h = inner
        ox, oy, ow, oh = outer
        return w > 0 and h > 0 and ow > 0 and oh > 0 and ox <= x and oy <= y and x + w <= ox + ow and y + h <= oy + oh

    def visible_links(self, windows):
        links = []
        for window in windows:
            stack, total = [(window, 0, [self.ax.frame(window)])], 0
            while stack:
                node, depth, clips = stack.pop()
                total += 1
                if total > 5000 or depth > 40:
                    raise KeeperError("tree_incomplete", "Accessibility tree exceeds inspection limits")
                role = self.ax.ax_get(node, "AXRole")
                if role == "AXScrollArea":
                    clips = [*clips, self.ax.frame(node)]
                if role == "AXLink" and self.matches(node):
                    bounds = self.ax.frame(node)
                    if bounds and all(self.contains(clip, bounds) for clip in clips):
                        links.append((bounds[1], node, window))
                stack.extend((n, depth + 1, clips) for n in self.ax.ax_get(node, "AXChildren") or [])
        return links

    def open(self, existing_only=False, send_link=False, activate=False):
        native, self.app = self.ax.application()
        current = self.select_window()
        if current is not None:
            if activate:
                self.focus_window(native, current, "page_not_open")
            return current
        if existing_only:
            raise KeeperError("page_not_open", "Open the target bot's permissions page first")
        if send_link:
            link = authorization_url(self.cfg)
            response = bridge_request(self.cfg, "POST", "/wecom/send", {
                "to": self.cfg["bot_chat_name"], "message": "授权续期入口 " + link,
                "idempotency_key": "wecom-renew-" + str(time.time_ns())})
            if response.get("success") is not True:
                raise KeeperError("link_delivery_failed", "Bridge did not confirm link delivery")
        self.ax.activate(native)
        self.sleep(1)
        links = self.visible_links(self.ax.ax_get(self.app, "AXWindows") or [])
        if not links and self.cfg.get("chat_history_navigation", False):
            from keeper_navigation import open_chat_history
            if self.cfg.get("organization_navigation"):
                from keeper_organization import ensure_organization
                ensure_organization(self, native)
            open_chat_history(self, native)
            links = self.visible_links(self.ax.ax_get(self.app, "AXWindows") or [])
        if not links:
            raise KeeperError("link_not_visible", "Open the target chat and make its authorization link visible")
        _, _, chat = max(links, key=lambda item: item[0])
        self.focus_window(native, chat)
        # Never click a stale node or a background-window coordinate. Re-read
        # the selected window and all scroll clipping after it has been raised.
        if chat not in (self.ax.ax_get(self.app, "AXWindows") or []):
            raise KeeperError("link_not_visible", "Target link window disappeared")
        links = self.visible_links([chat])
        if not links:
            raise KeeperError("link_not_visible", "Verified link is no longer visible")
        _, link, chat = max(links, key=lambda item: item[0])
        self.ax.click(link, chat)
        opened = self.wait(self.select_window, lambda value: value is not None, "page_not_open")
        if activate:
            self.focus_window(native, opened, "page_not_open")
        return opened

    def wait(self, read, accept, error, timeout=20):
        deadline = self.clock() + timeout
        while True:
            value = read()
            if accept(value):
                return value
            if self.clock() >= deadline:
                raise KeeperError(error, "Timed out waiting for verified UI state")
            self.sleep(0.5)

    def close_window(self):
        """Close the bound permission window/sheet, preserving the main window."""
        native, self.app = self.ax.application()
        window = self.select_window()
        if window is None:
            return {"ok": True, "mode": "close-window", "closed": False}, 0
        page = self.bound(window)
        from keeper_navigation import global_search, sidebar_rows
        embedded = (global_search(self, window) is not None or bool(sidebar_rows(self, window))
                    or any(self.ax.ax_get(n, 'AXRole') == 'AXSheet' for n in self.walk(window)))
        if embedded:
            from keeper_cleanup import embedded_close_button
            button = embedded_close_button(self, native, window, page)
            if button is None:
                raise KeeperError('embedded_page_close_unavailable',
                                  'No verified sheet close control; main window close refused')
        else:
            pages = [n for n in self.walk(window) if self.ax.ax_get(n, "AXRole") == "AXWebArea"]
            button = self.ax.ax_get(window, "AXCloseButton")
            if (len(pages) != 1 or button is None
                    or self.ax.ax_get(button, "AXRole") != "AXButton"
                    or self.ax.ax_get(button, "AXSubrole") != "AXCloseButton"):
                raise KeeperError("window_close_unavailable", "No unambiguous native close control for the target page")
        self.bound(window)
        if self.ax.ax_perform(button, "AXPress") != 0:
            raise KeeperError("window_close_failed", "Target window rejected its native close action")
        if embedded:
            stable = 0
            def dismissed():
                nonlocal stable
                remaining = self.ax.ax_get(self.app, 'AXWindows') or []
                if window not in remaining:
                    raise KeeperError('window_close_failed', 'Main window disappeared during sheet cleanup')
                nodes = list(self.walk(window))
                gone = (bool(self.ax.ax_get(window, 'AXChildren'))
                        and not any(self.ax.ax_get(n, 'AXRole') == 'AXSheet' for n in nodes)
                        and self.select_window() is None)
                stable = stable + 1 if gone else 0
                return stable >= 2
            self.wait(dismissed, bool, "window_close_failed", timeout=3)
        else:
            self.wait(lambda: self.ax.ax_get(self.app, "AXWindows") or [],
                      lambda windows: window not in windows, "window_close_failed", timeout=3)
        return {"ok": True, "mode": "close-window", "closed": True,
                "closed_kind": "embedded-sheet" if embedded else "standalone-window"}, 0

    def read_rows(self, window):
        page = self.bound(window)
        elements = []
        for node in self.walk(page):
            role, text, bounds = self.ax.ax_get(node, "AXRole"), self.text(node), self.ax.frame(node)
            if role in {"AXStaticText", "AXButton"} and text and bounds:
                elements.append((text, node, bounds, role))
        error = permission_page_error(e[0] for e in elements)
        if error:
            raise KeeperError(error, PAGE_ERROR_MESSAGES[error])
        # Capability descriptions can repeat the heading (e.g. contacts).
        # Headings share the leftmost column; description chips are indented.
        columns = [e[2][0] for e in elements if e[0] in CAPABILITY_LABELS.union(self.rows)]
        heading_x = min(columns) if columns else None
        headings = [e for e in elements if heading_x is not None and abs(e[2][0] - heading_x) <= 2]
        result = {}
        for name in self.rows:
            anchors = [e for e in headings if e[0] == name]
            row = {"status": "missing", "expiry": None, "btn": None, "authorized": None}
            if len(anchors) == 1:
                x, y, _, _ = anchors[0][2]
                # A narrow row band, with positive evidence required. Ambiguity fails closed.
                next_rows = [e[2][1] for e in headings
                             if e[0] in CAPABILITY_LABELS.union(self.rows)
                             and abs(e[2][0] - x) < 40 and e[2][1] > y]
                limit = min([y + 70, *next_rows])
                nearby = [e for e in elements if e[2][0] - x > 80 and y - 8 <= e[2][1] < limit]
                dates = [parse_expiry(e[0]) for e in nearby if e[0].startswith("有效期至")]
                buttons = [e[1] for e in nearby if e[0] == "授权" and e[3] == "AXButton"]
                granted = [e[1] for e in nearby if e[0] == "已授权"]
                row["status"] = "unknown"
                if len(buttons) == 1 and not granted and not dates:
                    row.update(status="expired", btn=buttons[0])
                elif not buttons and len(granted) == 1 and len(dates) == 1 and dates[0] is not None:
                    row.update(status="authorized" if dates[0] > datetime.now() else "expired",
                               expiry=dates[0], authorized=granted[0])
            elif len(anchors) > 1:
                row["status"] = "unknown"
            result[name] = row
        return result

    def click(self, window, element):
        page = self.bound(window)  # Recheck identity immediately before every action.
        if element is None:
            raise KeeperError("control_missing", "Expected action control is missing")
        if not any(node == element for node in self.walk(page)):
            raise KeeperError("control_target_changed", "Action control is no longer inside the verified permission page")
        # A matching page elsewhere in the window does not bind a dialog/control
        # to that page. Never fall back to a screen coordinate for authorization.
        self.ax.click(element, page, allow_coordinate_fallback=False)

    def named(self, window, text, role=None):
        return [n for n in self.walk(self.bound(window)) if self.text(n) == text and (role is None or self.ax.ax_get(n, "AXRole") == role)]

    def authorize(self, window, name, old_expiry=None):
        for _ in range(3):
            row = self.read_rows(window)[name]
            if row["status"] == "authorized" and (old_expiry is None or row["expiry"] > old_expiry):
                return row
            if row["status"] != "expired" or row["btn"] is None:
                raise KeeperError("row_not_actionable", "Permission is not in a verifiable grantable state")
            self.click(window, row["btn"])
            deadline = self.clock() + 15
            confirmed = False
            while self.clock() < deadline:
                self.sleep(0.5)
                row = self.read_rows(window)[name]
                if row["status"] == "authorized" and (old_expiry is None or row["expiry"] > old_expiry):
                    return row
                if not confirmed:
                    candidates = [n for n in self.walk(self.bound(window)) if self.ax.ax_get(n, "AXRole") == "AXButton"
                                  and self.text(n) in {"确认", "确定", "重新授权", "同意"}]
                    if len(candidates) > 1:
                        raise KeeperError("ambiguous_confirmation", "Multiple confirmation controls in target window")
                    if candidates:
                        self.click(window, candidates[0])
                        confirmed = True
        raise KeeperError("renew_failed", "Permission did not become authorized with an updated expiry")

    def recover_pending(self, window):
        if not self.journal.exists():
            return
        pending = json.loads(self.journal.read_text())
        name = pending.get("row")
        if pending.get("identity") != self.identity or name not in self.rows:
            raise KeeperError("pending_mismatch", "Recovery journal belongs to a different target")
        old = datetime.fromisoformat(pending["expiry_before"])
        self.authorize(window, name, old)
        self.journal.unlink()

    def prepare_revoke(self, window, name, old):
        # A leftover final confirmation is not the navigation menu. In
        # particular, AXPress on its obscured "已授权" anchor can be a no-op;
        # never let the next name-only lookup click that existing final button.
        if self.named(window, '取消授权', 'AXButton'):
            raise KeeperError('revoke_menu_unverified', 'Existing final revoke confirmation blocks preparation')
        row = self.read_rows(window)[name]
        if row['status'] != 'authorized' or row['expiry'] != old:
            raise KeeperError('row_changed', 'Permission changed before opening revoke menu')
        self.click(window, row['authorized'])

        def navigation_menu():
            items = self.named(window, '取消授权')
            # Only the calibrated text menu may open the final dialog. The
            # AXButton with the same label is reserved for pre_renew, after
            # durable phase/pending records exist. Unknown roles fail closed.
            if any(self.ax.ax_get(item, 'AXRole') != 'AXStaticText' for item in items):
                raise KeeperError('revoke_menu_unverified', 'Revoke navigation contains a final button or unknown control')
            return items

        menu = self.wait(navigation_menu, lambda items: len(items) == 1, 'revoke_menu_missing')
        if 'AXPress' not in self.ax.action_names(menu[0]):
            native, _ = self.ax.application()
            self.focus_window(native, window, 'revoke_menu_unverified')
            page = self.bound(window)
            # Re-read after focusing; no cached element or confirmation button.
            menu = navigation_menu()
            current = self.read_rows(window)[name]
            if (len(menu) != 1 or self.named(window, '取消授权', 'AXButton')
                    or current['status'] != 'authorized' or current['expiry'] != old):
                raise KeeperError('revoke_menu_unverified', 'Revoke menu or row changed')
            self.ax.open_revoke_confirmation(native, self.app, window, page, menu[0])
        else:
            self.click(window, menu[0])
        return self.wait(lambda: self.named(window, '取消授权', 'AXButton'), lambda items: len(items) == 1, 'revoke_confirmation_missing')[0]

    def pre_renew(self, window, name, row, *, before_revoke=None):
        old = row['expiry']
        try:
            confirmation = self.prepare_revoke(window, name, old)
        except Exception as exc:
            # The final revoke has not even been prepared in the journal.
            # Maintenance may clear ONLY this proven non-mutating intent after
            # independently re-reading the unchanged, still-authorized scope.
            exc.revocation_not_attempted = True
            raise
        if before_revoke is not None:
            # The scheduler records the irreversible-action phase before our
            # pending journal and final click. A callback/storage failure must
            # never permit the cancellation to proceed.
            before_revoke()
        # Persist BEFORE revocation. Next --renew resumes restoration before other work.
        atomic_json(self.journal, {"identity": self.identity, "row": name, "expiry_before": old.isoformat()})
        try:
            self.click(window, confirmation)
            self.wait(lambda: self.read_rows(window)[name], lambda r: r["status"] == "expired" and r["btn"] is not None, "revoke_not_confirmed")
            self.authorize(window, name, old)
        except Exception:
            # Recovery gets priority over another permission. Never issue another revoke.
            try:
                self.authorize(window, name, old)
            except Exception as recovery:
                raise KeeperError("needs_user_action", "Pre-renewal interrupted; pending recovery saved. Run --renew or restore this permission in WeCom") from recovery
            self.journal.unlink()
            return
        self.journal.unlink()

    def run(self, mode, existing_only=False, within_hours=24):
        # Inspection does not send messages or alter bridge state.
        if mode == "check" and not existing_only and self.cfg.get("bridge_monitor", self.cfg.get("bridge_send_link", False)):
            check_bridge_coordination(self.cfg)
        cfg = self.cfg if mode != "check" else {**self.cfg, "bridge_monitor": False}
        with monitor_guard(cfg):
            window = self.open(existing_only, mode != "check" and self.cfg.get("bridge_send_link", False), activate=mode != "check")
            before = self.wait(lambda: self.read_rows(window),
                               lambda rows: all(r["status"] in {"authorized", "expired"} for r in rows.values()), "rows_incomplete")
            if mode != "check":
                self.recover_pending(window)
                for name in self.rows:
                    row = self.read_rows(window)[name]
                    if row["status"] == "expired":
                        self.authorize(window, name, row["expiry"])
                    elif mode == "pre-renew" and row["status"] == "authorized" and row["expiry"] <= datetime.now() + timedelta(hours=within_hours):
                        self.pre_renew(window, name, row)
                    elif row["status"] != "authorized":
                        raise KeeperError("rows_incomplete", "Permission changed to an unknown state")
            after = self.read_rows(window)
            healthy = all(r["status"] == "authorized" for r in after.values()) and not self.journal.exists()
            result = {"ok": healthy, "mode": mode, "rows": {n: {
                "status": r["status"], "expiry": r["expiry"].isoformat(timespec="minutes") if r["expiry"] else None,
                "expiry_before": before[n]["expiry"].isoformat(timespec="minutes") if before[n]["expiry"] else None,
            } for n, r in after.items()}, "pending_recovery": self.journal.exists()}
            if mode == "check" and existing_only:
                result.update(navigation_performed=False, authorization_changed=False,
                              desktop_coordination="not_required_read_only")
            if not healthy:
                result["error"] = "permissions_not_healthy"
            atomic_json(self.cfg["state_file"], {**result, "read_at": datetime.now().isoformat()})
            return result, 0 if healthy else 2


def doctor(cfg):
    checks = {"macos": sys.platform == "darwin"}
    for module in ("AppKit", "Quartz", "ApplicationServices"):
        checks[module] = importlib.util.find_spec(module) is not None
    try:
        executable(cfg.get("wecom_cli"), "wecom-cli")
        checks["wecom_cli"] = True
    except KeeperError:
        checks["wecom_cli"] = False
    return {"ok": all(checks.values()), "mode": "doctor", "checks": checks,
            "gui_access": "not_checked", "note": "No GUI, network, credentials or permission changes performed"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(Path(__file__).with_name("config.json")))
    modes = parser.add_mutually_exclusive_group()
    for option in ("check", "renew", "pre-renew", "doctor", "close-window"):
        modes.add_argument("--" + option, action="store_true")
    parser.add_argument("--existing-window", action="store_true", help="Only inspect/use an already-open, identity-verified page")
    parser.add_argument("--within-hours", type=float, default=24, help="Pre-renew permissions due within this horizon (0..168)")
    args = parser.parse_args(argv)
    cfg = None
    try:
        if not 0 <= args.within_hours <= 168:
            raise KeeperError("invalid_arguments", "within-hours must be between 0 and 168", 3)
        cfg = load_config(args.config)
        if args.doctor:
            result = doctor(cfg)
            code = 0 if result["ok"] else 3
        else:
            if sys.platform != "darwin":
                raise KeeperError("unsupported_platform", "Desktop renewal requires macOS", 3)
            try:
                import keeper_ax as ax
            except ImportError as exc:
                raise KeeperError("missing_dependency", "Install requirements-macos.txt in this Python environment", 3) from exc
            mode = "pre-renew" if args.pre_renew else "renew" if args.renew else "check"
            if mode == "pre-renew" and not args.existing_window:
                raise KeeperError("invalid_arguments", "Experimental pre-renew requires --existing-window", 3)
            with process_lock(gui_lock_path(), cfg["lock_wait"]):
                try:
                    engine = Renewal(cfg, ax)
                    # Cleanup uses only a live, dual-ID-bound page's AXPress
                    # close control. It never focuses, navigates, changes Bridge
                    # mode or falls back to mouse/keyboard input.
                    result, code = (engine.close_window() if args.close_window else
                                    engine.run(mode, args.existing_window, args.within_hours))
                except Exception as exc:
                    result, code = emit_error(exc)
                    try:
                        # Write failures while still holding the GUI lock, so a failed
                        # process cannot overwrite a newer successful observation.
                        if not args.close_window:
                            atomic_json(cfg["state_file"], {**result, "read_at": datetime.now().isoformat(),
                                                           "pending_recovery": Path(cfg["state_file"] + ".pending.json").exists()})
                    except OSError:
                        pass
    except Exception as exc:
        result, code = emit_error(exc)
    print(json.dumps(result, ensure_ascii=False))
    return code


if __name__ == "__main__":
    sys.exit(main())
