#!/usr/bin/env python3
"""Standalone scheduled pre-expiry maintenance for any explicit target_rows allowlist."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import plistlib
import subprocess
import sys

from keeper_capabilities import CAPABILITY_GROUPS
from keeper_common import KeeperError, atomic_json, emit_error, executable, gui_lock_path, load_config, process_lock
from keeper_maintenance import policy, read_state, run_cycle
from keeper_bootstrap import require_entry
from renew import Renewal, monitor_guard


def validate_destinations(cfg):
    paths = [Path(cfg[key]).resolve() for key in ("_config_path", "state_file", "log_file")]
    paths += [Path(cfg["state_file"] + suffix).resolve() for suffix in (".pending.json", ".maintenance.json")]
    paths.append(Path(cfg["log_file"] + ".maintenance.log").resolve())
    if cfg.get('entry_receipt'):
        paths.append(Path(cfg['entry_receipt']).resolve())
    if len(set(paths)) != len(paths):
        raise KeeperError("invalid_config", "Configuration, evidence, recovery and schedule files must be distinct", 3)


def write_launchagent(cfg, output):
    validate_destinations(cfg)
    require_entry(cfg)
    settings = policy(cfg)
    output = Path(output).expanduser().absolute()
    forbidden = {Path(cfg[key]).resolve() for key in ("_config_path", "state_file", "log_file")}
    forbidden.update(Path(cfg["state_file"] + suffix).resolve() for suffix in (".pending.json", ".maintenance.json"))
    forbidden.add(Path(cfg["log_file"] + ".maintenance.log").resolve())
    if cfg.get('entry_receipt'):
        forbidden.add(Path(cfg['entry_receipt']).resolve())
    if output.resolve() in forbidden:
        raise KeeperError("invalid_output", "LaunchAgent must not replace configuration or state", 3)
    python = executable(cfg.get("venv_python"), sys.executable)
    identity = hashlib.sha256((cfg["aibotid"] + ":" + cfg["str_aibotid"]).encode()).hexdigest()[:12]
    label = "com.fyaic.wecom-auth-keeper." + identity
    log = Path(cfg["log_file"] + ".maintenance.log")
    log.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    data = {"Label": label, "RunAtLoad": True, "StartInterval": settings["interval_seconds"],
            "ProgramArguments": [python, str(Path(__file__).resolve()), "--config", cfg["_config_path"]],
            "WorkingDirectory": str(Path(__file__).resolve().parent),
            "StandardOutPath": str(log), "StandardErrorPath": str(log)}
    output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        with output.open("xb") as stream:
            output.chmod(0o600)
            plistlib.dump(data, stream)
    except FileExistsError:
        raise KeeperError("launchagent_exists", "LaunchAgent already exists; inspect it before replacing", 3) from None
    return {"ok": True, "mode": "write-launchagent", "installed": False, "label": label,
            "interval_seconds": settings["interval_seconds"], "within_hours": settings["within_hours"]}


def supervise(cfg, *, run=subprocess.run):
    require_entry(cfg)
    # The parent keeps ownership through worker termination and cleanup. A killed
    # worker cannot run its finally block, so it cannot own monitor restoration.
    with process_lock(gui_lock_path(), cfg["lock_wait"]) as lock_fd:
        cfg = {**cfg, "_desktop_lock_fd": lock_fd}
        result = None
        try:
            with monitor_guard(cfg):
                result, code = supervised_worker(cfg, run=run)
        except Exception as exc:
            error, _ = emit_error(exc)
            status = "monitor_restore_failed" if result is not None else "monitor_coordination_failed"
            # Preserve completed renewal/cleanup evidence if only the outer
            # monitor restoration failed, but never retain its success verdict.
            result = {**(result or {}), **error, "mode": "maintenance", "status": status,
                      "business_verified": False}
            code = 2
        result.setdefault("mode", "maintenance")
        result.setdefault("status", "healthy" if result["ok"] else "failed")
        result.setdefault("checked_at", datetime.now().isoformat(timespec="seconds"))
        result["pending_recovery"] = Path(cfg["state_file"] + ".pending.json").exists()
        # Publish the final supervised outcome before releasing the desktop.
        # Timeout/invalid output must replace a prior healthy state too. A
        # caller that never obtained this lock must not overwrite its owner.
        atomic_json(cfg["state_file"], result)
        return result, code


def supervised_worker(cfg, *, run=subprocess.run):
    """Bound the worker lifetime, including native AX calls; timeout never claims success."""
    python = executable(cfg.get("venv_python"), sys.executable)
    args = [python, str(Path(__file__).resolve()), "--config", cfg["_config_path"], "--worker"]
    inheritance = {"pass_fds": (cfg["_desktop_lock_fd"],)} if "_desktop_lock_fd" in cfg else {}
    try:
        child = run(args, capture_output=True, text=True, timeout=cfg["renew_timeout"], **inheritance)
        value = json.loads(child.stdout)
        if not isinstance(value, dict) or not isinstance(value.get("ok"), bool):
            raise ValueError()
        if child.returncode == 0 and value["ok"] and value.get("mode") == "maintenance":
            return value, 0
        if child.returncode != 0 and not value["ok"]:
            return value, 2
        raise ValueError()
    except subprocess.TimeoutExpired:
        result = {"ok": False, "mode": "maintenance", "status": "timeout", "error": "maintenance_timeout",
                  "business_verified": False}
    except (OSError, ValueError, TypeError):
        result = {"ok": False, "mode": "maintenance", "status": "failed",
                  "error": "invalid_worker_response", "business_verified": False}
    if policy(cfg)["close_window"]:
        try:
            # A timeout or abnormal worker exit cannot run its finally block.
            # Cleanup inherits the same parent lease and keeps its own budget.
            child = run([python, str(Path(__file__).resolve()), "--config", cfg["_config_path"],
                         "--cleanup-worker"], capture_output=True, text=True, timeout=30, **inheritance)
            closed = json.loads(child.stdout)
            valid = (isinstance(closed, dict) and child.returncode == 0
                     and closed.get("ok") is True and isinstance(closed.get("closed"), bool))
            result["cleanup"] = {"ok": valid}
            if valid:
                result["cleanup"]["closed"] = closed["closed"]
        except Exception:
            result["cleanup"] = {"ok": False}
    return result, 2


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(Path(__file__).with_name("config.json")))
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--list-capabilities", action="store_true", help="Print reusable UI permission groups without accessing WeCom")
    mode.add_argument("--status", action="store_true", help="Read historical scheduler evidence without accessing WeCom")
    mode.add_argument("--write-launchagent", metavar="PATH", help="Generate a launchd job; does not install or start it")
    mode.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    mode.add_argument("--cleanup-worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        if args.list_capabilities:
            result, code = {"ok": True, "capability_groups": CAPABILITY_GROUPS}, 0
        else:
            cfg = load_config(args.config)
            validate_destinations(cfg)
            settings = policy(cfg)
            if args.write_launchagent:
                result, code = write_launchagent(cfg, args.write_launchagent), 0
            elif args.status:
                state = read_state(Path(cfg["state_file"] + ".maintenance.json"), Renewal(cfg, None).identity)
                result, code = {"ok": True, "mode": "status", "historical": True, "policy": settings,
                                "permissions": state["permissions"], "failures": state["failures"],
                                "next_retry_at": state["next_retry_at"]}, 0
            elif args.worker or args.cleanup_worker:
                if sys.platform != "darwin":
                    raise KeeperError("unsupported_platform", "Scheduled desktop maintenance requires macOS", 3)
                import keeper_ax as ax
                # Internal worker: the supervising parent holds the desktop lock.
                result, code = Renewal(cfg, ax).close_window() if args.cleanup_worker else run_cycle(cfg, ax)
            else:
                result, code = supervise(cfg)
    except Exception as exc:
        result, code = emit_error(exc)
    print(json.dumps(result, ensure_ascii=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
