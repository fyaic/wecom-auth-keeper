#!/usr/bin/env python3
"""Pre-deployment checks for the 装柜提醒bot maintenance configuration.

Pure checks first (no GUI): required fields, capability whitelist membership,
str_aibotid format, venv executable, state/log destinations writable. With
--wecom-cli-env DIR it additionally verifies the CLI's bound Bot ID equals
str_aibotid (prevents renewing the wrong bot). Exits non-zero with a JSON
error via keeper_common, matching the other entry points.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from keeper_common import KeeperError, emit_error, load_config  # noqa: E402
from keeper_capabilities import CAPABILITY_LABELS  # noqa: E402

REQUIRED_KEYS = ("bot_chat_name", "aibotid", "str_aibotid", "venv_python", "state_file", "log_file")


def check_fields(cfg):
    problems = []
    for key in REQUIRED_KEYS:
        value = cfg.get(key)
        if not isinstance(value, str) or not value.strip():
            problems.append(f"missing:{key}")
        elif value.strip().startswith("<"):
            problems.append(f"placeholder:{key}")
    if problems:
        raise KeeperError("invalid_config", "Fill these fields: " + ", ".join(problems), 3)
    if not re.fullmatch(r"[0-9]+", cfg["aibotid"].strip()):
        raise KeeperError("invalid_config", "aibotid should be the numeric id from the authorization link", 3)
    if not cfg["str_aibotid"].strip().startswith("aib"):
        raise KeeperError("invalid_config", "str_aibotid should start with 'aib' and equal wecom-cli auth show Bot ID", 3)
    unknown = [row for row in cfg.get("target_rows", []) if row not in CAPABILITY_LABELS]
    if unknown:
        raise KeeperError("invalid_config", "target_rows not in capability catalog: " + ", ".join(unknown), 3)
    return {"fields": "ok", "target_rows": cfg["target_rows"]}


def check_paths(cfg):
    python = Path(cfg["venv_python"]).expanduser()
    if not python.is_file() or not os.access(python, os.X_OK):
        raise KeeperError("venv_missing", f"venv_python not executable: {python}", 3)
    for key in ("state_file", "log_file"):
        parent = Path(cfg[key]).expanduser().parent
        parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if not os.access(parent, os.W_OK):
            raise KeeperError("destination_unwritable", f"Cannot write {key} directory: {parent}", 3)
    return {"paths": "ok"}


def check_cli_identity(cfg, env_dir):
    env = dict(os.environ)
    base = Path(env_dir).expanduser()
    for var, sub in (("WECOM_CLI_CONFIG_DIR", "config"), ("WECOM_CLI_TMP_DIR", "tmp"), ("WECOM_CLI_LOG_DIR", "log")):
        env[var] = str(base / sub)
    try:
        result = subprocess.run(["wecom-cli", "auth", "show"], env=env, capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise KeeperError("cli_unavailable", f"wecom-cli auth show failed to run: {exc}", 3) from exc
    match = re.search(r"Bot ID:\s*(\S+)", result.stdout)
    if not match:
        raise KeeperError("cli_unexpected_output", result.stdout.strip()[:120] or "no Bot ID line", 3)
    bot_id = match.group(1)
    if bot_id != cfg["str_aibotid"].strip():
        raise KeeperError("bot_mismatch", f"CLI bot {bot_id} != configured str_aibotid; refusing to renew another bot", 3)
    status = re.search(r"Status:\s*(\S+)", result.stdout)
    return {"cli_identity": "ok", "bot_id": bot_id, "cli_status": status.group(1) if status else None}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, help="Private maintenance config path (didadi)")
    parser.add_argument("--wecom-cli-env", default="~/.config/warecheck-v2/wecom-directory-didadi",
                        help="Identity dir used by the warecheck pipelines (default: didadi)")
    args = parser.parse_args(argv)
    try:
        cfg = load_config(args.config)
        report = {"ok": True, "mode": "preflight-didadi"}
        report.update(check_fields(cfg))
        report.update(check_paths(cfg))
        report.update(check_cli_identity(cfg, args.wecom_cli_env))
    except KeeperError as exc:
        result, code = emit_error(exc)
        print(json.dumps(result, ensure_ascii=False))
        return code
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
