"""Reusable multi-permission, pre-expiry cycle. No model, Gateway or business probe dependency."""
from datetime import datetime, timedelta
import json
import math
from pathlib import Path

from keeper_common import KeeperError, atomic_json, emit_error
from renew import Renewal

DEFAULT_POLICY = {"within_hours": 24, "interval_seconds": 3600,
                  "min_renew_interval_seconds": 3600, "retry_seconds": 300,
                  "close_window": True, "stale_after_hours": 24}


def policy(cfg):
    raw = cfg.get("maintenance", {})
    if not isinstance(raw, dict) or set(raw) - DEFAULT_POLICY.keys():
        raise KeeperError("invalid_maintenance_policy", "Unknown maintenance settings", 3)
    value = {**DEFAULT_POLICY, **raw}
    limits = {"within_hours": (1, 168), "interval_seconds": (60, 86400),
              "min_renew_interval_seconds": (60, 86400), "retry_seconds": (60, 3600),
              "stale_after_hours": (1, 168)}
    for name, (low, high) in limits.items():
        number = value[name]
        if (isinstance(number, bool) or not isinstance(number, (int, float))
                or not math.isfinite(number) or not low <= number <= high
                or ((name.endswith("seconds") or name == "stale_after_hours")
                    and not isinstance(number, int))):
            raise KeeperError("invalid_maintenance_policy", f"Invalid maintenance field: {name}", 3)
    if not isinstance(value["close_window"], bool) or value["interval_seconds"] >= value["within_hours"] * 3600:
        raise KeeperError("invalid_maintenance_policy", "Check interval must be shorter than the pre-renew window", 3)
    return value


def timestamp(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


def iso(value):
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError()
    result = datetime.fromisoformat(value)
    if result.tzinfo is not None:
        raise ValueError()
    return result


def read_state(path, identity):
    if not path.exists():
        return {"version": 1, "identity": identity, "permissions": {}, "failures": 0, "next_retry_at": 0}
    try:
        value = json.loads(path.read_text())
        if (not isinstance(value, dict) or value.get("version") != 1
                or value.get("identity") != identity or not isinstance(value.get("permissions"), dict)
                or type(value.get("failures")) is not int or value["failures"] < 0
                or not timestamp(value.get("next_retry_at"))):
            raise ValueError()
        for name, record in value["permissions"].items():
            if not isinstance(name, str) or not isinstance(record, dict):
                raise ValueError()
            if not timestamp(record.get("next_allowed_at", 0)):
                raise ValueError()
            if "expiry" in record:
                iso(record["expiry"])
            if "checked_at" in record:
                iso(record["checked_at"])
            if "intent" in record:
                intent = record["intent"]
                if not isinstance(intent, dict) or "expiry_before" not in intent or not timestamp(intent.get("started_at")):
                    raise ValueError()
                iso(intent["expiry_before"])
        return value
    except (OSError, ValueError, TypeError):
        raise KeeperError("invalid_maintenance_state", "Cannot verify maintenance state or its Bot binding") from None


def expiry_text(row):
    return row["expiry"].isoformat(timespec="minutes") if row["expiry"] else None


def navigation_due(state, settings, rows, now, *, pending=False):
    """是否需要触碰 GUI 导航。False = 全部目标行都有较新的「远期到期」
    记录且无未决撤销——可零 GUI 跳过（2026-11-17 AZW 每小时残窗事故：
    未到期也无条件全导航，连续 83 次失败且从不清理，成为残窗源头）。

    需要导航的条件（任一）：有行存在未决 intent（门审轮1 P1——restored
    分支在 authorize 前持久化且无 journal 保护，恢复永远优先）；有行无
    expiry 记录（首跑学习）；有行临期（expiry ≤ now + within_hours）；
    记录陈旧（checked_at 距今超过 stale_after_hours——外部续期/撤销只能
    靠重观测发现，诚实的重验税）；存在未决撤销 journal。"""
    if pending:
        return True
    for name in rows:
        record = state["permissions"].get(name) or {}
        if record.get("intent"):
            # 门审轮1 P1：restored 分支在 authorize 完成前就持久化 intent 且
            # 无 journal 保护——未决 intent 是本仓自己的恢复未完成证据，
            # 「恢复永远优先」不得被 not_due 门延迟（跳过最坏推迟 24h）。
            return True
        expiry = record.get("expiry")
        if not expiry:
            return True
        try:
            when = iso(expiry)
        except ValueError:
            return True
        if when is None or when <= now() + timedelta(hours=settings["within_hours"]):
            return True
        checked = record.get("checked_at")
        seen = None
        if checked:
            try:
                seen = iso(checked)
            except ValueError:
                seen = None
        if seen is None or now() - seen > timedelta(hours=settings["stale_after_hours"]):
            return True
    return False


def observe(engine, window):
    return engine.wait(lambda: engine.read_rows(window),
                       lambda rows: all(row["status"] in {"authorized", "expired"} for row in rows.values()),
                       "rows_incomplete")


def run_cycle(cfg, ax, *, now=datetime.now, engine=None):
    """Caller holds the shared desktop lock across this entire cycle, including cleanup."""
    settings = policy(cfg)
    engine = engine or Renewal(cfg, ax)
    path = Path(cfg["state_file"] + ".maintenance.json")
    state = read_state(path, engine.identity)
    if state["next_retry_at"] > now().timestamp():
        return {"ok": False, "mode": "maintenance", "status": "backoff",
                "next_retry_at": state["next_retry_at"], "business_verified": False}, 2
    if not navigation_due(state, settings, engine.rows, now, pending=engine.journal.exists()):
        # 未到期跳过：零 GUI、零状态副作用（failures/next_retry_at 原样保留
        # ——跳过既不证明也不推翻上一次导航的成败），只落本轮 run result。
        result = {"ok": True, "mode": "maintenance", "status": "not_due_skipped",
                  "rows": {}, "business_verified": False, "pending_recovery": False,
                  "checked_at": now().isoformat(timespec="seconds")}
        atomic_json(cfg["state_file"], result)
        return result, 0
    result = {"ok": False, "mode": "maintenance", "status": "failed", "rows": {},
              "business_verified": False, "pending_recovery": engine.journal.exists()}
    attempted = False

    def save():
        atomic_json(path, state)

    def settle(name, row):
        state["permissions"][name] = {
            "expiry": expiry_text(row),
            "next_allowed_at": now().timestamp() + settings["min_renew_interval_seconds"],
        }
        save()  # Each successful row survives failure of a subsequent row.

    try:
        attempted = True
        window = engine.open(activate=True)  # Navigation is still opt-in in Keeper config.
        before = observe(engine, window)
        engine.recover_pending(window)  # Restoration always precedes any fresh revocation.
        for name in engine.rows:
            row = observe(engine, window)[name]
            record = state["permissions"].get(name, {})
            action = "not_due"
            intent = record.get("intent")
            if intent and row["status"] == "authorized":
                old = iso(intent["expiry_before"])
                if old is not None and row["expiry"] <= old:
                    raise KeeperError("action_outcome_unknown", "Prior action is unresolved; no new revocation issued")
                settle(name, row)
                action = "reconciled"
            elif row["status"] == "expired":
                record["intent"] = {"expiry_before": expiry_text(row), "started_at": now().timestamp()}
                state["permissions"][name] = record
                save()
                engine.authorize(window, name, row["expiry"])
                row = observe(engine, window)[name]
                settle(name, row)
                action = "restored"
            elif row["expiry"] <= now() + timedelta(hours=settings["within_hours"]):
                if (record.get("expiry") == expiry_text(row)
                        and record.get("next_allowed_at", 0) > now().timestamp()):
                    action = "cooldown"
                else:
                    record["intent"] = {"expiry_before": expiry_text(row), "started_at": now().timestamp()}
                    state["permissions"][name] = record
                    save()  # Covers a crash after Keeper removes its pending journal.
                    engine.pre_renew(window, name, row)
                    row = observe(engine, window)[name]
                    settle(name, row)
                    action = "pre_renewed"
            observed = state["permissions"].setdefault(name, {"next_allowed_at": 0})
            observed.update(expiry=expiry_text(row), checked_at=now().isoformat(timespec="seconds"))
            save()
            result["rows"][name] = {"status": row["status"], "action": action,
                                    "expiry": expiry_text(row), "expiry_before": expiry_text(before[name])}
        after = observe(engine, window)
        if any(row["status"] != "authorized" for row in after.values()) or engine.journal.exists():
            raise KeeperError("permissions_not_healthy", "Final permission verification failed")
        result.update(ok=True, status="renewed" if any(r["action"] in {"pre_renewed", "restored", "reconciled"}
                                                     for r in result["rows"].values()) else "healthy")
    except Exception as exc:
        error, _ = emit_error(exc)
        result.update(error)
    finally:
        if attempted:
            # 2026-11-14 语义：close_window 只关已验证授权页。2026-11-17 起在其
            # 【之后】追加导航遗留面板清理（搜索下拉/聊天记录面板——每小时
            # 残窗的第三根源；先关页再做，天然消除授权页对主窗工具栏的遮挡，
            # 门审轮1 P2-3）。
            if settings["close_window"]:
                try:
                    closed, _ = engine.close_window()
                    result["cleanup"] = {"ok": True, "closed": closed["closed"]}
                except Exception:
                    result["cleanup"] = {"ok": False, "error": "window_cleanup_failed"}
                    if result["ok"]:
                        result.update(ok=False, status="cleanup_failed", error="window_cleanup_failed")
            try:
                import keeper_navigation
                result.setdefault("cleanup", {})["navigation"] = keeper_navigation.restore_navigation(engine)
            except Exception:
                result.setdefault("cleanup", {})["navigation"] = {"ok": False}
    result["pending_recovery"] = engine.journal.exists()
    result["checked_at"] = now().isoformat(timespec="seconds")
    if result["ok"]:
        state.update(failures=0, next_retry_at=0)
    else:
        state["failures"] += 1
        state["next_retry_at"] = now().timestamp() + min(3600, settings["retry_seconds"] * 2 ** min(state["failures"] - 1, 6))
    save()
    atomic_json(cfg["state_file"], result)
    return result, 0 if result["ok"] else 2
