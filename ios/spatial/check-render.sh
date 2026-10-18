#!/bin/sh
# macOS: exercises the actual app audio graph offline; no audio is played.
set -eu
cd "$(dirname "$0")"
mkdir -p build
swiftc -swift-version 5 -Onone ../Marco/Core/*.swift ../Marco/Capture/FrameEncoder.swift ../Marco/Capture/HandTracker.swift ../Marco/Net/*.swift ../Marco/Audio/*.swift ../Marco/Voice/*.swift Tests/Renderer/main.swift -o build/marco-spatial-tests
./build/marco-spatial-tests
