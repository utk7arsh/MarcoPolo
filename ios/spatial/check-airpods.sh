#!/bin/sh
# macOS only. --listen: original tour; --front-back: tracked voice/beacon retest;
# --simulate-approach: scripted body approach/reach, NOT real navigation.
# Otherwise checks motion for 12 seconds. --build-only compiles without launching.
set -eu
cd "$(dirname "$0")"
if [ "${1:-}" = "--guidance" ]; then
    echo 'The automatic --guidance demo was withdrawn after wearer feedback. Use --front-back for a stationary listening test; real walking needs the iPhone. Scripted playback is explicitly --simulate-approach.' >&2
    exit 2
fi
APP="build/MarcoAirPodsCheck.app"
mkdir -p "$APP/Contents/MacOS"
cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleIdentifier</key><string>dev.marcopolo.airpodscheck</string>
<key>CFBundleName</key><string>Marco AirPods Check</string>
<key>CFBundleExecutable</key><string>MarcoAirPodsCheck</string>
<key>CFBundlePackageType</key><string>APPL</string>
<key>NSMotionUsageDescription</key><string>Verify headphone head tracking for Marco Polo spatial guidance.</string>
</dict></plist>
PLIST
swiftc -swift-version 5 -Onone ../ios/Marco/Core/*.swift ../ios/Marco/Capture/FrameEncoder.swift ../ios/Marco/Capture/HandTracker.swift ../ios/Marco/Net/*.swift ../ios/Marco/Audio/*.swift ../ios/Marco/Voice/*.swift Tools/SpatialAudioCheck/*.swift -Xlinker -sectcreate -Xlinker __TEXT -Xlinker __info_plist -Xlinker "$APP/Contents/Info.plist" -o "$APP/Contents/MacOS/MarcoAirPodsCheck"
codesign --force --sign - "$APP" >/dev/null 2>&1
if [ "${1:-}" = "--build-only" ]; then exit 0; fi
# LaunchServices gives the motion permission request the helper's own app identity.
LOG="$(mktemp -t marco-airpods-check)"
trap 'rm -f "$LOG"' EXIT
open -n -W --stdout "$LOG" --stderr "$LOG" "$APP" --args "$@"
cat "$LOG"
# LaunchServices itself can exit successfully even if the helper rejects the route.
# Require the helper's completion record rather than treating open's exit as a pass.
awk '/^Motion samples: / || /^GUIDANCE DEMO completed=true/ { completed = 1 } END { exit !completed }' "$LOG"
