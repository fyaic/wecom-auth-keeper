#!/bin/bash
# 双探针：读（业务表 sheet get）+ 写（bot 自有测试表写时间戳）——纯 CLI，零 GUI
# 配置：../config.json 的 read_docid / write_docid / write_sheet
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
DIR="$(cd "$(dirname "$0")/.." && pwd)"
CFG="$DIR/config.json"
[ -f "$CFG" ] || { echo "[PROBE] no config.json"; exit 1; }
READ_DOCID=$(python3 -c "import json;print(json.load(open('$CFG')).get('read_docid',''))")
WRITE_DOCID=$(python3 -c "import json;print(json.load(open('$CFG')).get('write_docid',''))")
WRITE_SHEET=$(python3 -c "import json;print(json.load(open('$CFG')).get('write_sheet',''))")
CRED=~/.config/wecom/credentials.enc
TS=$(date '+%Y-%m-%dT%H:%M:%S%z')
CRED_BEFORE=$(stat -f '%Sm' -t '%Y-%m-%dT%H:%M:%S' "$CRED" 2>/dev/null)
READ_OUT=$(/opt/homebrew/bin/wecom-cli sheet get --docid "$READ_DOCID" 2>&1)
READ_ERR=$(echo "$READ_OUT" | python3 -c "
import json,sys
try: print(json.loads(sys.stdin.read()).get('errcode','?'))
except Exception: print('parse_fail')" 2>/dev/null)
WRITE_OUT=$(python3 -c "
import subprocess, json
payload = {'start_row': 0, 'start_column': 0, 'rows': [{'values': [{'data_type':'TEXT','cell_value':{'text':'keepalive-$(date +%s)'}}]}]}
p = subprocess.run(['/opt/homebrew/bin/wecom-cli','sheet','contents','update',
    '--docid','$WRITE_DOCID','--sheet-id','$WRITE_SHEET',
    '--grid-data', json.dumps(payload)], capture_output=True, text=True, timeout=90)
try: print(json.loads(p.stdout).get('errcode','?'))
except Exception: print('parse_fail')" 2>&1)
CRED_AFTER=$(stat -f '%Sm' -t '%Y-%m-%dT%H:%M:%S' "$CRED" 2>/dev/null)
REFRESHED="no"; [ "$CRED_BEFORE" != "$CRED_AFTER" ] && REFRESHED="yes"
echo "[PROBE] ts=$TS read_errcode=$READ_ERR write_errcode=$WRITE_OUT cred_refreshed=$REFRESHED"
