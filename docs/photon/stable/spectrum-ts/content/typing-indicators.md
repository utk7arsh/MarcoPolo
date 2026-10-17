#### Typing indicators

Source: https://photon.codes/docs/spectrum-ts/content/typing-indicators.md
Documentation version: Stable

Use `typing()` to send a typing indicator signal through the content pipeline. The default action is `"start"`.

```ts
import { typing } from "spectrum-ts";

await space.send(typing());        // start typing
await space.send(typing("stop"));  // stop typing
```

`space.startTyping()`, `space.stopTyping()`, and `space.responding(fn)` are sugar over `space.send(typing(...))`.

Platforms without a typing-indicator API silently no-op.


