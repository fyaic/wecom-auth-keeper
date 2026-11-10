#!/usr/bin/env python3
"""Probe, recover expired permissions, verify, and optionally notify with deduplication."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

from keeper_common import KeeperError, atomic_json, emit_error, executable, load_config, process_lock
from probe import run_probes
from renew import bridge_request


def recover(cfg):
    python = executable(cfg.get("venv_python"), sys.executable)
    try:
        process = subprocess.run([python, str(Path(__file__).with_name("renew.py")),
                                  "--config", cfg["_config_path"], "--renew"],
                                 capture_output=True, text=True, timeout=cfg["renew_timeout"])
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "renew_timeout"}
    except OSError:
        return {"ok": False, "error": "renew_execution_failed"}
    try:
        result = json.loads(process.stdout)
        if not isinstance(result, dict) or not isinstance(result.get("ok"), bool):
            raise ValueError("Invalid renewal result")
    except (ValueError, TypeError):
        return {"ok": False, "error": "invalid_renew_response"}
    # Do not forward raw subprocess output / permission URLs to logs or recipients.
    return {"ok": process.returncode == 0 and result["ok"], "returncode": process.returncode,
            "error": result.get("error") if isinstance(result.get("error"), str) else None}


def cycle(cfg):
    before = run_probes(cfg)
    pending = Path(cfg["state_file"] + ".pending.json").exists()
    expired = any(before[k].get("errcode") == 850003 for k in ("read", "write"))
    if not expired and not pending:
        return {"ok": before["ok"], "status": "healthy" if before["ok"] else "probe_failed", "probes": before}
    renewal = recover(cfg)
    after = run_probes(cfg)
    # Require both the renewal contract and real API evidence; neither alone suffices.
    healthy = renewal["ok"] and after["ok"] and not Path(cfg["state_file"] + ".pending.json").exists()
    return {"ok": healthy, "status": "recovered" if healthy else "recovery_failed",
            "renewal": renewal, "probes": after}


def notify(cfg, result):
    if not cfg.get("notify_to") or not cfg.get("bridge_url"):
        return "disabled"
    receipt = Path(cfg["log_file"] + ".notice.json")
    previous = {}
    try:
        previous = json.loads(receipt.read_text())
    except (OSError, ValueError):
        pass
    if not isinstance(previous, dict):
        previous = {}
    signature = result["status"]
    # Healthy steady state is quiet; a transition out of failure still sends recovery.
    if signature == "healthy" and previous.get("status") in (None, "healthy", "recovered"):
        return "unchanged"
    now = time.time()
    sent_at = previous.get("sent_at", 0)
    if isinstance(sent_at, (int, float)) and previous.get("status") == signature and now - sent_at < 21600:
        return "deduplicated"
    message = ("✅ wecom-cli 授权探针恢复正常。" if result["ok"] else
               "⚠️ wecom-cli 授权保活失败，请检查本机日志与企业微信授权状态。")
    identity = hashlib.sha256(cfg["_config_path"].encode()).hexdigest()[:16]
    response = bridge_request(cfg, "POST", "/wecom/send", {
        "to": cfg["notify_to"], "message": message,
        "idempotency_key": f"wecom-keeper-{identity}-{signature}-{time.time_ns()}"})
    if response.get("success") is not True:
        raise KeeperError("notification_failed", "Bridge did not confirm notification delivery")
    atomic_json(receipt, {"status": signature, "sent_at": now})
    return "sent"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(Path(__file__).with_name("config.json")))
    args = parser.parse_args(argv)
    try:
        cfg = load_config(args.config)
        load_config(args.config, probes=True)
        with process_lock(cfg["state_file"] + ".keepalive.lock", cfg["lock_wait"]):
            try:
                result = cycle(cfg)
            except Exception as exc:
                result, _ = emit_error(exc)
                result["status"] = "operation_failed"
            try:
                result["notification"] = notify(cfg, result)
            except Exception:
                result["notification"] = "failed"
            result["checked_at"] = datetime.now().isoformat()
            log = Path(cfg["log_file"])
            log.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            with log.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(result, ensure_ascii=False) + "\n")
            code = 0 if result["ok"] and result["notification"] != "failed" else 2
    except Exception as exc:
        result, code = emit_error(exc)
    print(json.dumps(result, ensure_ascii=False))
    return code


if __name__ == "__main__":
    sys.exit(main())
