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
from urllib.parse import parse_qs, urlencode, urlsplit

from keeper_common import KeeperError, atomic_json, emit_error, executable, gui_lock_path, load_config, process_lock

ZW = re.compile(r"[\u200b\u200c\u200d\ufeff\ufffc]")
CAPABILITY_LABELS = {
    "发送消息", "发送邮件", "搜索与获取邮件内容", "新建与编辑文档",
    "搜索与获取文档内容", "新建与跟进待办", "新建与管理日程", "预约与更新会议",
    "搜索与获取会议信息", "上传与更新微盘文件", "搜索与获取微盘文件内容",
    "搜索企业成员", "获取对话用户信息",
}


def clean(value):
    return ZW.sub("", str(value or "")).strip()


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


@contextmanager
def monitor_guard(cfg):
    enabled = cfg.get("bridge_monitor", cfg.get("bridge_send_link", False))
    if not enabled:
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

    def open(self, existing_only=False, send_link=False, activate=False):
        native, self.app = self.ax.application()
        current = self.select_window()
        if current is not None:
            if activate:
                self.ax.activate(native)
            return current
        if existing_only:
            raise KeeperError("page_not_open", "Open the target bot's permissions page first")
        if send_link:
            link = "https://work.weixin.qq.com/ai/aiHelper/authorizationList?" + urlencode({
                "from": "chat", "forceInnerBrowser": "1", "aibotid": self.cfg["aibotid"],
                "str_aibotid": self.cfg["str_aibotid"], "type": "1"})
            response = bridge_request(self.cfg, "POST", "/wecom/send", {
                "to": self.cfg["bot_chat_name"], "message": "授权续期入口 " + link,
                "idempotency_key": "wecom-renew-" + str(time.time_ns())})
            if response.get("success") is not True:
                raise KeeperError("link_delivery_failed", "Bridge did not confirm link delivery")
        self.ax.activate(native)
        self.sleep(1)
        links = []
        for win in self.ax.ax_get(self.app, "AXWindows") or []:
            for node in self.walk(win):
                if self.ax.ax_get(node, "AXRole") == "AXLink" and self.matches(node):
                    bounds = self.ax.frame(node)
                    if bounds:
                        links.append((bounds[1], node, win))
        if not links:
            raise KeeperError("link_not_visible", "Open the target chat and make its authorization link visible")
        _, link, chat = max(links, key=lambda item: item[0])
        self.ax.click(link, chat)
        return self.wait(self.select_window, lambda value: value is not None, "page_not_open")

    def wait(self, read, accept, error, timeout=20):
        deadline = self.clock() + timeout
        while True:
            value = read()
            if accept(value):
                return value
            if self.clock() >= deadline:
                raise KeeperError(error, "Timed out waiting for verified UI state")
            self.sleep(0.5)

    def read_rows(self, window):
        page = self.bound(window)
        elements = []
        for node in self.walk(page):
            role, text, bounds = self.ax.ax_get(node, "AXRole"), self.text(node), self.ax.frame(node)
            if role in {"AXStaticText", "AXButton"} and text and bounds:
                elements.append((text, node, bounds, role))
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
        self.bound(window)  # Recheck identity immediately before every action.
        if element is None:
            raise KeeperError("control_missing", "Expected action control is missing")
        self.ax.click(element, self.bound(window))

    def named(self, window, text, role=None):
        return [n for n in self.walk(window) if self.text(n) == text and (role is None or self.ax.ax_get(n, "AXRole") == role)]

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
                    candidates = [n for n in self.walk(window) if self.ax.ax_get(n, "AXRole") == "AXButton"
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

    def pre_renew(self, window, name, row):
        old = row["expiry"]
        self.click(window, row["authorized"])
        menu = self.wait(lambda: self.named(window, "取消授权"), lambda items: len(items) == 1, "revoke_menu_missing")
        self.click(window, menu[0])
        confirm = self.wait(lambda: self.named(window, "取消授权", "AXButton"), lambda items: len(items) == 1, "revoke_confirmation_missing")
        # Persist BEFORE revocation. Next --renew resumes restoration before other work.
        atomic_json(self.journal, {"identity": self.identity, "row": name, "expiry_before": old.isoformat()})
        try:
            self.click(window, confirm[0])
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
    for option in ("check", "renew", "pre-renew", "doctor"):
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
                    result, code = Renewal(cfg, ax).run(mode, args.existing_window, args.within_hours)
                except Exception as exc:
                    result, code = emit_error(exc)
                    try:
                        # Write failures while still holding the GUI lock, so a failed
                        # process cannot overwrite a newer successful observation.
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
