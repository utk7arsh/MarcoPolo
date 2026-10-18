> ## Documentation Index
> Fetch the complete documentation index at: https://docs.photon.codes/docs/llms.txt
> Use this file to discover all available pages before exploring further.

> ## Agent Instructions
> Use Stable documentation by default. Honor an explicit Beta request or a URL under /docs/beta/. If the requested version conflicts with the installed CLI package or API origin, clarify the target before writing integration code.
> Pages under /docs/beta/ document Beta; other product pages document Stable. Keep the CLI package, commands, API origin, and credentials within the selected version. State the documentation version in your answer.
> For MCP search, always pass version: Stable or version: Beta. Unfiltered search mixes both versions. For filesystem reads, keep Beta queries under /beta/ and exclude /beta/ from Stable queries; discover paths before reading them.
> The public docs base is https://photon.codes/docs. Convert MCP page paths to public URLs under that base, preserving /beta/ when present. Read https://photon.codes/docs/skill.md for version selection and https://photon.codes/docs/llms.txt for the version indexes.

# Event delivery over Socket.IO

> Receive your project events with cursor-based replay.

Receive the same public event objects delivered by webhooks over a persistent Socket.IO connection. Each connection subscribes to one project.

Use `socket.io-client` in Node.js. Socket.IO supplies heartbeat detection and automatic reconnection. Subscribe again after every connection, using your last successfully processed cursor.

Start with [Connect](/docs/beta/websocket/connect), then read [Cursors and replay](/docs/beta/websocket/cursors). The [event reference](/docs/beta/websocket/frames) is generated from the runtime definitions.


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.