"""Reusable multi-permission, pre-expiry cycle. No model, Gateway or business probe dependency."""
from datetime import datetime, timedelta
import json
import math
from pathlib import Path

from keeper_common import KeeperError, atomic_json, emit_error
from renew import Renewal

DEFAULT_POLICY = {"within_hours": 24, "interval_seconds": 3600,
                  "min_renew_interval_seconds": 3600, "retry_seconds": 300,
                  "close_window": True}


def policy(cfg):
    raw = cfg.get("maintenance", {})
    if not isinstance(raw, dict) or set(raw) - DEFAULT_POLICY.keys():
        raise KeeperError("invalid_maintenance_policy", "Unknown maintenance settings", 3)
    value = {**DEFAULT_POLICY, **raw}
    limits = {"within_hours": (1, 168), "interval_seconds": (60, 86400),
              "min_renew_interval_seconds": (60, 86400), "retry_seconds": (60, 3600)}
    for name, (low, high) in limits.items():
        number = value[name]
        if (isinstance(number, bool) or not isinstance(number, (int, float))
                or not math.isfinite(number) or not low <= number <= high
                or (name.endswith("seconds") and not isinstance(number, int))):
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
        if attempted and settings["close_window"]:
            try:
                closed, _ = engine.close_window()
                result["cleanup"] = {"ok": True, "closed": closed["closed"]}
            except Exception:
                result["cleanup"] = {"ok": False, "error": "window_cleanup_failed"}
                if result["ok"]:
                    result.update(ok=False, status="cleanup_failed", error="window_cleanup_failed")
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
