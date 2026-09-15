#!/bin/bash
# 保活主循环（探针 + 850003 自动续期联动）——launchd 每小时调起
# 逻辑：双探针 → 任一 850003 → 自动调 renew.py --renew → 复探 → 通知
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
DIR="$(cd "$(dirname "$0")/.." && pwd)"
CFG="$DIR/config.json"
PY=$(python3 -c "import json;print(json.load(open('$CFG')).get('venv_python','python3'))")
NOTIFY_TO=$(python3 -c "import json;print(json.load(open('$CFG')).get('notify_to',''))")
BRIDGE=$(python3 -c "import json;print(json.load(open('$CFG')).get('bridge_url',''))")
LOG=$(python3 -c "import json,os;print(os.path.expanduser(json.load(open('$CFG')).get('log_file','/tmp/wecom-auth-renew.log')))")
LOCKDIR="/tmp/wecom-auth-keepalive.lock"

mkdir "$LOCKDIR" 2>/dev/null || {
  if [ -n "$(find "$LOCKDIR" -maxdepth 0 -mmin +10 2>/dev/null)" ]; then
    rmdir "$LOCKDIR" 2>/dev/null; mkdir "$LOCKDIR" 2>/dev/null || exit 0
  else
    exit 0
  fi
}
trap 'rmdir "$LOCKDIR" 2>/dev/null' EXIT
cd "$DIR"   # launchd 无 cwd——renew.py 的 bridge 依赖需要

PROBE_OUT=$(bash "$DIR/scripts/probe.sh" 2>/dev/null)
echo "$PROBE_OUT" >> "$LOG"
READ=$(echo "$PROBE_OUT" | grep -o 'read_errcode=[0-9a-z?]*' | head -1 | cut -d= -f2)
WRITE=$(echo "$PROBE_OUT" | grep -o 'write_errcode=[0-9a-z?]*' | head -1 | cut -d= -f2)

if [ "$READ" = "850003" ] || [ "$WRITE" = "850003" ]; then
  TS=$(date '+%Y-%m-%dT%H:%M:%S%z')
  echo "[$TS] 850003 detected (read=$READ write=$WRITE) → auto renew" >> "$LOG"
  if ! pgrep -x 企业微信 >/dev/null; then
    echo "[$TS] WeCom not running — skip, next cycle retries" >> "$LOG"
    exit 0
  fi
  RENEW_OUT=$("$PY" "$DIR/renew.py" --config "$CFG" --renew 2>&1)
  echo "$RENEW_OUT" >> "$LOG"
  sleep 3
  AFTER=$(bash "$DIR/scripts/probe.sh" 2>/dev/null)
  echo "$AFTER" >> "$LOG"
  R2=$(echo "$AFTER" | grep -o 'read_errcode=[0-9a-z?]*' | head -1 | cut -d= -f2)
  W2=$(echo "$AFTER" | grep -o 'write_errcode=[0-9a-z?]*' | head -1 | cut -d= -f2)
  if [ -n "$NOTIFY_TO" ] && [ -n "$BRIDGE" ]; then
    if [ "$R2" = "0" ] && [ "$W2" = "0" ]; then
      MSG="✅ wecom-cli 授权自动续期成功：850003(read=$READ write=$WRITE)已自动重授权，复探双绿。$RENEW_OUT"
    else
      MSG="⚠️ wecom-cli 授权自动续期后仍未恢复(read=$R2 write=$W2)，需人工：报错回执续期链接点一下，或 auth init 扫码选原 bot。$RENEW_OUT"
    fi
    python3 - "$MSG" "$NOTIFY_TO" "$BRIDGE" << 'PYEOF' >> "$LOG" 2>&1
import json, sys, time, urllib.request
msg, to, bridge = sys.argv[1], sys.argv[2], sys.argv[3]
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
for i in range(2):
    try:
        payload = json.dumps({"to": to, "message": msg[:800],
                              "idempotency_key": "wacl-notify-" + time.strftime("%Y%m%d%H%M")}).encode()
        req = urllib.request.Request(bridge + "/wecom/send", data=payload,
                                     headers={"Content-Type": "application/json"})
        with opener.open(req, timeout=120) as r:
            print("notify sent:", r.status); break
    except Exception as e:
        print("notify try", i, "failed:", e); time.sleep(5)
PYEOF
  fi
fi
