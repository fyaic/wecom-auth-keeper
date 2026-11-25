#!/bin/bash
# warecheck 全链路日检（2026-11-25 停更 24h 无人察觉事故后制定）
# 用法: bash warecheck-daily-check.sh
# 判定口径: 只看"每轮 run 的真实状态"和"最后成功时间"，绝不用表行数代替（行数不变也显示存在）。
set -u
SERVER=ddd-bondie@100.89.149.114
SSH="ssh -o ConnectTimeout=15 -o BatchMode=yes $SERVER"
FAIL=0

echo "===== 服务器 ddd-bondie ====="
SERVER_OUT=$($SSH 'bash -s' <<'REMOTE'
echo "--v2 装柜--"
cd ~/Projects/warecheck-v2/v2/customer-data-confirmation/.runtime/loading-lite 2>/dev/null || { echo "MISSING runtime dir"; exit 1; }
python3 - <<PY
import json, glob, time, datetime
runs = sorted(glob.glob("runs/*.json"))
d = json.load(open(runs[-1]))
ok_at = json.load(open("alert-state.json")) if False else None
import sqlite3
c = sqlite3.connect("state.sqlite3")
ok = c.execute("SELECT MAX(finished_at) FROM runs WHERE status IN ('ok','capture_partial')").fetchone()[0]
age = (time.time() - ok) / 60 if ok else -1
print(f"latest_run: {d['started_at']} status={d.get('status')} err={str(d.get('error'))[:60]}")
print(f"last_ok_age_minutes: {round(age,1)}  notify: {d.get('notify')}")
print(f"alert_state: {open('alert-state.json').read().strip() or '{}'}")
PY
echo "--v1 验货--"
python3 - <<PY
import json, time
try:
    h = json.load(open("/Users/bondie/.config/warecheck/phase1-observe/flow2-health.json"))
    print("health:", h["health"], " last_error:", h["last_error"])
    r = h.get("notification_routing", {})
    print("routing eligible/blocked:", r.get("eligible"), "/", r.get("blocked"), " gates:", h.get("notification_gates"))
    print("problems:", h.get("health_problems"))
except Exception as e:
    print("health read failed:", e)
PY
echo "--launchd--"
launchctl list | grep -E "warecheck|flow2" || true
REMOTE
) || FAIL=1
echo "$SERVER_OUT"

echo
echo "===== 本机 keeper ====="
tail -1 ~/.wecom-auth-renew/didadi/run.log.maintenance.log 2>/dev/null | python3 -c "
import json,sys
try:
    d = json.loads(sys.stdin.read())
    print('keeper:', d.get('status'), 'at', d.get('checked_at'), ('ERR:'+str(d.get('error'))) if not d.get('ok') else '')
except Exception as e:
    print('keeper log unreadable:', e)
"
pgrep -x "企业微信" >/dev/null && echo "WeCom: running" || { echo "WeCom: NOT RUNNING (keeper will fail)"; FAIL=1; }

echo
echo "===== git ====="
for r in ~/projects/warecheck-v2 ~/projects/warecheck ~/projects/wecom-auth-keeper; do
  s=$(git -C $r status --short --branch | head -1)
  dirty=$(git -C $r status --short | wc -l | tr -d ' ')
  echo "$(basename $r): $s (dirty:$dirty)"
done

echo
if echo "$SERVER_OUT" | grep -qE "last_ok_age_minutes: (-1|[1-9][0-9][0-9]*)\."; then
  echo "!! v2 停更（无成功记录或超过 100 分钟），立即排查"
  FAIL=1
fi
echo "$SERVER_OUT" | grep -q "health: ok" || { echo "!! v1 非健康状态，看上方 problems"; FAIL=1; }
[ $FAIL -eq 0 ] && echo "RESULT: PASS" || echo "RESULT: NEED ATTENTION"
exit $FAIL
