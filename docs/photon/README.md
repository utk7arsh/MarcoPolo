# Photon docs (local copy)

Pulled from https://photon.codes/docs/llms-full.txt on 2026-10-17 and split into one Markdown file per page under `stable/`. `INDEX-llms.txt` is the full page index, covering both Stable and Beta.

## Which Photon

We use **Stable: Spectrum** (`spectrum-ts`). Photon also documents a **Beta (2.0)** platform: `api.photon.codes/v1`, with Python, TS, Rust and Go clients and HTTP `listMessages`/`sendMessage`. We do not use it, because:

- the LA Hacks prize requires "integrate with Spectrum";
- the HACKWITHPHOTON promo is for Spectrum Pro;
- the Beta messaging docs say "being rewritten from the ground up".

Do not mix the two: packages, hosts and credentials differ.

## Read these first

| Page | Why |
|---|---|
| `stable/spectrum-ts/messages.md` | Inbound content types, including `voice`, `group` and `reply` |
| `stable/spectrum-ts/spaces-and-users.md` | `space.send`, `space.get`, typing |
| `stable/spectrum-ts/reactions-and-replies.md` | Tapbacks and threaded replies |
| `stable/spectrum-ts/content/read.md` | Inbound read receipts (the "Mom is looking at it" signal) |
| `stable/spectrum-ts/providers/imessage/connection-and-routing.md` | Shared vs dedicated lines, quotas, `space.get(chatGuid)` |
| `stable/spectrum-ts/troubleshooting/imessage.md` | "Target not allowed for this project", handle mismatch, the debug line |
| `stable/best-practices/imessage-deliverability.md` | What gets a line flagged by Apple |
| `stable/spectrum-ts/providers/terminal/*.md` | Local dev without credentials |

## Changes since the Oct 13 deep dive (`notes/research/photon-spectrum-dd.md`)

Verified against the docs and the `spectrum-ts` 12.11.0 source:

- **12.11.0** shipped Oct 15.
- **Voice memos** now arrive as `voice` content (`audio/x-caf`, with `read()`), not as a generic attachment.
- **Bytes come straight off inbound content.** `content.read()` returns them, so `getAttachment` is not needed.
- **Swipe-replies** arrive on the SDK stream as `reply` content whose `target` is the message we sent. This is what lets an answer route to the exact photo it belongs to.
- **A photo with a caption** in one iMessage arrives as `group` content.
- **Signal handlers.** Since 12.10, Spectrum no longer installs SIGINT/SIGTERM handlers, so the app calls `app.stop()` itself.
- **Local iMessage** moved to its own package, `@spectrum-ts/imessage-local`.
- **The Beta docs say it outright:** "a shared line cannot send an unsolicited first message". The caretaker texts first.
