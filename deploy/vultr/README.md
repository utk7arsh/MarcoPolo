# Marco server on a Vultr Cloud GPU

This runs `server/` (the `docs/INTERFACES.md` server) with `MARCO_MODE=real` on a Vultr GPU box. The box is private: the phone, the Photon bridge and the dashboard reach it at `https://marco-gpu.<tailnet>.ts.net` over Tailscale, exactly as they would reach the venue Mac.

```
iPhone / Photon / dashboard ──tailnet (WireGuard)──► marco-gpu
                                                     tailscale serve :443 ──► 127.0.0.1:8000  python -m marco.app
                                                     (adds Tailscale-User-Login; the gate checks TAILSCALE_ALLOWED_LOGINS)
Vultr firewall group: no inbound rules. SSH is Tailscale SSH. Nothing listens on the public IP.
```

## Pick a plan

GPU plans that could actually be deployed on 2026-10-17. Re-check with `./marco-vultr.sh plans lax` (no key needed):

| Plan | Region | $/h | ~$/day |
|---|---|---|---|
| `vcg-a40-24c-120g-48vram` (A40, 48 GB) | `lax` Los Angeles | 1.712 | 41 |
| `vcg-a16-6c-60g-16vram` (A16, 16 GB) | `sjc` San Jose | 0.471 | 11 |

- **The model is small:** OWLv2 base at fp16 plus DINOv2-small use about 1.5 GB of VRAM, so either plan is plenty.
- **LA vs San Jose:** `sjc` adds roughly 10 ms per round trip over `lax`. A frame takes about 400 ms on the Mac, so that is noise.
- **No fractional GPU plans:** Vultr's public plan list has none any more.
- **Stopping doesn't stop billing.** Billing stops only when the instance is destroyed (`./marco-vultr.sh down`), with a one-hour minimum.

To deploy the A16 instead: `export VULTR_REGION=sjc VULTR_PLAN=vcg-a16-6c-60g-16vram`.

## One-time setup

1. **Vultr API key:**
   - Go to Account → API → Enable API, and copy the key.
   - Under Access Control, allow your current IP. Calls from an IP that isn't listed are refused.
   - Apply the MLH credit under Billing → Gift Code before you deploy. Vultr allows one code per account.
2. **Tailscale (admin console, once per tailnet):**
   - DNS: turn on **MagicDNS** and **HTTPS Certificates**.
   - Settings → Keys → **Generate auth key**. Make it **not reusable**, **pre-approved** and **not ephemeral**, with a 1-day expiry.
     - The key travels in the instance's first-boot data. A one-off key is spent the moment the box joins, so it is useless afterwards.
   - Every device that talks to the server joins this tailnet: the iPhone (Tailscale app), the Mac that runs Photon, the dashboard machine, and this Mac.
3. **On this Mac:** `jq`, `rsync` and an SSH key (`~/.ssh/id_ed25519.pub`, used only for Vultr's console fallback). Tailscale must be running.

Keys stay in your shell, never in a file in this repo:
```bash
export VULTR_API_KEY=...            # Vultr → Account → API
export TS_AUTHKEY=tskey-auth-...    # the one-off key from step 2
export TAILSCALE_ALLOWED_LOGINS=utkarshlal@gmail.com,vedant@...   # tailnet logins allowed to call the server
```

## Run it

```bash
cd deploy/vultr
./marco-vultr.sh up        # ~5-10 min: creates the box, waits for boot, waits for it to join the tailnet
./marco-vultr.sh deploy    # syncs server/, installs CUDA PyTorch + requirements, caches weights, starts, publishes
./marco-vultr.sh status    # service, GPU, the gate (local call must be 403), your call through the tailnet URL (200)
./marco-vultr.sh bench     # per-frame time on the GPU with 1, 10 and 20 items (budget: 1 s)
```

`deploy` prints the server URL, `https://marco-gpu.<tailnet>.ts.net`. Point everything at it:
- **iPhone:** the Server field in the app.
- **Photon bridge:** `MARCO_SERVER_URL`.
- **Dashboard and tools:** e.g. `python server/tools/replay.py <session> --server https://marco-gpu.<tailnet>.ts.net`.

| When | Command |
|---|---|
| Server code changed | `./marco-vultr.sh deploy` (it syncs your working tree, committed or not) |
| Something's wrong | `./marco-vultr.sh logs`, or `./marco-vultr.sh ssh` |
| Refit thresholds | `./marco-vultr.sh ssh`, then add `TH_PHOTO_NAME=...` lines to `/etc/marco/local.env` and run `systemctl restart marco` |
| Done for the day / after judging | `./marco-vultr.sh down` |

## What `deploy` sets up on the box

- **The service:** `marco.service` runs `python -m marco.app` as an unprivileged `marco` user.
  - The code in `/opt/marco/server` is read-only to it.
  - Recordings and model weights live in `/var/lib/marco`.
- **The config:** `/etc/marco/marco.env`, rewritten on every deploy. It holds `MARCO_MODE=real`, `MARCO_AUTH=tailscale`, your allow-list and loopback `HOST`.
  - It also sets `HF_HUB_OFFLINE=1`, so a restart never waits on Hugging Face.
  - Your own overrides go in `/etc/marco/local.env`.
- **PyTorch:** a CUDA build matched to the driver that `nvidia-smi` reports. Vultr's GPU images ship the NVIDIA driver and CUDA.
  - **Don't install your own NVIDIA driver:** the A16 and A40 are vGPUs, and the host manages their driver.
- **The gate check:** `deploy` checks that an unauthenticated local request gets 403 before it publishes anything with `tailscale serve`.

## Troubleshooting

- **"can't be deployed in lax right now":** run `./marco-vultr.sh plans lax`, or switch to `sjc` (see above).
- **`up` creates the box but it never joins the tailnet:**
  - Open the Vultr web console for the instance and read `/var/log/cloud-init-output.log`.
  - The usual cause is an expired or already-used auth key. Fix: `./marco-vultr.sh down`, make a new key, then `up` again.
- **Tailscale SSH asks you to approve in the browser:** that's its "check" mode. Approve once, then re-run the command.
- **Laggy round trips:** run `tailscale ping marco-gpu` from the phone's network.
  - If it says "via DERP" (a relay), destroy and re-create with `DIRECT_UDP=1`.
  - That opens UDP 41641 for WireGuard only, never the app.
- **`deploy` says no PyTorch CUDA build works:** paste the `nvidia-smi` output into the team chat. The driver's CUDA version decides which wheel can load.

## Security rules this follows (repo `CLAUDE.md` §4)

- The app binds 127.0.0.1.
- Every route goes through `server/marco/auth.py`, with the Tailscale allow-list.
- The tailnet sees the app only through `tailscale serve`. Never `tailscale funnel`, and no public or cloud port.
- No keys are written to the repo:
  - the Vultr key is read from the environment;
  - the Tailscale key is a one-off.
