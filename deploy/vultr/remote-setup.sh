#!/usr/bin/env bash
# Runs on the Vultr box as root, from `marco-vultr.sh deploy` after the server code is synced to /opt/marco/server.
# Idempotent: re-run it after every code sync. Inputs: ALLOWED (tailnet logins, comma-separated), MODE (real|stub).
set -euo pipefail
: "${ALLOWED:?set ALLOWED to the tailnet logins that may call the server}"
MODE="${MODE:-real}"
SRV=/opt/marco/server
PY="$SRV/.venv/bin/python"
export UV_PYTHON_INSTALL_DIR=/opt/marco/python      # uv's Python must be readable by the service user, not under /root

step() { printf '\n== %s\n' "$*"; }

step "service user and state"
id marco >/dev/null 2>&1 || useradd --system --home-dir /var/lib/marco --create-home --shell /usr/sbin/nologin marco
install -d -o marco -g marco -m 750 /var/lib/marco /var/lib/marco/data /var/lib/marco/hf
command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin INSTALLER_NO_MODIFY_PATH=1 sh

step "GPU"
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader || { echo "no NVIDIA driver: is this a GPU plan?"; exit 1; }

step "Python 3.12 venv"
[ -x "$PY" ] || uv venv -q --python 3.12 "$SRV/.venv"

cuda_ok() { "$PY" -c "import torch, sys; sys.exit(0 if torch.cuda.is_available() else 1)" 2>/dev/null; }
if [ "$MODE" = real ] && ! cuda_ok; then
  step "PyTorch for this driver's CUDA"
  cuda=$(nvidia-smi | sed -n 's/.*CUDA Version: \([0-9]*\.[0-9]*\).*/\1/p' | head -1)
  echo "driver supports CUDA $cuda"
  picked=""
  for tag in cu130 cu129 cu128 cu126 cu124; do
    v="${tag#cu}"; v="${v:0:2}.${v:2}"
    awk -v have="$cuda" -v want="$v" 'BEGIN { exit !(have + 0 >= want + 0) }' || continue
    if uv pip install -q --python "$PY" --index-url "https://download.pytorch.org/whl/$tag" torch 2>/dev/null && cuda_ok; then
      picked=$tag; break
    fi
  done
  [ -n "$picked" ] || { echo "no PyTorch CUDA build works with driver CUDA $cuda"; exit 1; }
  echo "torch built for $picked"
fi

step "server requirements"
uv pip install -q --python "$PY" -r "$SRV/requirements.txt"

if [ "$MODE" = real ]; then
  step "model weights (once, ~1 GB)"
  sudo -u marco env HF_HOME=/var/lib/marco/hf "$PY" - <<'EOF'
import sys
sys.path.insert(0, "/opt/marco/server")
from transformers import AutoImageProcessor, AutoModel, Owlv2ForObjectDetection, Owlv2Processor
from marco.perception.detector import OwlDetector as D
Owlv2Processor.from_pretrained(D.OWL); Owlv2ForObjectDetection.from_pretrained(D.OWL, use_safetensors=True)
AutoImageProcessor.from_pretrained(D.DINO); AutoModel.from_pretrained(D.DINO, use_safetensors=True)
import torch
print("cached; cuda:", torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else "")
EOF
fi

step "config and service"
install -d -m 755 /etc/marco
cat > /etc/marco/marco.env <<EOF
# Written by deploy/vultr/remote-setup.sh on every deploy. Overrides go in /etc/marco/local.env.
MARCO_MODE=$MODE
MARCO_AUTH=tailscale
TAILSCALE_ALLOWED_LOGINS=$ALLOWED
MARCO_DATA=/var/lib/marco/data
HF_HOME=/var/lib/marco/hf
HF_HUB_OFFLINE=1
HOST=127.0.0.1
PORT=8000
EOF
chown root:marco /etc/marco/marco.env && chmod 640 /etc/marco/marco.env
install -m 644 /opt/marco/deploy/marco.service /etc/systemd/system/marco.service
systemctl daemon-reload
systemctl enable -q marco
systemctl restart marco

step "waiting for the server (models load at start)"
for _ in $(seq 1 90); do
  code=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/v1/items || true)
  [ "$code" != 000 ] && break
  sleep 2
done
# No tailnet identity on a local request, so a correctly closed gate answers 403.
[ "$code" = 403 ] || { echo "expected 403 from the auth gate, got $code"; journalctl -u marco -n 40 --no-pager; exit 1; }
echo "up; the gate refuses unauthenticated calls (403)"

step "publish to the tailnet only"
# Needs MagicDNS + HTTPS certificates on in the tailnet admin console; if not, tailscale prints the link to turn them on.
tailscale serve --bg 8000
echo "server: https://$(tailscale status --json | python3 -c 'import json, sys; print(json.load(sys.stdin)["Self"]["DNSName"].rstrip("."))')"
