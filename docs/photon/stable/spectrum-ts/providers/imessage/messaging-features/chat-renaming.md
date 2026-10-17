##### iMessage chat renaming

Source: https://photon.codes/docs/spectrum-ts/providers/imessage/messaging-features/chat-renaming.md
Documentation version: Stable

Rename a group chat using `space.rename()` or the canonical `rename()` content
builder:

```ts
import { rename } from "spectrum-ts";

// Sugar
await space.rename("Book Club");

// Canonical
await space.send(rename("Book Club"));
```

Renaming requires `@spectrum-ts/imessage` and only works on group chats. With
`@spectrum-ts/imessage-local`, or on a DM, `rename()` throws an
`UnsupportedError`.


