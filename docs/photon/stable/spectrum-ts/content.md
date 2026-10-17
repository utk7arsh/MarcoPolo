#### Content

Source: https://photon.codes/docs/spectrum-ts/content.md
Documentation version: Stable

Spectrum exposes a family of content builders for text, markdown, attachments, rich previews, replies, edits, typing indicators, chat metadata, and provider-specific payloads. Any API that takes a `ContentInput` accepts a plain string or a `ContentBuilder`.

Use this section when you need to choose the right outbound content shape or understand how a builder degrades across providers.

- [**Text**](https://photon.codes/docs/spectrum-ts/content/text) — Send plain text and stream generated text into supported providers.
- [**Markdown**](https://photon.codes/docs/spectrum-ts/content/markdown) — Send styled text that renders through each provider's native formatting model.
- [**Attachments**](https://photon.codes/docs/spectrum-ts/content/attachments) — Send files from paths, URLs, or buffers with stable attachment IDs.
- [**Voice**](https://photon.codes/docs/spectrum-ts/content/voice) — Send voice notes with audio metadata and provider fallbacks.
- [**Contacts**](https://photon.codes/docs/spectrum-ts/content/contacts) — Share contact cards from structured data, users, or vCards.
- [**Rich links**](https://photon.codes/docs/spectrum-ts/content/rich-links) — Let each platform render URLs with its native preview behavior.
- [**App link cards**](https://photon.codes/docs/spectrum-ts/content/app) — Present URLs as tappable app-style cards where providers support them.
- [**Polls**](https://photon.codes/docs/spectrum-ts/content/polls) — Send poll prompts and receive selected options as content.
- [**Groups**](https://photon.codes/docs/spectrum-ts/content/groups) — Bundle multiple messages into one logical visual group.
- [**Custom content**](https://photon.codes/docs/spectrum-ts/content/custom) — Send provider-specific structured payloads.
- [**Replies**](https://photon.codes/docs/spectrum-ts/content/replies) — Thread content under an existing message.
- [**Edits**](https://photon.codes/docs/spectrum-ts/content/edits) — Rewrite previously sent outbound messages.
- [**Unsend**](https://photon.codes/docs/spectrum-ts/content/unsend) — Retract a previously sent outbound message.
- [**Typing indicators**](https://photon.codes/docs/spectrum-ts/content/typing-indicators) — Send start and stop typing signals.
- [**Rename**](https://photon.codes/docs/spectrum-ts/content/rename) — Rename chats through the content pipeline.
- [**Avatar**](https://photon.codes/docs/spectrum-ts/content/avatar) — Set or clear group chat avatars.
- [**Membership**](https://photon.codes/docs/spectrum-ts/content/membership) — Add or remove group members and leave chats.
- [**Composing content**](https://photon.codes/docs/spectrum-ts/content/composing-content) — Send multiple content items or reply with multiple parts.

##### Builder shortcut

Plain strings are equivalent to `text()`:

```ts
await space.send("Hello, world.");
await space.send(text("Hello, world."));
```

Reach for an explicit builder when you need provider-aware behavior, structured metadata, or a content type that is not plain text.


