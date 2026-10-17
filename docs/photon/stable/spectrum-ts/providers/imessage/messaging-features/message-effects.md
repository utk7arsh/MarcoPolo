##### iMessage message effects

Source: https://photon.codes/docs/spectrum-ts/providers/imessage/messaging-features/message-effects.md
Documentation version: Stable

iMessage supports bubble effects, which animate the sent message bubble, and
screen effects, which play a full-screen animation on receive. Wrap any
content with `effect()`:

```ts
import { attachment } from "spectrum-ts";
import { effect, imessage } from "spectrum-ts/providers/imessage";

await space.send(effect("Happy birthday!", imessage.effect.message.celebration));
await space.send(
  effect(
    attachment("/path/to/photo.jpg"),
    imessage.effect.message.confetti
  )
);
```

The wrapped content can be a string, `markdown(...)`, or any
`attachment(...)`. Effects only apply on iMessage. Other platforms see the
inner content unchanged.

  Sending effects requires the cloud `@spectrum-ts/imessage` package. The local
  package exports the helper for API consistency but rejects effect sends with
  an `UnsupportedError`.

**Bubble effects** — Animate the sent message bubble.

| Constant | Value |
|---|---|
| `imessage.effect.message.slam` | `"com.apple.MobileSMS.expressivesend.impact"` |
| `imessage.effect.message.loud` | `"com.apple.MobileSMS.expressivesend.loud"` |
| `imessage.effect.message.gentle` | `"com.apple.MobileSMS.expressivesend.gentle"` |
| `imessage.effect.message.invisible` | `"com.apple.MobileSMS.expressivesend.invisibleink"` |

**Screen effects** — Play a full-screen animation on the recipient

| Constant | Value |
|---|---|
| `imessage.effect.message.confetti` | `"com.apple.messages.effect.CKConfettiEffect"` |
| `imessage.effect.message.fireworks` | `"com.apple.messages.effect.CKFireworksEffect"` |
| `imessage.effect.message.balloons` | `"com.apple.messages.effect.CKBalloonEffect"` |
| `imessage.effect.message.heart` | `"com.apple.messages.effect.CKHeartEffect"` |
| `imessage.effect.message.lasers` | `"com.apple.messages.effect.CKLasersEffect"` |
| `imessage.effect.message.celebration` | `"com.apple.messages.effect.CKHappyBirthdayEffect"` |
| `imessage.effect.message.sparkles` | `"com.apple.messages.effect.CKSparklesEffect"` |
| `imessage.effect.message.spotlight` | `"com.apple.messages.effect.CKSpotlightEffect"` |
| `imessage.effect.message.echo` | `"com.apple.messages.effect.CKEchoEffect"` |


