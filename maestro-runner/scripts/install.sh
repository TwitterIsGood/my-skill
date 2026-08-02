#!/bin/sh
set -eu

VERSION=${1:-1.1.22}
VERSION=${VERSION#v}
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if [ -n "${MAESTRO_RUNNER_PROJECT_ROOT:-}" ]; then
  PROJECT_ROOT=$MAESTRO_RUNNER_PROJECT_ROOT
elif command -v git >/dev/null 2>&1 && PROJECT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null); then
  :
else
  PROJECT_ROOT=$(pwd)
fi
TOOL_ROOT="$PROJECT_ROOT/.tools/maestro-runner"
INSTALL_DIR="$TOOL_ROOT/versions/$VERSION"
BINARY="$INSTALL_DIR/bin/maestro-runner"

if [ -x "$BINARY" ] && "$BINARY" --version 2>/dev/null | grep -q "maestro-runner $VERSION"; then
  mkdir -p "$TOOL_ROOT"
  printf '%s\n' "$VERSION" > "$TOOL_ROOT/CURRENT"
  echo "maestro-runner $VERSION is already installed at $INSTALL_DIR"
  exit 0
fi

command -v curl >/dev/null 2>&1 || { echo "curl is required" >&2; exit 1; }
command -v tar >/dev/null 2>&1 || { echo "tar is required" >&2; exit 1; }

case "$(uname -s)" in
  Darwin) OS=darwin ;;
  Linux) OS=linux ;;
  *) echo "Unsupported OS: $(uname -s)" >&2; exit 1 ;;
esac

case "$(uname -m)" in
  arm64|aarch64) ARCH=arm64 ;;
  x86_64|amd64) ARCH=amd64 ;;
  *) echo "Unsupported architecture: $(uname -m)" >&2; exit 1 ;;
esac

ARCHIVE="maestro-runner-$VERSION-$OS-$ARCH.tar.gz"
BASE_URL="https://open.devicelab.dev/download/maestro-runner/$VERSION"
TMP_DIR=$(mktemp -d "${TMPDIR:-/tmp}/maestro-runner-install.XXXXXX")
trap 'rm -rf "$TMP_DIR"' EXIT INT TERM

echo "Downloading maestro-runner $VERSION for $OS/$ARCH..."
if curl --fail --location --silent --show-error --max-time 300 \
  "$BASE_URL/$ARCHIVE" -o "$TMP_DIR/$ARCHIVE"; then
  if curl --fail --location --silent --show-error --max-time 30 \
    "$BASE_URL/$ARCHIVE.sha256" -o "$TMP_DIR/$ARCHIVE.sha256"; then
    EXPECTED=$(awk '{print $1}' "$TMP_DIR/$ARCHIVE.sha256")
    if command -v sha256sum >/dev/null 2>&1; then
      ACTUAL=$(sha256sum "$TMP_DIR/$ARCHIVE" | awk '{print $1}')
    else
      ACTUAL=$(shasum -a 256 "$TMP_DIR/$ARCHIVE" | awk '{print $1}')
    fi
    [ "$EXPECTED" = "$ACTUAL" ] || { echo "Checksum verification failed" >&2; exit 1; }
  fi

  mkdir -p "$TMP_DIR/extract" "$INSTALL_DIR"
  tar -xzf "$TMP_DIR/$ARCHIVE" -C "$TMP_DIR/extract"
  if [ -d "$TMP_DIR/extract/maestro-runner" ]; then
    cp -R "$TMP_DIR/extract/maestro-runner/." "$INSTALL_DIR/"
  else
    cp -R "$TMP_DIR/extract/." "$INSTALL_DIR/"
  fi
  if [ -f "$INSTALL_DIR/maestro-runner" ]; then
    mkdir -p "$INSTALL_DIR/bin"
    mv "$INSTALL_DIR/maestro-runner" "$BINARY"
  fi
else
  command -v git >/dev/null 2>&1 || { echo "Download failed and git is unavailable" >&2; exit 1; }
  command -v go >/dev/null 2>&1 || { echo "Download failed and Go is unavailable" >&2; exit 1; }
  echo "Release download failed; building v$VERSION from source..."
  git clone --depth 1 --branch "v$VERSION" https://github.com/devicelab-dev/maestro-runner.git "$TMP_DIR/source"
  mkdir -p "$INSTALL_DIR/bin"
  COMMIT=$(git -C "$TMP_DIR/source" rev-parse --short HEAD)
  BUILD_DATE=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
  (
    cd "$TMP_DIR/source"
    CGO_ENABLED=0 go build \
      -ldflags "-s -w -X github.com/devicelab-dev/maestro-runner/pkg/cli.Version=$VERSION -X github.com/devicelab-dev/maestro-runner/pkg/cli.Commit=$COMMIT -X github.com/devicelab-dev/maestro-runner/pkg/cli.BuildDate=$BUILD_DATE" \
      -o "$BINARY" .
  )
  cp -R "$TMP_DIR/source/drivers" "$INSTALL_DIR/drivers"
fi

chmod +x "$BINARY"
mkdir -p "$TOOL_ROOT"
printf '%s\n' "$VERSION" > "$TOOL_ROOT/CURRENT"
printf '%s\n' "https://github.com/devicelab-dev/maestro-runner/releases/tag/v$VERSION" > "$INSTALL_DIR/SOURCE"

MAESTRO_RUNNER_HOME="$INSTALL_DIR" "$BINARY" --version
echo "Installed project-local maestro-runner at $INSTALL_DIR"
