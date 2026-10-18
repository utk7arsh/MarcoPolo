> ## Documentation Index
> Fetch the complete documentation index at: https://docs.photon.codes/docs/llms.txt
> Use this file to discover all available pages before exploring further.

> ## Agent Instructions
> Use Stable documentation by default. Honor an explicit Beta request or a URL under /docs/beta/. If the requested version conflicts with the installed CLI package or API origin, clarify the target before writing integration code.
> Pages under /docs/beta/ document Beta; other product pages document Stable. Keep the CLI package, commands, API origin, and credentials within the selected version. State the documentation version in your answer.
> For MCP search, always pass version: Stable or version: Beta. Unfiltered search mixes both versions. For filesystem reads, keep Beta queries under /beta/ and exclude /beta/ from Stable queries; discover paths before reading them.
> The public docs base is https://photon.codes/docs. Convert MCP page paths to public URLs under that base, preserving /beta/ when present. Read https://photon.codes/docs/skill.md for version selection and https://photon.codes/docs/llms.txt for the version indexes.

# Receive events

> Handle the public event and its delivery metadata.

Listen for `delivery(event, metadata)`:

```ts theme={null}
socket.on("delivery", (event, { seq, replyExpected }) => {
  // Queue event processing, then checkpoint seq after it succeeds.
});
```

`event` is the same parsed public JSON object you receive from a webhook for the same source occurrence and API version. Its identity, type, data, and extension fields are preserved. Whitespace and property order are not part of this transport’s contract.

`metadata` describes this delivery: `seq` is its replay cursor, and `replyExpected` indicates whether this connection may submit a synchronous reply. Metadata is separate from the event object.

Deliveries have no processing acknowledgement callback. Receipt does not prove your handler completed. Process events in order and save only a successfully handled cursor. A reconnect can redeliver an event; make handling idempotent.


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.