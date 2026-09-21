#!/usr/bin/env python3
"""Credential-free syntax/config/document-link checks; no GUI or WeCom calls."""

import ast
import json
import plistlib
import re
import subprocess
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]


def main():
    errors = []
    # Git inventory includes new, non-ignored files but excludes local venv/secrets.
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    paths = sorted({ROOT / name for name in result.stdout.split("\0") if name})
    for path in paths:
        if not path.exists():
            continue  # A staged/uncommitted deletion need not be readable.
        label = str(path.relative_to(ROOT))
        try:
            if path.suffix == ".py":
                ast.parse(path.read_text(encoding="utf-8"), filename=label)
            elif path.suffix == ".sh":
                check = subprocess.run(["bash", "-n", str(path)], capture_output=True, text=True)
                if check.returncode:
                    raise ValueError(check.stderr.strip())
            elif path.name.endswith(".plist.example"):
                with path.open("rb") as stream:
                    plist = plistlib.load(stream)
                if not plist.get("ProgramArguments") or plist.get("StartInterval", 0) <= 0:
                    raise ValueError("launchd example lacks command or positive interval")
            elif path.suffix == ".md":
                # Inline relative-link targets, excluding fenced code and anchors.
                prose = re.sub(r"```.*?```", "", path.read_text(encoding="utf-8"), flags=re.S)
                for target in re.findall(r"\]\(([^\s)]+)\)", prose):
                    parts = urlsplit(target.strip("<>"))
                    if parts.scheme or parts.netloc or not parts.path:
                        continue
                    linked = path.parent / unquote(parts.path)
                    if not linked.exists():
                        errors.append(f"{label}: missing local link {target}")
        except (ValueError, SyntaxError, OSError) as exc:
            errors.append(f"{label}: {exc}")

    config = json.loads((ROOT / "config.example.json").read_text(encoding="utf-8"))
    required = {
        "bot_chat_name", "aibotid", "str_aibotid", "target_rows",
        "read_docid", "write_docid", "write_sheet", "venv_python",
        "wecom_bridge_src", "state_file", "log_file", "bridge_url",
        "bridge_send_link", "notify_to",
    }
    missing = required - config.keys()
    if missing:
        errors.append("config.example.json: missing fields " + ", ".join(sorted(missing)))
    if not isinstance(config.get("bridge_send_link"), bool):
        errors.append("config.example.json: bridge_send_link must be boolean")
    for error in errors:
        print("FAIL:", error)
    if errors:
        return 1
    print("PASS: Python/Bash syntax, plist, example config and local inline Markdown links")
    print("Not tested: live GUI, authorization renewal, external links or business APIs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
