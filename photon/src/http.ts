import { serve } from "@hono/node-server";
import { createNodeWebSocket } from "@hono/node-ws";
import { Hono, type Context } from "hono";
import { readFile } from "node:fs/promises";
import { basename } from "node:path";
import type { MarcoAgent } from "./agent.js";
import type { Config } from "./config.js";
import { itemView, type EventBus } from "./events.js";
import { contentTypeFor, type Media } from "./media.js";
import type { SimPart, SimPlatform } from "./sim.js";
import type { Store } from "./store.js";

interface HttpDeps {
  config: Config;
  agent: MarcoAgent;
  store: Store;
  media: Media;
  events: EventBus;
  sim: SimPlatform | null;
}

const STATUS_CODE = { sent: 202, already_asked: 200, already_labeled: 200, no_caretaker: 409, failed: 502 } as const;

export function startHttp({ config, agent, store, media, events, sim }: HttpDeps) {
  const app = new Hono();
  const { injectWebSocket, upgradeWebSocket } = createNodeWebSocket({ app });

  app.use("*", async (c, next) => {
    const open = c.req.path === "/health" || c.req.path.startsWith("/media/");
    if (!config.bridgeToken || open) return next();
    const token = c.req.header("authorization")?.replace(/^Bearer\s+/i, "") ?? c.req.query("token");
    if (token !== config.bridgeToken) return c.json({ error: "unauthorized" }, 401);
    return next();
  });

  app.get("/health", (c) =>
    c.json({
      ok: true,
      mode: config.mode,
      caretakers: store.caretakers().map((t) => t.name),
      primary_caretaker: agent.primaryCaretaker()?.name ?? null,
      items: store.items().length,
    }),
  );

  // Flow B. The phone posts the touched item's photo (ideally with the item boxed).
  // Accepts multipart (field `image`, optional `item_id`), JSON {image_base64, mime_type?, item_id?},
  // or a raw image body with ?item_id=.
  app.post("/labels/request", async (c) => {
    const input = await readImage(c);
    if (!input) return c.json({ error: "send an image: multipart field 'image', JSON image_base64, or a raw image body" }, 400);
    const result = await agent.requestLabel(input);
    return c.json(result, STATUS_CODE[result.status]);
  });

  app.get("/labels/requests/:id", (c) => {
    const q = store.question(c.req.param("id"));
    if (!q) return c.json({ error: "not found" }, 404);
    const item = store.item(q.itemId);
    return c.json({
      request_id: q.id,
      status: q.status,
      seen_at: q.seenAt,
      answered_at: q.answeredAt,
      caretaker: store.caretaker(q.caretaker)?.name ?? null,
      item: item ? itemView(item, media) : null,
    });
  });

  app.get("/items", (c) => c.json(store.items().map((i) => itemView(i, media))));

  app.get("/items/:id", (c) => {
    const item = store.item(c.req.param("id"));
    return item ? c.json(itemView(item, media)) : c.json({ error: "not found" }, 404);
  });

  app.get("/media/:file", async (c) => {
    const file = basename(c.req.param("file"));
    try {
      const bytes = await readFile(media.path(file));
      return c.body(bytes, 200, { "content-type": contentTypeFor(file), "cache-control": "public, max-age=31536000, immutable" });
    } catch {
      return c.json({ error: "not found" }, 404);
    }
  });

  // Push channel for the phone and the family page: label_ready, label_request_seen, ...
  app.get(
    "/events",
    upgradeWebSocket(() => {
      let unsubscribe: (() => void) | undefined;
      return {
        onOpen(_event, ws) {
          ws.send(JSON.stringify({ type: "hello", at: new Date().toISOString() }));
          unsubscribe = events.subscribe((event) => ws.send(JSON.stringify(event)));
        },
        onClose() {
          unsubscribe?.();
        },
      };
    }),
  );

  app.get("/events/recent", (c) => c.json(events.recent));

  if (sim) {
    // Play the caretaker without Photon: JSON {from, text?, image_base64?, voice_base64?, reply_to?}.
    // Responds with what Marco sent back.
    app.post("/dev/inbound", async (c) => {
      const body = await c.req.json<{ from?: string; text?: string; image_base64?: string; image_mime?: string; voice_base64?: string; voice_mime?: string; reply_to?: string }>();
      const parts: SimPart[] = [];
      if (body.image_base64) parts.push({ image: Buffer.from(body.image_base64, "base64"), mimeType: body.image_mime ?? "image/jpeg" });
      if (body.text) parts.push({ text: body.text });
      if (body.voice_base64) parts.push({ voice: Buffer.from(body.voice_base64, "base64"), mimeType: body.voice_mime ?? "audio/x-caf" });
      if (!parts.length) return c.json({ error: "send text, image_base64 or voice_base64" }, 400);
      const before = sim.outbox.length;
      const [space, message] = sim.inbound(body.from ?? "+13105550101", parts, { ...(body.reply_to ? { replyTo: body.reply_to } : {}) });
      await agent.handle(space, message);
      await agent.settled();
      return c.json({ message_id: message.id, marco_sent: sim.outbox.slice(before) });
    });

    app.post("/dev/read", async (c) => {
      const body = await c.req.json<{ from?: string; message_id: string }>();
      const [space, message] = sim.readReceipt(body.from ?? "+13105550101", body.message_id);
      await agent.handle(space, message);
      return c.json({ ok: true });
    });

    app.get("/dev/outbox", (c) => c.json(sim.outbox));
  }

  const server = serve({ fetch: app.fetch, port: config.port });
  injectWebSocket(server);
  return server;
}

async function readImage(c: Context): Promise<{ image: Buffer; mimeType: string; itemId?: string } | null> {
  const type = c.req.header("content-type") ?? "";
  const withItem = (image: Buffer, mimeType: string, itemId: unknown) =>
    typeof itemId === "string" && itemId ? { image, mimeType, itemId } : { image, mimeType };

  if (type.startsWith("multipart/form-data")) {
    const body = await c.req.parseBody();
    const file = body.image;
    if (!(file instanceof File)) return null;
    return withItem(Buffer.from(await file.arrayBuffer()), file.type || "image/jpeg", body.item_id);
  }
  if (type.startsWith("application/json")) {
    const body = await c.req.json<{ image_base64?: string; mime_type?: string; item_id?: string }>();
    if (!body.image_base64) return null;
    return withItem(Buffer.from(body.image_base64, "base64"), body.mime_type ?? "image/jpeg", body.item_id);
  }
  if (type.startsWith("image/")) {
    const bytes = Buffer.from(await c.req.arrayBuffer());
    return bytes.length ? withItem(bytes, type.split(";")[0]!, c.req.query("item_id")) : null;
  }
  return null;
}
