#!/usr/bin/env python3
"""Seed a fresh authorization link into the bot chat when a renewal is due.

maintain.py navigates chat history for the link but never sends one, and WeCom
history search only indexes recent messages — a link seeded once ages out of
the index before the next 7-day cycle. This runs before each scheduled cycle
and sends the official link (built from the same aibotid/str_aibotid the
engine verifies) only when the maintenance state shows a permission entering
its pre-renew window this cycle, or when no state exists yet. Normal noise:
one message per week, at night, in the bot's own app chat.
"""
import argparse
import json
import sys
import time
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode


def send(cfg, bridge_url, idem):
    link = "https://work.weixin.qq.com/ai/aiHelper/authorizationList?" + urlencode({
        "from": "chat", "forceInnerBrowser": "1", "aibotid": cfg["aibotid"],
        "str_aibotid": cfg["str_aibotid"], "type": "1"})
    body = {"to": cfg["bot_chat_name"],
            "message": "续期通道（自动，请忽略）" + link,
            "idempotency_key": idem}
    if cfg.get("bot_chat_org"):
        body["organization"] = cfg["bot_chat_org"]
    req = urllib.request.Request(bridge_url.rstrip("/") + "/wecom/send",
                                 data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"},
                                 method="POST")
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=120) as r:
        result = json.load(r)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(Path(__file__).resolve().parents[1] / "config.json"))
    args = parser.parse_args()
    cfg = json.loads(Path(args.config).expanduser().read_text(encoding="utf-8"))
    within = cfg.get("maintenance", {}).get("within_hours", 24)
    state_path = Path(str(Path(cfg["state_file"]).expanduser()) + ".maintenance.json")

    due = not state_path.exists()
    why = "no-state"
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
            permissions = state.get("permissions", {})
            # Never successfully read the page yet (empty records): keep seeding
            # every cycle so the retry chain always has a fresh visible link.
            if not permissions:
                due, why = True, "no-permission-records-yet"
            else:
                horizon = datetime.now() + timedelta(hours=within)
                for record in permissions.values():
                    expiry = record.get("expiry")
                    if expiry and datetime.fromisoformat(expiry) <= horizon:
                        due, why = True, f"expiry {expiry} within {within}h"
                        break
        except (OSError, ValueError):
            due, why = True, "state-unreadable"

    if not due:
        print(json.dumps({"ok": True, "seeded": False, "reason": "not-due"}, ensure_ascii=False))
        return 0
    result = send(cfg, cfg["bridge_url"], f"wak-seed-{time.time_ns()}")
    print(json.dumps({"ok": bool(result.get("success")), "seeded": bool(result.get("success")),
                      "reason": why, "bridge": result}, ensure_ascii=False))
    return 0 if result.get("success") else 2


if __name__ == "__main__":
    sys.exit(main())
