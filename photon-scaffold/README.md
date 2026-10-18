# Photon scaffold: reference wiring for the caretaker bridge

**The team's bridge is [`photon/`](../photon/) (Utkarsh's).** This folder is a small, tested reference that speaks [docs/INTERFACES.md §5](../docs/INTERFACES.md) exactly, against the server as it is today. Use it whole, or lift what you need:
- `src/server.js`: the server client (`getCrop`, `postLabel`, `postItem`) and the `/v1/photon` socket;
- `src/bridge.js`: the reply-matching logic.

Where `photon/` and §5 differ:

| Step | §5 (this scaffold, and the server today) | `photon/` |
|---|---|---|
| The phone asks "what is this?" | the phone sends a `what_is_this` query to the server; the server sends `label_request` to Photon on WebSocket `/v1/photon` | the phone posts the photo to Photon's `/labels/request` |
| The answer goes back | multipart `POST /v1/labels` (`touch_id`, `name`, `text`, `audio`); the server sends `label_ready` to the phone | JSON `POST /labels/reply` (`request_id`, `item`) |
| Registration | `POST /v1/items` (`photo`, `name`) | `POST /items` (also sends `item_id` and `source`) |

Pick one with the team: either `photon/` adopts these routes, or the server adds the other ones.

What this scaffold does, over iMessage with Photon's [iMessage Kit](https://github.com/photon-hq/imessage-kit):

1. **The user touches something unknown and asks "what is this?"** The server sends `label_request` on `/v1/photon`. The bridge texts the caretaker the crop: *"Marco here. What is this? Reply with its name..."*
2. **The caretaker replies "That's the cumin, love".** The bridge posts it to `POST /v1/labels`:
   - name `cumin`;
   - the full reply as the spoken label.
3. **A voice note (before or after the name)** is added as the label audio. When the user touches that jar, they hear the caretaker.
4. **Setup without being asked:** the caretaker sends a photo with a caption ("keys") and the bridge registers it (`POST /v1/items`). A photo without a caption gets "What is it called?" first.

Only the handles in `CARETAKERS` are listened to; everyone else is ignored. Replies answer the oldest open question first.

## Run (on the Mac that is signed in to Messages)
1. Node 22 or later.
2. Give your terminal **Full Disk Access** (System Settings > Privacy & Security). The SDK reads `~/Library/Messages/chat.db`.
3. Install and start:
   ```
   cd photon-scaffold
   npm install
   MARCO_SERVER=https://<server-mac>.<tailnet>.ts.net CARETAKERS=+15551234567 npm start
   ```
4. Connect to the server through the **tailscale serve URL**, even on the server Mac itself, not `127.0.0.1`.
   - The server's fail-closed gate admits only tailnet logins listed in `TAILSCALE_ALLOWED_LOGINS`.
   - A WebSocket close with code 1008 means this login isn't on that list.

## Files
| File | What |
|---|---|
| `src/bridge.js` | all the logic: asking, matching replies to questions, voice notes, setup photos, expiry (pure, tested) |
| `src/server.js` | the server's routes (`getCrop`, `postLabel`, `postItem`) and the `/v1/photon` socket with reconnect |
| `src/main.js` | wiring to iMessage: `sdk.startWatching({ onDirectMessage })` in, `sdk.send({ to, text, attachments })` out |
| `tools/smoke.js` | the server calls without iMessage, against a running server |

## Test
```
cd photon-scaffold && npm test            # node --test, no install needed (the SDK is only loaded by main.js)
cd server && ../poc/.venv/bin/python -m pytest -q tests/test_photon_contract.py
```
The second command:
1. starts a real server on loopback;
2. runs `tools/smoke.js` against it: crop, label, voice note, registration;
3. checks that the phone gets `label_ready` with playable audio.

## To check on the real Mac
- **Voice notes:** iMessage audio arrives as `.caf`. The server stores it as is, and the phone plays it with `AVAudioFile`. Play one on the phone in hour one. If it won't play, convert it on the server with ffmpeg.
- **Attachments that are still downloading:** `main.js` re-reads the message for up to 10 s until `localPath` exists.
