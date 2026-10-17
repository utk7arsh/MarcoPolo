#### Text

Source: https://photon.codes/docs/spectrum-ts/content/text.md
Documentation version: Stable

Use `text()` for plain outbound text. You can also pass a plain string anywhere Spectrum accepts content.

```ts
import { text } from "spectrum-ts";

await space.send(text("Hello, world."));

// Plain strings are equivalent:
await space.send("Hello, world.");
```

##### Streaming text

Both `text()` and `markdown()` accept a `StreamTextSource`: an AI SDK result, an `AsyncIterable`, or a `ReadableStream`.

On platforms that support it, text streams live. iMessage in remote mode sends the first chunk as a real message and edits in place as more text arrives. Telegram private chats animate a native draft preview. Platforms without streaming support wait for the stream to finish and send the full text as one message.

**Vercel AI SDK**

```ts
import { text } from "spectrum-ts";
import { streamText as aiStreamText } from "ai";

const result = aiStreamText({ model, prompt: message.content.text });
await space.send(text(result));
```

**AsyncIterable**

```ts
import { text } from "spectrum-ts";

async function* generate() {
  yield "Hello, ";
  yield "world!";
}

await space.send(text(generate()));
```

**Custom extractor**

```ts
import { text } from "spectrum-ts";

await space.send(
  text(customStream, {
    extract: (chunk) => chunk.delta?.text ?? null,
  }),
);
```

A stream can only be sent once.

**TextStreamOptions**

| Option | Type | Description |
|---|---|---|
| `extract?` | `DeltaExtractor&lt;T&gt;` | Map each chunk to its incremental text. Omit to rely on built-in auto-detection of the common SDK shapes (OpenAI chat/responses, Anthropic messages, AI SDK text streams, and plain strings). |


