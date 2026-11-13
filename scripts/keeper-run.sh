#!/bin/bash
# Local coordination wrapper for scheduled maintain.py cycles on THIS machine.
#
# The wecom-bridge service shares the same WeCom desktop: its OrgRotator polls
# every ~2s and would switch organizations mid-navigation (return-home debt),
# killing the keeper's chat-history search. This wrapper holds the bridge's
# TTL-bounded GUI lease around the cycle; maintain.py's built-in monitor_guard
# separately parks the bridge monitor in observe mode during the GUI phase.
# Lease TTL (600s) bounds the damage if this wrapper is SIGKILLed: the bridge
# self-recovers and multi-org intake resumes without human action.
set -euo pipefail

BRIDGE="${WECOM_BRIDGE_URL:-http://127.0.0.1:23392}"
DIR="$(cd "$(dirname "$0")/.." && pwd)"
CFG="${1:-$DIR/config.json}"

lease() {
  curl -sS --max-time 10 -X POST "$BRIDGE/wecom/orgs/rotator/pause" \
    -H "Content-Type: application/json" \
    -d '{"seconds":600,"reason":"wecom-auth-keeper scheduled cycle"}' >/dev/null
}
release() {
  curl -sS --max-time 10 -X POST "$BRIDGE/wecom/orgs/rotator/resume" >/dev/null
}

lease || echo "$(date '+%F %T') [keeper-run] bridge lease unavailable; running uncoordinated" >&2

# Zero-message chat open: put the renewal channel DM on screen so the keeper's
# first path (click the identity-verified link at the bottom of the chat)
# always works. The keeper's own search fallback is unreliable for bot DMs on
# WeCom 5.0.13 — this replaces it as the primary navigation entry.
open_chat() {
  python3 - "$BRIDGE" "$CFG" <<'PYOPEN' || echo "$(date '+%F %T') [keeper-run] chat open failed; keeper will try its own navigation" >&2
import json, sys, urllib.request
from pathlib import Path
cfg = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
body = {"name": cfg["bot_chat_name"]}
if cfg.get("bot_chat_org"):
    body["organization"] = cfg["bot_chat_org"]
req = urllib.request.Request(sys.argv[1].rstrip("/") + "/wecom/conversations/open",
                             data=json.dumps(body).encode(),
                             headers={"Content-Type": "application/json"}, method="POST")
with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=120) as r:
    result = json.load(r)
sys.exit(0 if result.get("success") else 2)
PYOPEN
}
open_chat

# Conditional fresh-link seeding: only fires when a permission enters its
# pre-renew window this cycle (one message per week in steady state). Must run
# inside the lease so the bridge send does not race the rotator either.
SEEDED_JSON=$("$DIR/.venv/bin/python" "$DIR/scripts/seed-if-due.py" --config "$CFG") ||
  echo "$(date '+%F %T') [keeper-run] seed-if-due failed; continuing" >&2
echo "$SEEDED_JSON"
if echo "$SEEDED_JSON" | grep -q '"seeded": *true'; then
  # The bridge send returns before its post-send GUI work (post-send read,
  # return-home) finishes; give the desktop time to settle before navigating.
  sleep 25
fi

rc=0
"$DIR/.venv/bin/python" "$DIR/maintain.py" --config "$CFG" || rc=$?
release || true

# Best-effort failure ping (GUI may be the broken part; bridge send queues or fails silently).
# Rate-limited to one per 6h: overnight failure storms must not spam the notify chat.
if [ "$rc" -ne 0 ] && ! find /tmp/wak-last-fail-ping -mtime -6h 2>/dev/null | grep -q .; then
  touch /tmp/wak-last-fail-ping
  "$DIR/.venv/bin/python" - "$BRIDGE" "$CFG" <<'PYFAIL' || true
import json, sys, time, urllib.request
from pathlib import Path
log = Path.home() / ".wecom-auth-renew/maintenance-launchd.log"
tail = log.read_text(errors="replace")[-300:] if log.exists() else "(no log)"
cfg = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
to = cfg.get("notify_to") or "AI助手测试专用"
body = {"to": to,
        "message": f"[wecom-auth-keeper] 周期失败(exit≠0) @ {time.strftime('%F %T')}\n{tail}",
        "idempotency_key": f"wak-fail-{time.time_ns()}"}
if cfg.get("notify_org"):
    body["organization"] = cfg["notify_org"]
req = urllib.request.Request(sys.argv[1] + "/wecom/send", data=body,
                             headers={"Content-Type": "application/json"}, method="POST")
urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=90)
PYFAIL
fi
exit $rc
