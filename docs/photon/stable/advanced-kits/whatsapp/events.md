##### Events

Source: https://photon.codes/docs/advanced-kits/whatsapp/events.md
Documentation version: Stable

`client.events.subscribe()` returns an async iterable of every event Meta sends for your business account — inbound messages and delivery status updates. The stream reconnects automatically on failure and buffers missed events while you're offline.

###### The event stream

```ts
for await (const event of client.events.subscribe()) {
  switch (event.type) {
    case "message":
      // inbound message from a user
      break;
    case "status":
      // status update for a message you sent
      break;
  }
}
```

Every event carries a `cursor` string. The cursor advances with each event — save the most recent one and pass it back on restart to pick up where you left off:

```ts
for await (const event of client.events.subscribe({ cursor: lastCursor })) {
  lastCursor = event.cursor;
  await persist(lastCursor); // durable storage
  // handle event...
}
```

###### Subscribe options

**SubscribeOptions**

| Option | Type | Description |
|---|---|---|
| `cursor` | `string` | Resume from a previously saved cursor. |
| `reconnect` | `ReconnectOptions` | Reconnection configuration for automatic reconnects. |

###### Inbound messages

When `event.type === "message"`, the event carries an `InboundMessage`. Narrow on `content.type` before reading content-specific fields:

```ts
if (event.type === "message") {
  const { message } = event;

  switch (message.content.type) {
    case "text":
      console.log(message.content.body);
      break;
    case "image":
    case "video":
    case "audio":
    case "document":
      console.log(message.content.media.id);
      const { url } = await client.media.getUrl(message.content.media.id);
      break;
    case "location":
      console.log(message.content.location.latitude);
      break;
    case "reaction":
      console.log(message.content.reaction.emoji);
      break;
    case "interactive":
      // button / list / flow reply — see Interactive messages
      break;
    case "order":
      console.log(message.content.order.productItems);
      break;
  }
}
```

###### Inbound content variants

**InboundContent** — Every content shape a WhatsApp user can send.

| Variant | Fields |
|---|---|
| `"text"` | `body` |
| `"image"` | `media` |
| `"video"` | `media` |
| `"audio"` | `media` |
| `"document"` | `media` |
| `"sticker"` | `sticker` |
| `"location"` | `location` |
| `"contacts"` | `contacts` |
| `"reaction"` | `reaction` |
| `"interactive"` | `interactive` |
| `"button"` | `button` |
| `"order"` | `order` |
| `"system"` | `system` |
| `"unknown"` | — |

###### Replying to an incoming message

Thread your reply with `replyTo: message.id`:

```ts
if (event.type === "message" && event.message.content.type === "text") {
  await client.messages.send({
    to: event.message.from,
    replyTo: event.message.id,
    text: `You said: ${event.message.content.body}`,
  });
}
```

###### Status updates

When `event.type === "status"`, the event carries a `StatusUpdate`. The `status` field progresses through `sent → delivered → read` (or `played` for voice notes, or `failed`):

```ts
if (event.type === "status") {
  const { status } = event;
  console.log(`${status.id}: ${status.status}`);
  if (status.status === "failed") {
    for (const err of status.errors) {
      console.error(err.code, err.title, err.message);
    }
  }
}
```

`status.bizOpaqueCallbackData` echoes whatever you passed on the original `send()` call — use it to correlate the status back to your own order/ticket/session ID.

###### Reconnection

`subscribe()` reconnects automatically. Tune the backoff via `options.reconnect`:

**ReconnectOptions**

| Option | Type | Description |
|---|---|---|
| `initialDelay` | `number` | Initial delay in milliseconds before the first reconnect. Default `1000`. |
| `maxAttempts` | `number` | Maximum number of consecutive reconnect attempts. Default `Infinity`. |
| `maxDelay` | `number` | Maximum delay in milliseconds between retries. Default `30000`. |
| `multiplier` | `number` | Multiplier applied to the delay after each failed attempt. Default `2`. |
| `onReconnect` | `(attempt: number) =&gt; void` | Callback invoked before each reconnect attempt. |

```ts
client.events.subscribe({
  cursor: lastCursor,
  reconnect: {
    initialDelay: 500,
    maxDelay: 60_000,
    maxAttempts: 10,
    onReconnect: (attempt) => console.log(`reconnect attempt ${attempt}`),
  },
});
```

On reconnect, the stream internally calls `fetchMissedEvents` with the last cursor it saw, so you don't lose events that arrived while you were offline.

###### Fetching missed events manually

If your client crashed without draining the stream, fetch missed events on startup before resubscribing:

```ts
const { events } = await client.events.fetchMissed({
  cursor: lastCursor,
  limit: 100,
});

for (const event of events) {
  // replay in order
}

// then resume live subscription
for await (const event of client.events.subscribe({ cursor: lastCursor })) {
  // ...
}
```

Missed events are verified against your `app_secret` server-side before being returned — payloads that fail verification are dropped.

###### Message context, referrals, errors

Every `InboundMessage` can also carry:

- `context` — reply-to metadata if the user replied to one of your earlier messages.
- `referral` — set when the user arrived via a Click-to-WhatsApp ad.
- `errors` — non-empty when Meta returned a partial error alongside the message.
- `contact` — the sender's display name (when available).


