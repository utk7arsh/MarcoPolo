##### iMessage group avatars

Source: https://photon.codes/docs/spectrum-ts/providers/imessage/messaging-features/group-avatars.md
Documentation version: Stable

Set or clear the group chat icon using `space.avatar()` or the canonical
`avatar()` content builder:

```ts
import { avatar } from "spectrum-ts";

// Sugar - set from a file path
await space.avatar("./icon.png");

// Sugar - clear the current avatar
await space.avatar("clear");

// Canonical
await space.send(avatar("./icon.png"));
```

Read the current icon back with `space.getAvatar()`. It resolves to
`AvatarData` or
`undefined` when the group has no icon. The result round-trips into the setter:

```ts
const icon = await space.getAvatar();
if (icon) {
  await otherGroup.avatar(icon.data, { mimeType: icon.mimeType });
}
```

Group avatars require `@spectrum-ts/imessage` and only work on group chats.
With `@spectrum-ts/imessage-local`, or on a DM, `avatar()` and `getAvatar()`
throw an `UnsupportedError`.


