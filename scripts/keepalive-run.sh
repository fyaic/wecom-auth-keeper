#!/bin/bash
# Compatibility entry point for existing launchd installations.
set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
DIR="$(cd "$(dirname "$0")/.." && pwd)"
exec "${PYTHON:-python3}" "$DIR/keepalive.py" "$@"
