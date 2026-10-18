> ## Documentation Index
> Fetch the complete documentation index at: https://docs.photon.codes/docs/llms.txt
> Use this file to discover all available pages before exploring further.

> ## Agent Instructions
> Use Stable documentation by default. Honor an explicit Beta request or a URL under /docs/beta/. If the requested version conflicts with the installed CLI package or API origin, clarify the target before writing integration code.
> Pages under /docs/beta/ document Beta; other product pages document Stable. Keep the CLI package, commands, API origin, and credentials within the selected version. State the documentation version in your answer.
> For MCP search, always pass version: Stable or version: Beta. Unfiltered search mixes both versions. For filesystem reads, keep Beta queries under /beta/ and exclude /beta/ from Stable queries; discover paths before reading them.
> The public docs base is https://photon.codes/docs. Convert MCP page paths to public URLs under that base, preserving /beta/ when present. Read https://photon.codes/docs/skill.md for version selection and https://photon.codes/docs/llms.txt for the version indexes.

# Reply to a webhook event

> Submit a synchronous response when a delivery expects one.

When `metadata.replyExpected` is true, your connection may emit `reply` with the public `event.id` and an acknowledgement callback. Your credential must have `project:write`.

```ts theme={null}
socket.timeout(5_000).emit("reply", {
  eventId: event.id,
  status: 200,
  headers: { "content-type": "text/plain" },
  body: Buffer.from("accepted").toString("base64"),
}, (error, result) => {
  if (error) console.error("Reply outcome unknown");
  else if (!result.ok) console.error(result.error.code);
});
```

The acknowledgement confirms acceptance for forwarding. It does not confirm downstream processing. A timeout leaves the outcome uncertain; do not assume the reply was rejected.

Reply promptly. The expectation expires at the original request’s deadline and can be used only once. A replayed event may no longer expect a reply. Late, duplicate, and cross-connection replies are rejected without interrupting event delivery.

The body uses standard base64. Omitting `status`, or sending zero, leaves the normal response status unchanged. See the [event reference](/docs/beta/websocket/frames) for the complete reply schema.


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.