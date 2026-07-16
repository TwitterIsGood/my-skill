#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SUITE_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
export PYTHONPATH="$SUITE_ROOT${PYTHONPATH:+:$PYTHONPATH}"
exec python3 -m ui_pipeline sprites "$@"
