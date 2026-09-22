#!/bin/bash
# Compatibility entry point. stdout is now one JSON object; failures exit nonzero.
set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
DIR="$(cd "$(dirname "$0")/.." && pwd)"
exec "${PYTHON:-python3}" "$DIR/probe.py" "$@"
