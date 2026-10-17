#### Polls

Source: https://photon.codes/docs/spectrum-ts/content/polls.md
Documentation version: Stable

Use `poll()` to send a poll with a title and a list of choices. Each choice can be a plain string or a `PollChoiceInput` object. Use `option()` when you want the explicit form.

```ts
import { poll, option } from "spectrum-ts";

// Variadic strings
await space.send(poll("Lunch?", "Pizza", "Sushi", "Tacos"));

// Or an array, optionally using option() for clarity
await space.send(poll("Lunch?", [
  option("Pizza"),
  option("Sushi"),
  option("Tacos"),
]));
```

Poll responses arrive as `poll_option` content. See [Messages](https://photon.codes/docs/spectrum-ts/messages) for narrowing on incoming votes.


