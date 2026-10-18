#!/bin/sh
# Run after check-airpods.sh --build-only. Neither accepted command plays audio.
set -eu
cd "$(dirname "$0")"
check_withdrawn() {
    if option_message=$("$@" --guidance 2>&1); then
        echo 'FAIL: withdrawn guidance option returned success' >&2
        exit 1
    else
        option_status=$?
    fi
    [ "$option_status" -eq 2 ] || { echo "$option_message" >&2; exit 1; }
    case "$option_message" in
        *withdrawn*) ;;
        *) echo 'FAIL: missing withdrawn-mode explanation' >&2; exit 1 ;;
    esac
}
check_withdrawn sh ./check-airpods.sh
check_withdrawn ./build/MarcoAirPodsCheck.app/Contents/MacOS/MarcoAirPodsCheck
echo '2 withdrawn-mode checks passed'
