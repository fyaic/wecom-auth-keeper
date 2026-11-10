#!/usr/bin/env python3
"""Bounded read/write probes. The write probe overwrites cell A1 of a test sheet."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys
import time

from keeper_common import emit_error, executable, load_config


def call_cli(binary, args, timeout):
    try:
        process = subprocess.run([binary, *args], capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"ok": False, "errcode": None, "error": "timeout"}
    except OSError:
        return {"ok": False, "errcode": None, "error": "execution_failed"}
    try:
        data = json.loads(process.stdout)
        code = data.get("errcode") if isinstance(data, dict) else None
        if isinstance(code, str) and code.isdecimal():
            code = int(code)
        if isinstance(code, bool) or not isinstance(code, int):
            raise ValueError("Missing numeric errcode")
    except (ValueError, TypeError):
        return {"ok": False, "errcode": None, "error": "invalid_response", "returncode": process.returncode}
    return {"ok": code == 0 and process.returncode == 0, "errcode": code,
            "returncode": process.returncode, "error": None if code == 0 and process.returncode == 0 else "cli_error"}


def run_probes(cfg):
    binary = executable(cfg.get("wecom_cli"), "wecom-cli")
    read = call_cli(binary, ["sheet", "get", "--docid", cfg["read_docid"]], cfg["probe_timeout"])
    grid = {"start_row": 0, "start_column": 0, "rows": [{"values": [{
        "data_type": "TEXT", "cell_value": {"text": f"keepalive-{int(time.time())}"}}]}]}
    write = call_cli(binary, ["sheet", "contents", "update", "--docid", cfg["write_docid"],
                             "--sheet-id", cfg["write_sheet"], "--grid-data", json.dumps(grid)], cfg["probe_timeout"])
    return {"ok": read["ok"] and write["ok"], "checked_at": datetime.now().isoformat(), "read": read, "write": write}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(Path(__file__).with_name("config.json")))
    args = parser.parse_args(argv)
    try:
        result = run_probes(load_config(args.config, probes=True))
        code = 0 if result["ok"] else 2
    except Exception as exc:
        result, code = emit_error(exc)
    print(json.dumps(result, ensure_ascii=False))
    return code


if __name__ == "__main__":
    sys.exit(main())
