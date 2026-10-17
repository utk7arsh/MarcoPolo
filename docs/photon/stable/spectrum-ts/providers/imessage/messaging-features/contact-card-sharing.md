##### Native iMessage contact card sharing

Source: https://photon.codes/docs/spectrum-ts/providers/imessage/messaging-features/contact-card-sharing.md
Documentation version: Stable

Share the bot account's own iMessage contact card directly in a chat. Use
`nativeContactCard()` to build the content, or the `space.shareContactCard()`
sugar method on a narrowed iMessage space:

**Sugar (space.shareContactCard)**

```ts
import { imessage } from "spectrum-ts/providers/imessage";

const im = imessage(space);
await im.shareContactCard();
```

**Canonical (space.send)**

```ts
import { nativeContactCard } from "spectrum-ts/providers/imessage";

await space.send(nativeContactCard());
```

This shares the bot's own contact card as it appears in iMessage. Recipients
can tap it to save the contact. Use it in onboarding flows where you want users
to add your bot to their contacts.

  Native contact card sharing requires `@spectrum-ts/imessage`. With
  `@spectrum-ts/imessage-local`, `nativeContactCard()` throws an
  `UnsupportedError`.


