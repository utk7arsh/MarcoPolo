#!/usr/bin/env bash
# Marco's server on a Vultr Cloud GPU, private behind Tailscale. Read deploy/vultr/README.md first.
#
#   marco-vultr.sh plans [region]   GPU plans deployable now, with prices (no API key needed)
#   marco-vultr.sh up               create the box: no inbound ports, joins the tailnet at first boot
#   marco-vultr.sh deploy           sync server/ to the box, install, (re)start, publish with `tailscale serve`
#   marco-vultr.sh status           instance, service, GPU, and an authenticated call through the tailnet URL
#   marco-vultr.sh logs             follow the server log
#   marco-vultr.sh bench            per-frame time on the box (tools/bench_frame.py on a synthetic session)
#   marco-vultr.sh ssh              a shell on the box (Tailscale SSH)
#   marco-vultr.sh down             destroy the box (billing stops only on destroy, not on stop)
#
# Env: VULTR_API_KEY, TS_AUTHKEY (up), TAILSCALE_ALLOWED_LOGINS (deploy). Optional: VULTR_REGION (lax),
# VULTR_PLAN (vcg-a40-24c-120g-48vram), VULTR_OS_ID (2284 = Ubuntu 24.04), MARCO_HOST (marco-gpu),
# SSH_PUBKEY (~/.ssh/id_ed25519.pub), MARCO_MODE (real), DIRECT_UDP (0).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
API="https://api.vultr.com/v2"
REGION="${VULTR_REGION:-lax}"
PLAN="${VULTR_PLAN:-vcg-a40-24c-120g-48vram}"
OS_ID="${VULTR_OS_ID:-2284}"
NAME="${MARCO_HOST:-marco-gpu}"
SSH_PUBKEY="${SSH_PUBKEY:-$HOME/.ssh/id_ed25519.pub}"
SSH=(ssh -o BatchMode=no -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new "root@$NAME")

die() { echo "error: $*" >&2; exit 1; }
need() { [ -n "${!1:-}" ] || die "set $1 (see deploy/vultr/README.md)"; }
for tool in curl jq; do command -v "$tool" >/dev/null || die "needs $tool"; done

# Vultr API call; the key goes in through a file descriptor so it never shows up in `ps`.
api() {
  local method=$1 path=$2 out code; shift 2
  out=$(curl -sS -X "$method" "$API$path" -H @<(printf 'Authorization: Bearer %s\n' "$VULTR_API_KEY") \
    -H "Content-Type: application/json" -w '\n%{http_code}' "$@") || { echo "error: can't reach the Vultr API" >&2; return 1; }
  code=${out##*$'\n'}; out=${out%$'\n'*}
  if [ "${code:0:1}" != 2 ]; then
    echo "error: Vultr API $method $path -> HTTP $code: $(jq -r '.error // .' <<<"$out" 2>/dev/null || echo "$out")" >&2
    case "$out" in *"Unauthorized IP"*)
      echo "  Vultr -> Account -> API -> Access Control: allow this IP. Phone hotspots change IP between calls," >&2
      echo "  so for the hackathon use 'Allow all IPv4' (turn it off afterwards)." >&2 ;; esac
    return 1
  fi
  printf '%s' "$out"
}

instance_json() { api GET "/instances?label=$NAME&per_page=100" | jq -c --arg n "$NAME" '[.instances[] | select(.label == $n)][0] // empty'; }

available() {
  { curl -sS "$API/regions/$1/availability?type=vdm"; curl -sS "$API/regions/$1/availability?type=vcg"; } | jq -r '.available_plans[]'
}

cmd_plans() {
  local region="${1:-$REGION}" ids
  ids=$(available "$region")
  [ -n "$ids" ] || { echo "no GPU plans deployable in $region right now"; return; }
  { curl -sS "$API/plans?type=vdm&per_page=500"; curl -sS "$API/plans?type=vcg&per_page=500"; } |
    jq -rs --arg ids "$ids" '($ids | split("\n")) as $want | [.[].plans[] | select(.id as $i | $want | index($i))] | unique_by(.id)[] |
      "\(.id)\t$\(.hourly_cost)/h\t~$\(.hourly_cost * 24 | floor)/day\t\(.vcpu_count) vCPU\t\(.ram / 1024 | floor) GB RAM"' |
    column -t -s $'\t'
}

cmd_up() {
  need VULTR_API_KEY; need TS_AUTHKEY
  api GET /account >/dev/null || exit 1
  [ -f "$SSH_PUBKEY" ] || die "no SSH public key at $SSH_PUBKEY (set SSH_PUBKEY); it is only for Vultr's console fallback"
  local existing
  existing=$(instance_json) || exit 1           # a failed lookup must not read as "no instance yet"
  [ -z "$existing" ] || die "an instance labelled $NAME already exists: use deploy/status, or down first"
  available "$REGION" | grep -qx "$PLAN" || die "$PLAN can't be deployed in $REGION right now. See: $0 plans $REGION"

  local key_id fw_id userdata body id
  key_id=$(api GET "/ssh-keys?per_page=500" | jq -r --arg n "$NAME" '[.ssh_keys[] | select(.name == $n)][0].id // empty')
  [ -n "$key_id" ] || key_id=$(jq -n --arg n "$NAME" --arg k "$(cat "$SSH_PUBKEY")" '{name: $n, ssh_key: $k}' |
    api POST /ssh-keys --data @- | jq -r .ssh_key.id)

  # A firewall group with no inbound rules drops all inbound traffic; Tailscale only needs outbound.
  fw_id=$(api GET "/firewalls?per_page=500" | jq -r --arg n "$NAME" '[.firewall_groups[] | select(.description == $n)][0].id // empty')
  if [ -z "$fw_id" ]; then
    fw_id=$(jq -n --arg n "$NAME" '{description: $n}' | api POST /firewalls --data @- | jq -r .firewall_group.id)
    if [ "${DIRECT_UDP:-0}" = 1 ]; then         # WireGuard only (not the app): lets Tailscale connect directly, not via relay
      jq -n '{ip_type: "v4", protocol: "udp", port: "41641", subnet: "0.0.0.0", subnet_size: 0, notes: "tailscale direct"}' |
        api POST "/firewalls/$fw_id/rules" --data @- >/dev/null
    fi
  fi

  userdata=$(sed -e "s|__TS_AUTHKEY__|$TS_AUTHKEY|" -e "s|__HOST__|$NAME|" "$HERE/cloud-init.yaml" | base64 | tr -d '\n')
  body=$(jq -n --arg region "$REGION" --arg plan "$PLAN" --argjson os "$OS_ID" --arg name "$NAME" --arg key "$key_id" \
    --arg fw "$fw_id" --arg ud "$userdata" \
    '{region: $region, plan: $plan, os_id: $os, label: $name, hostname: $name, sshkey_id: [$key],
      firewall_group_id: $fw, user_data: $ud, backups: "disabled", enable_ipv6: false, tags: ["marco"]}')
  id=$(printf '%s' "$body" | api POST /instances --data @- | jq -r .instance.id)
  echo "created $NAME ($id): $PLAN in $REGION. It bills by the hour until '$0 down'; stopping does not stop billing."

  printf 'waiting for Vultr to boot it'
  for _ in $(seq 1 120); do
    [ "$(api GET "/instances/$id" | jq -r '.instance.status + "/" + .instance.server_status')" = "active/ok" ] && break
    printf '.'; sleep 10
  done
  printf '\nwaiting for it to join the tailnet as %s (cloud-init installs Tailscale)' "$NAME"
  for _ in $(seq 1 60); do
    "${SSH[@]}" -o BatchMode=yes true 2>/dev/null && { echo; echo "on the tailnet. Next: TAILSCALE_ALLOWED_LOGINS=you@x,teammate@y $0 deploy"; return; }
    printf '.'; sleep 10
  done
  echo
  echo "not reachable over Tailscale yet. Check the tailnet admin console for $NAME; if it shows, run '$0 ssh' once"
  echo "(Tailscale SSH may ask you to approve in the browser). Vultr's web console is the fallback."
}

cmd_deploy() {
  need TAILSCALE_ALLOWED_LOGINS
  "${SSH[@]}" "mkdir -p /opt/marco/server /opt/marco/deploy" || die "can't reach root@$NAME over Tailscale. Is this Mac on the tailnet, and did 'up' finish?"
  rsync -az --delete --exclude '.env*' --exclude .venv --exclude data --exclude __pycache__ --exclude .pytest_cache \
    -e "ssh -o StrictHostKeyChecking=accept-new" "$REPO/server/" "root@$NAME:/opt/marco/server/"
  rsync -az -e "ssh -o StrictHostKeyChecking=accept-new" "$HERE/remote-setup.sh" "$HERE/marco.service" "root@$NAME:/opt/marco/deploy/"
  "${SSH[@]}" "ALLOWED='$TAILSCALE_ALLOWED_LOGINS' MODE='${MARCO_MODE:-real}' bash /opt/marco/deploy/remote-setup.sh"
}

cmd_status() {
  if [ -n "${VULTR_API_KEY:-}" ]; then
    instance_json | jq -r '"instance  \(.label) \(.id)\nplan      \(.plan) in \(.region), \(.status)/\(.server_status), since \(.date_created)"'
  fi
  "${SSH[@]}" 'echo "service   $(systemctl is-active marco)"
    nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu --format=csv,noheader | sed "s/^/gpu       /"
    echo "local     unauthenticated /v1/items -> $(curl -s -o /dev/null -w %{http_code} http://127.0.0.1:8000/v1/items) (want 403)"'
  local url
  url="https://$("${SSH[@]}" "tailscale status --json" | jq -r '.Self.DNSName | rtrimstr(".")')"
  echo "url       $url"
  echo "from here $url/v1/items -> $(curl -s -o /dev/null -w '%{http_code}' "$url/v1/items") (want 200 if your login is allowed)"
}

cmd_logs() { "${SSH[@]}" -t journalctl -u marco -f -n 100; }
cmd_ssh() { "${SSH[@]}" -t; }

cmd_bench() {
  # The synthetic session needs poc/'s ARKit emulator, which isn't on the box: make it here, send it over.
  local s="$REPO/server/data/sessions/fake"
  [ -d "$s" ] || die "make the session first: cd server && .venv/bin/python tools/fake_session.py data/sessions/fake"
  "${SSH[@]}" "install -d -o marco -g marco /var/lib/marco/data/sessions"
  rsync -az --delete -e "ssh -o StrictHostKeyChecking=accept-new" "$s/" "root@$NAME:/var/lib/marco/data/sessions/bench/"
  "${SSH[@]}" 'chown -R marco:marco /var/lib/marco/data/sessions/bench && cd /opt/marco/server &&
    sudo -u marco env HF_HOME=/var/lib/marco/hf HF_HUB_OFFLINE=1 \
      .venv/bin/python tools/bench_frame.py /var/lib/marco/data/sessions/bench --items 1 10 20 2>&1 | grep -E "^\{|Error"'
}

cmd_down() {
  need VULTR_API_KEY
  api GET /account >/dev/null || exit 1
  local inst id fw_id key_id
  inst=$(instance_json)
  [ -n "$inst" ] || die "no instance labelled $NAME"
  id=$(jq -r .id <<<"$inst")
  if [ "${1:-}" != "--yes" ]; then
    read -r -p "Destroy $NAME ($id, $(jq -r .plan <<<"$inst"))? Recordings on it are lost. Type the name to confirm: " ans
    [ "$ans" = "$NAME" ] || die "not confirmed"
  fi
  "${SSH[@]}" -o BatchMode=yes 'tailscale serve reset; tailscale logout' 2>/dev/null || echo "(couldn't log it out of the tailnet; remove $NAME in the admin console)"
  api DELETE "/instances/$id" >/dev/null
  echo "destroyed $id; billing stopped"
  fw_id=$(api GET "/firewalls?per_page=500" | jq -r --arg n "$NAME" '[.firewall_groups[] | select(.description == $n)][0].id // empty')
  key_id=$(api GET "/ssh-keys?per_page=500" | jq -r --arg n "$NAME" '[.ssh_keys[] | select(.name == $n)][0].id // empty')
  for _ in 1 2 3 4 5 6; do                      # the firewall group frees up a little after the instance goes
    [ -z "$fw_id" ] && break
    api DELETE "/firewalls/$fw_id" >/dev/null 2>&1 && fw_id="" || sleep 10
  done
  [ -z "$fw_id" ] || echo "firewall group $NAME still attached; delete it later in the Vultr console"
  [ -z "$key_id" ] || api DELETE "/ssh-keys/$key_id" >/dev/null
}

case "${1:-}" in
  plans) shift; cmd_plans "$@" ;;
  up) cmd_up ;;
  deploy) cmd_deploy ;;
  status) cmd_status ;;
  logs) cmd_logs ;;
  ssh) cmd_ssh ;;
  bench) cmd_bench ;;
  down) shift; cmd_down "$@" ;;
  *) sed -n '2,17p' "$0" | sed 's/^# \{0,1\}//'; exit 1 ;;
esac
