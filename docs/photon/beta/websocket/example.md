> ## Documentation Index
> Fetch the complete documentation index at: https://docs.photon.codes/docs/llms.txt
> Use this file to discover all available pages before exploring further.

> ## Agent Instructions
> Use Stable documentation by default. Honor an explicit Beta request or a URL under /docs/beta/. If the requested version conflicts with the installed CLI package or API origin, clarify the target before writing integration code.
> Pages under /docs/beta/ document Beta; other product pages document Stable. Keep the CLI package, commands, API origin, and credentials within the selected version. State the documentation version in your answer.
> For MCP search, always pass version: Stable or version: Beta. Unfiltered search mixes both versions. For filesystem reads, keep Beta queries under /beta/ and exclude /beta/ from Stable queries; discover paths before reading them.
> The public docs base is https://photon.codes/docs. Convert MCP page paths to public URLs under that base, preserving /beta/ when present. Read https://photon.codes/docs/skill.md for version selection and https://photon.codes/docs/llms.txt for the version indexes.

# Node.js example

> Connect, process events serially, and resume with a saved cursor.

This example keeps a cursor in memory. For restart recovery, load it from durable storage before connecting and persist it after each successful handler.

```ts theme={null}
import { io } from "socket.io-client";

let cursor = 0;
let epoch = 0;
let pending = 0;
let queue = Promise.resolve();
const socket = io(process.env.PHOTON_API_ORIGIN ?? "https://api.photon.codes", {
  path: `/v1/projects/${process.env.PHOTON_PROJECT_ID}/events/ws`,
  addTrailingSlash: false,
  transports: ["websocket"],
  extraHeaders: { Authorization: `Bearer ${process.env.PHOTON_API_KEY}` },
  autoConnect: false,
});

socket.on("connect", () => {
  socket.timeout(10_000).emit("subscribe", { startSeq: cursor }, (error, result) => {
    if (error) socket.io.engine.close();
    else if (!result.ok) console.error(result.error.code);
  });
});
socket.on("disconnect", () => { epoch++; });
socket.on("delivery", (event, { seq }) => {
  const generation = epoch;
  if (++pending > 128) {
    pending--;
    epoch++;
    socket.io.engine.close();
    return;
  }
  queue = queue.then(async () => {
    if (generation !== epoch || seq <= cursor) return;
    await handleEvent(event); // Your idempotent application handler.
    // Persist seq here before advancing the in-memory checkpoint.
    cursor = seq;
  }).catch(error => {
    console.error("Event processing failed", error);
    if (generation === epoch) {
      epoch++;
      socket.io.engine.close();
    }
  }).finally(() => { pending--; });
});
socket.on("delivery_error", error => console.error(error.code));
socket.on("connect_error", error => console.error(error.message));
socket.connect();
```

The queue bounds pending handlers. If it fills, the connection restarts and unprocessed deliveries replay from the saved cursor. Socket.IO owns reconnection; do not add a second retry loop. This example does not send synchronous replies; see [Reply to a webhook event](/docs/beta/websocket/replies).


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.