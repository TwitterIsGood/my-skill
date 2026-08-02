#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if [ -n "${MAESTRO_RUNNER_PROJECT_ROOT:-}" ]; then
  PROJECT_ROOT=$MAESTRO_RUNNER_PROJECT_ROOT
elif command -v git >/dev/null 2>&1 && PROJECT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null); then
  :
else
  PROJECT_ROOT=$(pwd)
fi
TOOL_ROOT="$PROJECT_ROOT/.tools/maestro-runner"
CURRENT_FILE="$TOOL_ROOT/CURRENT"

if [ ! -f "$CURRENT_FILE" ]; then
  echo "maestro-runner is not installed in this project." >&2
  echo "Run: $SCRIPT_DIR/install.sh" >&2
  exit 1
fi

VERSION=$(sed -n '1p' "$CURRENT_FILE")
HOME_DIR="$TOOL_ROOT/versions/$VERSION"
BINARY="$HOME_DIR/bin/maestro-runner"

if [ ! -x "$BINARY" ]; then
  echo "maestro-runner $VERSION is incomplete: $BINARY is missing or not executable." >&2
  echo "Run: $SCRIPT_DIR/install.sh $VERSION" >&2
  exit 1
fi

export MAESTRO_RUNNER_HOME="$HOME_DIR"
exec "$BINARY" "$@"
