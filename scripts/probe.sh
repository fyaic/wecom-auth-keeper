#!/bin/bash
<<<<<<< Updated upstream
# Compatibility entry point. stdout is now one JSON object; failures exit nonzero.
set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
DIR="$(cd "$(dirname "$0")/.." && pwd)"
exec "${PYTHON:-python3}" "$DIR/probe.py" "$@"
=======
# 双探针：读（业务智能表 records list）+ 写（bot 自有测试表 records add 时间戳）——纯 CLI，零 GUI
# 本机适配（vessel-eta-watch 部署）：探针目标为智能表格（smartsheet），上游原版针对普通表格（sheet）；
# wecom-cli 位于 ~/.npm-global/bin（npm 全局安装），非 /opt/homebrew/bin。
# 配置：../config.json 的 read_docid / read_sheet / write_docid / write_sheet / write_field
export PATH="$HOME/.npm-global/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
DIR="$(cd "$(dirname "$0")/.." && pwd)"
CFG="$DIR/config.json"
[ -f "$CFG" ] || { echo "[PROBE] no config.json"; exit 1; }
CLI=$(command -v wecom-cli || true)
[ -n "$CLI" ] || { echo "[PROBE] wecom-cli not in PATH"; exit 1; }
cfg() { python3 -c "import json;print(json.load(open('$CFG')).get('$1',''))"; }
READ_DOCID=$(cfg read_docid)
READ_SHEET=$(cfg read_sheet)
WRITE_DOCID=$(cfg write_docid)
WRITE_SHEET=$(cfg write_sheet)
WRITE_FIELD=$(cfg write_field)
CRED=~/.config/wecom/credentials.enc
TS=$(date '+%Y-%m-%dT%H:%M:%S%z')
CRED_BEFORE=$(stat -f '%Sm' -t '%Y-%m-%dT%H:%M:%S' "$CRED" 2>/dev/null)
errcode_of() { python3 -c "
import json,sys
try: print(json.loads(sys.stdin.read()).get('errcode','?'))
except Exception: print('parse_fail')" 2>/dev/null; }
READ_ERR=$("$CLI" smartsheet records list --docid "$READ_DOCID" --sheet-id "$READ_SHEET" \
  --type records --limit 1 2>&1 | errcode_of)
PAYLOAD=$(python3 -c "
import json,sys
print(json.dumps({'docid': sys.argv[1], 'sheet_id': sys.argv[2], 'key_type': 'field_title',
  'records': [{'values': {sys.argv[3]: 'keepalive-' + sys.argv[4]}}]}, ensure_ascii=False))" \
  "$WRITE_DOCID" "$WRITE_SHEET" "${WRITE_FIELD:-智能表列}" "$(date +%s)")
WRITE_ERR=$("$CLI" smartsheet records add --json "$PAYLOAD" 2>&1 | errcode_of)
CRED_AFTER=$(stat -f '%Sm' -t '%Y-%m-%dT%H:%M:%S' "$CRED" 2>/dev/null)
REFRESHED="no"; [ "$CRED_BEFORE" != "$CRED_AFTER" ] && REFRESHED="yes"
echo "[PROBE] ts=$TS read_errcode=$READ_ERR write_errcode=$WRITE_ERR cred_refreshed=$REFRESHED"
>>>>>>> Stashed changes
