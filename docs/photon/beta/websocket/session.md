> ## Documentation Index
> Fetch the complete documentation index at: https://docs.photon.codes/docs/llms.txt
> Use this file to discover all available pages before exploring further.

> ## Agent Instructions
> Use Stable documentation by default. Honor an explicit Beta request or a URL under /docs/beta/. If the requested version conflicts with the installed CLI package or API origin, clarify the target before writing integration code.
> Pages under /docs/beta/ document Beta; other product pages document Stable. Keep the CLI package, commands, API origin, and credentials within the selected version. State the documentation version in your answer.
> For MCP search, always pass version: Stable or version: Beta. Unfiltered search mixes both versions. For filesystem reads, keep Beta queries under /beta/ and exclude /beta/ from Stable queries; discover paths before reading them.
> The public docs base is https://photon.codes/docs. Convert MCP page paths to public URLs under that base, preserving /beta/ when present. Read https://photon.codes/docs/skill.md for version selection and https://photon.codes/docs/llms.txt for the version indexes.

# Start a session

> Subscribe once on each connection and read the accepted limits.

On every `connect`, emit `subscribe` with your saved `startSeq` and an acknowledgement callback. A successful acknowledgement arrives before deliveries and includes the selected project, API version, connection ID, accepted cursor, and limits.

Include `apiVersion` to pin a selectable customer contract date, or omit it to use
the service default. Use the date returned by the acknowledgement when interpreting
projected events. Resend your chosen date on every reconnect. An unavailable date
returns `frame_invalid`; correct it and subscribe again before the connection's
subscription deadline. Already-public events retain their original envelope.

```ts theme={null}
socket.on("connect", () => {
  socket.timeout(10_000).emit("subscribe", { startSeq: savedCursor, apiVersion: "2026-07-01" }, (error, result) => {
    if (error) { socket.io.engine.close(); return; }
    if (!result.ok) { console.error(result.error.code); return; }
    console.info("Subscribed", result.connectionId, result.apiVersion);
  });
});
```

Send one subscription per connection. A repeated subscription is rejected while the existing stream continues. Subscribe promptly; an idle connection that never subscribes is closed.

Read `limits.maxFrameBytes` and `limits.maxReplyBodyBytes` from the acknowledgement. Size reply payloads against these limits. Socket.IO manages heartbeat timing internally.

The connection ID is assigned by Socket.IO and changes after reconnection. Use it to correlate delivery diagnostics. See [Cursors and replay](/docs/beta/websocket/cursors) before saving a cursor.


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.