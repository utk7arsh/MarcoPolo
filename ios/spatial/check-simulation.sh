#!/bin/sh
set -eu
cd "$(dirname "$0")"
mkdir -p build
swiftc -swift-version 5 -Onone ../Marco/Core/*.swift Tools/SpatialAudioCheck/GuidanceDemo.swift ../Marco/Audio/*.swift Tests/Simulation/main.swift -o build/marco-guidance-demo-tests
./build/marco-guidance-demo-tests
