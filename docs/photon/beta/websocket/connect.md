> ## Documentation Index
> Fetch the complete documentation index at: https://docs.photon.codes/docs/llms.txt
> Use this file to discover all available pages before exploring further.

> ## Agent Instructions
> Use Stable documentation by default. Honor an explicit Beta request or a URL under /docs/beta/. If the requested version conflicts with the installed CLI package or API origin, clarify the target before writing integration code.
> Pages under /docs/beta/ document Beta; other product pages document Stable. Keep the CLI package, commands, API origin, and credentials within the selected version. State the documentation version in your answer.
> For MCP search, always pass version: Stable or version: Beta. Unfiltered search mixes both versions. For filesystem reads, keep Beta queries under /beta/ and exclude /beta/ from Stable queries; discover paths before reading them.
> The public docs base is https://photon.codes/docs. Convert MCP page paths to public URLs under that base, preserving /beta/ when present. Read https://photon.codes/docs/skill.md for version selection and https://photon.codes/docs/llms.txt for the version indexes.

# Connect

> Authenticate and open your project’s Socket.IO connection.

Install `socket.io-client` and connect to your API origin. Set the transport path separately from the namespace:

```ts theme={null}
import { io } from "socket.io-client";

const socket = io("https://api.photon.codes", {
  path: `/v1/projects/${projectId}/events/ws`,
  addTrailingSlash: false,
  transports: ["websocket"],
  extraHeaders: { Authorization: `Bearer ${apiKey}` },
  autoConnect: false,
});
```

Register your listeners before calling `socket.connect()`. Use the default namespace; the project path is the `path` option, not a namespace URL.

The endpoint accepts the path with or without a trailing slash. You can omit `addTrailingSlash: false` to use the Socket.IO client's default trailing slash.

Your credential needs `project:read` for the selected project. Replies additionally require `project:write`. A browser cannot supply this authorization header on a websocket-only connection; the public integration targets Node.js and other clients that support handshake headers. Direct connections from customer browser applications are not supported.

Polling and Socket.IO session recovery are disabled. See [Start a session](/docs/beta/websocket/session) for subscription setup and [Errors and reconnection](/docs/beta/websocket/errors) for reconnect behavior.


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.