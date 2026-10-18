#!/usr/bin/env bash
# Run as root after syncing photon/ and this directory to /opt/marco.
# Installs dependencies and the unit, but does not start it: stop the old bridge
# and transfer its state/cursor first. Credentials remain in /etc/marco/photon.env.
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo 'Run as root.' >&2; exit 1; }
test -s /etc/marco/photon.env
id marco >/dev/null
test -f /opt/marco/photon/package-lock.json

if ! /opt/marco/node/bin/node -e 'process.exit(Number(process.versions.node.split(".")[0]) === 24 ? 0 : 1)' 2>/dev/null; then
  case "$(uname -m)" in
    x86_64) arch=x64 ;;
    aarch64) arch=arm64 ;;
    *) echo 'Unsupported Node architecture.' >&2; exit 1 ;;
  esac
  download=$(mktemp -d)
  trap 'rm -rf "$download"' EXIT
  base=https://nodejs.org/dist/latest-v24.x
  curl --fail --silent --show-error --location "$base/SHASUMS256.txt" -o "$download/SHASUMS256.txt"
  archive=$(awk -v arch="$arch" '$2 ~ ("-linux-" arch "[.]tar[.]xz$") {print $2}' "$download/SHASUMS256.txt")
  [[ "$archive" =~ ^node-v24\.[0-9]+\.[0-9]+-linux-(x64|arm64)\.tar\.xz$ ]]
  curl --fail --silent --show-error --location "$base/$archive" -o "$download/$archive"
  (cd "$download" && awk -v file="$archive" '$2 == file' SHASUMS256.txt | sha256sum --check --status)
  tar -xJf "$download/$archive" -C /opt/marco
  ln -sfn "/opt/marco/${archive%.tar.xz}" /opt/marco/node
fi

export PATH="/opt/marco/node/bin:$PATH"
node --version
npm --version
cd /opt/marco/photon
# tsx is used at runtime; keep the pinned development dependencies installed.
npm ci --include=dev --no-audit --no-fund
npm run typecheck
node --env-file=/etc/marco/photon.env --import tsx --input-type=module -e \
  'import { loadConfig } from "./src/config.ts"; const c=loadConfig(); if(c.mode!=="photon" || !c.caretakerNames.size) process.exit(1); console.log("Bridge environment parses; credentials not printed.");'
install -d -o marco -g marco -m 750 /var/lib/marco-photon
install -m 644 /opt/marco/deploy/marco-photon.service /etc/systemd/system/marco-photon.service
systemd-analyze verify /etc/systemd/system/marco-photon.service
systemctl daemon-reload
echo 'Installed, not started. After the single-bridge handoff: systemctl enable --now marco-photon'
