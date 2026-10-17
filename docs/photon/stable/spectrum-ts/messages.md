#### Messages

Source: https://photon.codes/docs/spectrum-ts/messages.md
Documentation version: Stable

Every incoming message arrives through `app.messages` as a tuple containing a `Space` and a `Message`. The space is already bound to the originating conversation — you don't need to resolve it yourself to reply.

##### Receiving messages

```ts
for await (const [space, message] of app.messages) {
  // handle the message
}
```

Messages from every configured provider merge into this single stream. The order reflects arrival time.

##### The Message shape

Every message conforms to `Message`.

**Message**

| Member | Description |
|---|---|
| `content: Content` |  |
| `direction: "inbound" \| "outbound"` |  |
| `edit(newContent: ContentInput): Promise&lt;void&gt;` |  |
| `readonly id: string` |  |
| `platform: TPlatform` |  |
| `react(reaction: string): Promise&lt;(Message&lt;TPlatform, AgentSender, TSpace&gt; & { content: Reaction;   }) \| undefined&gt;` | React to this message. Resolves to the reaction `Message` (content narrowed to `Reaction`) — keep it as the handle to `unsend()` later. Resolves `undefined` when the platform does not support reactions (warned and skipped). |
| `read(): Promise&lt;void&gt;` | Mark this message (and everything before it in the conversation) as read. Sugar for `space.send(read(this))`. Reads are fire-and-forget; per-platform granularity and support (e.g. iMessage marks the whole chat; Telegram/Slack silently no-op) surface from the provider's send action. Only inbound messages can be marked read; calling this on an outbound message throws. |
| `reply(content: ContentInput): Promise&lt;Message&lt;TPlatform, AgentSender, TSpace&gt; \| undefined&gt;` |  |
| `reply(...content: [ContentInput, ContentInput, ...ContentInput[]]): Promise&lt;Message&lt;TPlatform, AgentSender, TSpace&gt;[]&gt;` |  |
| `sender: TSender \| undefined` |  |
| `space: TSpace` |  |
| `timestamp: Date` |  |
| `unsend(): Promise&lt;void&gt;` | Retract this message. Sugar for `space.send(unsend(this))`. Unsends are fire-and-forget; per-platform support and constraints (e.g. iMessage's ~2-minute unsend window for regular messages) surface from the provider's send action. Only outbound messages can be unsent; calling this on an inbound message throws. |

##### Narrowing content

`Content` is a discriminated union. Narrow on `message.content.type` before accessing fields:

```ts
for await (const [space, message] of app.messages) {
  switch (message.content.type) {
    case "text":
      console.log(message.content.text);
      break;
    case "attachment":
      console.log(
        `${message.content.name} (${message.content.mimeType})`,
        await message.content.read(),
      );
      break;
    case "voice":
      console.log(`voice note (${message.content.duration}s)`);
      break;
    case "contact":
      console.log(message.content.name?.formatted, message.content.phones);
      break;
    case "richlink":
      console.log(message.content.url);
      break;
    case "reaction":
      console.log(`${message.content.emoji} on ${message.content.target.id}`);
      break;
    case "poll":
      console.log(message.content.title, message.content.options);
      break;
    case "poll_option":
      console.log(`vote ${message.content.selected ? "+" : "-"}`, message.content.title);
      break;
    case "group":
      console.log(`group of ${message.content.items.length} items`);
      break;
    case "addMember":
      console.log(`${message.sender?.id ?? "someone"} added ${message.content.members.join(", ")}`);
      break;
    case "custom":
      console.log(message.content.raw);
      break;
  }
}
```

**Content**

| Type | Fields |
|---|---|
| `"text"` | `text: string` |
| `"markdown"` | `markdown: string` — outbound-only styled text |
| `"attachment"` | `id: string`, `name: string`, `mimeType: string`, `size?: number`, `read()`, `stream()` |
| `"voice"` | `name?: string`, `mimeType: string`, `duration?: number`, `size?: number`, `read()`, `stream()` |
| `"contact"` | `name?`, `phones?`, `emails?`, `addresses?`, `org?`, `urls?`, `birthday?`, `note?`, `photo?`, `user?`, `raw?` |
| `"richlink"` | `url: string` |
| `"effect"` | `content`, `effect: string` — iMessage effect wrapping text, markdown, or an attachment |
| `"reaction"` | `emoji: string`, `target:` `Message` |
| `"poll"` | `title: string`, `options: { title: string }[]` |
| `"poll_option"` | `option: { title }`, `poll:` `Poll`, `selected: boolean`, `title: string` — sent as a vote |
| `"group"` | `items:` `Message``[]` — bundled multi-message unit |
| `"rename"` | `displayName: string` — the chat was renamed |
| `"avatar"` | `action: { kind: "set", read(), mimeType } \| { kind: "clear" }` — group icon set or cleared |
| `"addMember"` | `members: string[]` — members added; `sender` is who added them |
| `"removeMember"` | `members: string[]` — members removed; `sender` is who removed them |
| `"leaveSpace"` | *(no fields)* — `sender` is the member who left |
| `"reply"` | `content:` `Content`, `target:` `Message` — threaded reply wrapping inner content |
| `"edit"` | `content:` `Content`, `target:` `Message` — rewrite of a previously-sent message |
| `"unsend"` | `target:` `Message` — retraction of a previously-sent message |
| `"read"` | `target:` `Message` — outbound: mark the conversation read through the target. Inbound: `sender` read `target`, a message you sent |
| `"typing"` | `state: "start" \| "stop"` — typing indicator signal |
| `"streamText"` | `stream: () => AsyncIterable<string>`, `format?: "plain" \| "markdown"` — streaming text content |
| `"app"` | `url()`, `layout()`, `live?: boolean` — app-style link card |
| `"custom"` | `raw: unknown` — platform-specific structured data |

Outgoing-only variants like `"effect"` (an iMessage screen effect wrapping inner content) appear on messages you sent and are echoed by the platform; see [iMessage](https://photon.codes/docs/spectrum-ts/providers/imessage) for the builder.

Group-management events (`rename`, `avatar`, `addMember`, `removeMember`, `leaveSpace`) arrive with `message.sender` set to the acting user — or `undefined` when the platform recorded no actor — so narrow with `message.sender?.id`. The agent's own actions (e.g. `space.add(...)`) are not echoed back.

`read` is the other bidirectional arm: inbound, it means someone read a message you sent, with `message.sender` the reader and `content.target` your message. See [Read](https://photon.codes/docs/spectrum-ts/content/read).

##### Filtering out your own messages

Every `Message` carries a `direction`. Skip outbound messages when you only want user input:

```ts
for await (const [space, message] of app.messages) {
  if (message.direction === "outbound") continue;
  // handle incoming
}
```

##### Acting on a message

Every message is its own context. You can reply, react, or send new content into the space:

```ts
for await (const [space, message] of app.messages) {
  await message.react("❤️");
  await message.reply("Got it");
  await space.send("Here's more context");
}
```

See [Content](https://photon.codes/docs/spectrum-ts/content) for all the ways to build outgoing messages, and [Reactions and replies](https://photon.codes/docs/spectrum-ts/reactions-and-replies) for the details of `react` and `reply`.


