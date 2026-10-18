// Local status and development routes only. The phone and the dashboard talk to the Marco server, never to this
// service (docs/INTERFACES.md §5). Bound to 127.0.0.1: nothing here is meant for other machines.
import { serve } from "@hono/node-server";
import { Hono } from "hono";
import type { MarcoAgent } from "./agent.js";
import type { Config } from "./config.js";
import type { LabelRequest } from "./marco-server.js";
import type { SimChannel, SimPart } from "./sim.js";
import type { Store } from "./store.js";

interface HttpDeps {
  config: Config;
  agent: MarcoAgent;
  store: Store;
  sim: SimChannel | null;
  /** Whether the /v1/photon socket is up; recent unanswered requests replay on reconnect. */
  serverConnected: () => boolean;
}

export function startHttp({ config, agent, store, sim, serverConnected }: HttpDeps) {
  const app = new Hono();

  app.get("/health", (c) => {
    const questions = store.caretakers().flatMap((t) => store.openQuestions(t.handle));
    const pending = store.pendingIdentifyQuestions();
    const primary = agent.primaryCaretaker();
    return c.json({
      ok: serverConnected() && !!primary && pending.length === 0,
      mode: config.mode,
      marco_server: { url: config.marcoServerUrl, connected: serverConnected() },
      caretakers: store.caretakers().map((t) => t.name),
      primary_caretaker: primary?.name ?? null,
      pending_questions: pending.length,
      open_questions: questions.length,
      items: store.items().length,
    });
  });

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
      const message = sim.inbound(body.from ?? "+13105550101", parts, { ...(body.reply_to ? { replyTo: body.reply_to } : {}) });
      await agent.handle(message);
      await agent.settled();
      return c.json({ message_id: message.id, marco_sent: sim.outbox.slice(before) });
    });

    app.post("/dev/read", async (c) => {
      const body = await c.req.json<{ from?: string; message_id: string }>();
      await agent.handle(sim.readReceipt(body.from ?? "+13105550101", body.message_id));
      return c.json({ ok: true });
    });

    // Stand in for the server's label_request, e.g. when testing without the phone.
    app.post("/dev/label_request", async (c) => {
      const request = await c.req.json<LabelRequest>();
      return c.json(await agent.onLabelRequest({ ...request, type: "label_request" }));
    });

    app.get("/dev/outbox", (c) => c.json(sim.outbox));
  }

  return serve({ fetch: app.fetch, port: config.port, hostname: "127.0.0.1" });
}
