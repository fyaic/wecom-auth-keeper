#!/usr/bin/env python3
"""Standalone scheduled pre-expiry maintenance for any explicit target_rows allowlist."""
import argparse
import hashlib
import json
from pathlib import Path
import plistlib
import subprocess
import sys

from keeper_capabilities import CAPABILITY_GROUPS
from keeper_common import KeeperError, emit_error, executable, gui_lock_path, load_config, process_lock
from keeper_maintenance import policy, read_state, run_cycle
from renew import Renewal


def validate_destinations(cfg):
    paths = [Path(cfg[key]).resolve() for key in ("_config_path", "state_file", "log_file")]
    paths += [Path(cfg["state_file"] + suffix).resolve() for suffix in (".pending.json", ".maintenance.json")]
    paths.append(Path(cfg["log_file"] + ".maintenance.log").resolve())
    if len(set(paths)) != len(paths):
        raise KeeperError("invalid_config", "Configuration, evidence, recovery and schedule files must be distinct", 3)


def write_launchagent(cfg, output):
    validate_destinations(cfg)
    settings = policy(cfg)
    output = Path(output).expanduser().absolute()
    forbidden = {Path(cfg[key]).resolve() for key in ("_config_path", "state_file", "log_file")}
    forbidden.update(Path(cfg["state_file"] + suffix).resolve() for suffix in (".pending.json", ".maintenance.json"))
    forbidden.add(Path(cfg["log_file"] + ".maintenance.log").resolve())
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
    """Bound the worker lifetime, including native AX calls; timeout never claims success."""
    python = executable(cfg.get("venv_python"), sys.executable)
    args = [python, str(Path(__file__).resolve()), "--config", cfg["_config_path"], "--worker"]
    try:
        child = run(args, capture_output=True, text=True, timeout=cfg["renew_timeout"])
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
        if policy(cfg)["close_window"]:
            try:
                child = run([python, str(Path(__file__).with_name("renew.py")), "--config", cfg["_config_path"],
                             "--close-window"], capture_output=True, text=True, timeout=30)
                closed = json.loads(child.stdout)
                result["cleanup"] = {"ok": child.returncode == 0 and closed.get("ok") is True}
            except Exception:
                result["cleanup"] = {"ok": False}
        return result, 2
    except (OSError, ValueError, TypeError):
        return {"ok": False, "mode": "maintenance", "error": "invalid_worker_response"}, 2


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(Path(__file__).with_name("config.json")))
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--list-capabilities", action="store_true", help="Print reusable UI permission groups without accessing WeCom")
    mode.add_argument("--status", action="store_true", help="Read historical scheduler evidence without accessing WeCom")
    mode.add_argument("--write-launchagent", metavar="PATH", help="Generate a launchd job; does not install or start it")
    mode.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
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
            elif args.worker:
                if sys.platform != "darwin":
                    raise KeeperError("unsupported_platform", "Scheduled desktop maintenance requires macOS", 3)
                import keeper_ax as ax
                with process_lock(gui_lock_path(), cfg["lock_wait"]):
                    result, code = run_cycle(cfg, ax)
            else:
                result, code = supervise(cfg)
    except Exception as exc:
        result, code = emit_error(exc)
    print(json.dumps(result, ensure_ascii=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
