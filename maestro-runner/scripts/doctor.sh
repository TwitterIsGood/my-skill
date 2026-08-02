#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PLATFORM=${1:-all}
FAILED=0

check_command() {
  label=$1
  command_name=$2
  if command -v "$command_name" >/dev/null 2>&1; then
    printf 'ok      %-18s %s\n' "$label" "$(command -v "$command_name")"
  else
    printf 'missing %-18s %s\n' "$label" "$command_name"
    FAILED=1
  fi
}

"$SCRIPT_DIR/run.sh" --version

case "$PLATFORM" in
  android)
    check_command "Android adb" adb
    if command -v adb >/dev/null 2>&1; then
      adb devices -l
    fi
    ;;
  ios)
    check_command "Xcode xcrun" xcrun
    if command -v xcrun >/dev/null 2>&1; then
      xcrun simctl list devices available
    fi
    ;;
  web)
    if command -v "Google Chrome" >/dev/null 2>&1; then
      check_command "Chrome" "Google Chrome"
    elif [ -x "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" ]; then
      printf 'ok      %-18s %s\n' "Chrome" "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    elif command -v chromium >/dev/null 2>&1; then
      check_command "Chromium" chromium
    elif command -v google-chrome >/dev/null 2>&1; then
      check_command "Chrome" google-chrome
    else
      printf 'missing %-18s %s\n' "Chrome/Chromium" "browser executable"
      FAILED=1
    fi
    ;;
  all)
    check_command "Android adb" adb
    check_command "Xcode xcrun" xcrun
    ;;
  *)
    echo "Usage: $0 [android|ios|web|all]" >&2
    exit 2
    ;;
esac

exit "$FAILED"
