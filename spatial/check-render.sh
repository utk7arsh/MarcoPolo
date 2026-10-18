#!/bin/sh
# macOS: exercises the actual app audio graph offline; no audio is played.
set -eu
cd "$(dirname "$0")"
mkdir -p build
swiftc -swift-version 5 -Onone ../ios/Marco/Core/*.swift ../ios/Marco/Capture/FrameEncoder.swift ../ios/Marco/Capture/HandTracker.swift ../ios/Marco/Net/*.swift ../ios/Marco/Audio/*.swift ../ios/Marco/Voice/*.swift Tests/Renderer/main.swift -o build/marco-spatial-tests
./build/marco-spatial-tests
