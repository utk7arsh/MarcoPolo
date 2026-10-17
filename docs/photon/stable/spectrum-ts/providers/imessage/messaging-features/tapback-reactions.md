##### iMessage tapback reactions

Source: https://photon.codes/docs/spectrum-ts/providers/imessage/messaging-features/tapback-reactions.md
Documentation version: Stable

iMessage converts six universal
`Emoji` aliases into native
tapbacks:

**Emoji**

| Constant | Value |
|---|---|
| `Emoji.love` | `"❤️"` |
| `Emoji.like` | `"👍"` |
| `Emoji.dislike` | `"👎"` |
| `Emoji.laugh` | `"😂"` |
| `Emoji.emphasize` | `"‼️"` |
| `Emoji.question` | `"❓"` |

```ts
import { Emoji } from "spectrum-ts";

await message.react(Emoji.laugh);
```

Other emoji are sent as ordinary emoji reactions when supported. Reactions
require the cloud iMessage package.

See [Reactions and replies](https://photon.codes/docs/spectrum-ts/reactions-and-replies) for the
cross-platform reaction model.


#### Terminal

