#### Quickstart

Source: https://photon.codes/docs/webhooks/quickstart.md
Documentation version: Stable

The [Overview](https://photon.codes/docs/webhooks/overview) introduced the model — a service POSTing signed JSON to a URL you publish. This page makes it real. We'll go from "I have a Spectrum project" to "my server processed a real message" in about five minutes, using Bun + Hono on the server side and [ngrok](https://ngrok.com/) to expose your local machine to the internet so you can test before deploying.

If you already have a deployed HTTPS URL, skip the ngrok step.

##### Prerequisites

- A Spectrum project with at least one platform enabled. See [Providers](https://photon.codes/docs/spectrum-ts/providers) for the current list, or [Getting Started with Spectrum](https://photon.codes/docs/spectrum-ts/getting-started) if you don't have a project yet.
- Your project id and project secret, from the [dashboard](https://app.photon.codes/dashboard) or `photon projects show`.
- A reachable, public HTTPS URL — ngrok works for local development. The worker won't deliver to plain `http://` or to a private/internal address like `localhost`, so point it at the ngrok `https://` URL, not the local port directly.

**Stand up a local endpoint**

Create `server.ts`. We'll fill in the verification logic in the next step.

```ts server.ts
import { Hono } from 'hono';

const app = new Hono();

app.post('/spectrum-webhook', async (c) => {
  const body = await c.req.text();
  console.log('received', body.slice(0, 200));
  return c.text('ok', 200);
});

export default { port: 3000, fetch: app.fetch };
```

```sh
bun add hono
bun --hot server.ts
```

In another terminal, expose port 3000:

```sh
ngrok http 3000
```

Copy the `https://...ngrok-free.app` URL it prints. That's your webhook destination.

**Register the URL**

Use `curl` (or any HTTP client) to register the URL with your project credentials:

```sh
curl -X POST "https://spectrum.photon.codes/projects/$PROJECT_ID/webhooks/" \
  -u "$PROJECT_ID:$PROJECT_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"webhookUrl":"https://abcd1234.ngrok-free.app/spectrum-webhook"}'
```

The response contains the `signingSecret` — **save it now**. This is the only time you will ever see it.

```json
{
  "succeed": true,
  "data": {
    "id": "6a4d2e8c-7b1f-4d3a-9a8e-2c5d6f7e8a9b",
    "webhookUrl": "https://abcd1234.ngrok-free.app/spectrum-webhook",
    "signingSecret": "a3f8e29b...5c7e9b2d",
    "createdAt": "2026-05-14T19:00:00Z",
    "updatedAt": "2026-05-14T19:00:00Z"
  }
}
```

Export the secret so the server can use it:

```sh
export SPECTRUM_SIGNING_SECRET=a3f8e29b...5c7e9b2d
```

Restart `bun --hot server.ts` after exporting so the variable is in scope.

**Add signature verification**

Replace `server.ts` with a version that verifies the signature before processing the body:

```ts server.ts
import { Hono } from 'hono';
import { createHmac, timingSafeEqual } from 'node:crypto';

const app = new Hono();
const SECRET = process.env.SPECTRUM_SIGNING_SECRET!;
const TOLERANCE_SEC = 5 * 60;

app.post('/spectrum-webhook', async (c) => {
  const rawBody = await c.req.text();
  const event = c.req.header('X-Spectrum-Event');
  const timestamp = c.req.header('X-Spectrum-Timestamp');
  const signature = c.req.header('X-Spectrum-Signature');

  if (!event || !timestamp || !signature) {
    return c.text('missing headers', 400);
  }

  const age = Math.abs(Math.floor(Date.now() / 1000) - Number(timestamp));
  if (!Number.isFinite(age) || age > TOLERANCE_SEC) {
    return c.text('stale timestamp', 400);
  }

  const expected =
    'v0=' +
    createHmac('sha256', SECRET)
      .update(`v0:${timestamp}:${rawBody}`)
      .digest('hex');

  const a = Buffer.from(expected);
  const b = Buffer.from(signature);
  if (a.length !== b.length || !timingSafeEqual(a, b)) {
    return c.text('bad signature', 401);
  }

  const payload = JSON.parse(rawBody);
  if (event === 'messages') {
    console.log('message from', payload.message.sender.id, ':', payload.message.content);
  }

  return c.text('ok', 200);
});

export default { port: 3000, fetch: app.fetch };
```

Three things to notice:

- We read the body as **raw text** (`c.req.text()`), not parsed JSON. The signature is computed over the exact bytes that arrived; any reformatting breaks verification.
- We reject timestamps older than 5 minutes for replay protection.
- We compare with `timingSafeEqual` to avoid leaking information about the secret through response timing.

See [Verifying signatures](https://photon.codes/docs/webhooks/verifying-signatures) for the same logic in Express, FastAPI, and others.

**Send a real message**

Send a real message to your project from any of its enabled platforms — an iMessage to the assigned number, a WhatsApp message, whatever you've configured. Within a second or two, your terminal should print:

```text
message from +15550100 : { type: 'text', text: 'hi' }
```

If you see `bad signature`, double-check that you exported `SPECTRUM_SIGNING_SECRET` correctly and re-started the server.

If you see `missing headers`, the request didn't come from Spectrum — check your ngrok URL and that the registered `webhookUrl` matches.

**Reply from your handler (optional)**

The webhook delivery only carries inbound messages — there is no public HTTP "send a message" endpoint today. To reply, run the [`spectrum-ts`](https://photon.codes/docs/spectrum-ts/getting-started) SDK in a separate process (or alongside your handler) and call `space.send(...)` there. The webhook tells your service *what* arrived; the SDK is what puts a message back on the wire.

A common split:

```ts
// sender.ts — long-lived process holding an outbound SDK instance
import { Spectrum, text } from "spectrum-ts";
import { imessage } from "spectrum-ts/providers/imessage";

const app = await Spectrum({
  projectId: process.env.PROJECT_ID!,
  projectSecret: process.env.PROJECT_SECRET!,
  providers: [imessage.config()],
});
const im = imessage(app);

// call this from your webhook handler (e.g. via a queue / RPC).
// There is no "get space by id" API — rebuild the DM from the sender's
// address (the webhook's `message.sender.id`, an E.164 number for iMessage).
export const reply = async (senderId: string, body: string) => {
  const user = await im.user(senderId);
  const space = await im.space(user);
  await space.send(text(body));
};
```

Inside the webhook handler, acknowledge with `2xx` first (the worker treats a slow response as a timeout and retries) and enqueue the reply job:

```ts
app.post('/spectrum-webhook', async (c) => {
  if (!verify(c)) return c.text('bad signature', 401);
  const payload = JSON.parse(await c.req.text());
  if (payload.event === 'messages' && payload.message.content.type === 'text') {
    void enqueueReply(payload.message.sender.id, `echo: ${payload.message.content.text}`);
  }
  return c.text('ok', 200);
});
```

An HTTP send-message API is on the roadmap; until then, the SDK is the supported path.

##### What you just built

You have an end-to-end pipeline:

```text
user's device → platform → Spectrum → POST /spectrum-webhook → your code
```

You verified each delivery is genuine (not spoofed), recent (not a replay), and unmodified (not tampered with).

##### What's next

You wired up one URL, one verifier, and one delivery. The next chapters of the guide expand each piece — what's *in* the delivery, *why* the verifier looks the way it does, and what happens when things fail.

- [**Events**](https://photon.codes/docs/webhooks/events) — Open the envelope — every header and every field in the payload, with examples for each content type.
- [**Verifying signatures**](https://photon.codes/docs/webhooks/verifying-signatures) — The *why* behind the verifier, plus copy-paste implementations for Node, Bun, Python, and Go.
- [**Delivery and retries**](https://photon.codes/docs/webhooks/delivery) — What the worker does when your endpoint is slow, down, or returns an unexpected status code.
- [**Managing webhooks**](https://photon.codes/docs/webhooks/managing-webhooks) — List, delete, and rotate signing secrets via the API — full schemas in the [API reference](https://photon.codes/docs/api-reference/introduction).


