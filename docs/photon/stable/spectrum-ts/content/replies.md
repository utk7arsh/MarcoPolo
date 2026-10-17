#### Replies

Source: https://photon.codes/docs/spectrum-ts/content/replies.md
Documentation version: Stable

Use `reply()` to send a threaded reply by wrapping content with the message being replied to. See [Reactions and replies](https://photon.codes/docs/spectrum-ts/reactions-and-replies) for the full details and sugar methods.

```ts
import { reply, text } from "spectrum-ts";

await space.send(reply(text("Got it"), message));
```

`reply()` cannot wrap `reply`, `edit`, `reaction`, `group`, `typing`, `rename`, `avatar`, `addMember`, `removeMember`, `leaveSpace`, `unsend`, or `read` content.

##### Reply sugar

`message.reply(...)` has the same variadic signature and delegates to `space.send(reply(...))` internally:

```ts
await message.reply(
  "Thanks for the question.",
  attachment("/path/to/answer.png"),
);
```

On platforms without thread support, `reply()` resolves as a no-op. If you need guaranteed delivery, use `space.send(...)` instead.


