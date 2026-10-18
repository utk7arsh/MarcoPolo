#!/bin/sh
# Type-checks every Swift file that builds on macOS (no Xcode or iOS SDK needed) and runs the core tests.
#   sh ios/check.sh                 unit tests
#   sh ios/check.sh --emit DIR      also write what the app sends, for server/tests/test_ios_contract.py
# The ARKit/UIKit files (App/, Capture/ARSessionManager.swift) only build in Xcode.
set -e
cd "$(dirname "$0")"
PORTABLE="Marco/Core/*.swift Marco/Capture/FrameEncoder.swift Marco/Capture/HandTracker.swift Marco/Net/*.swift Marco/Audio/*.swift Marco/Voice/*.swift"
mkdir -p build
# shellcheck disable=SC2086
swiftc -swift-version 5 -typecheck $PORTABLE
# shellcheck disable=SC2086
swiftc -swift-version 5 -Onone $PORTABLE Tests/main.swift -o build/marco-core-tests
./build/marco-core-tests "$@"
