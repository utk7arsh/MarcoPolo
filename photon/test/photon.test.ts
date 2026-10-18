// The Photon 2.0 transport against a local fake of api.photon.codes: the official client makes real HTTP calls
// (and validates every response against Photon's schemas), and events arrive over a real Socket.IO server.
import assert from "node:assert/strict";
import { mkdtempSync, writeFileSync } from "node:fs";
import { createServer, type IncomingMessage } from "node:http";
import type { AddressInfo } from "node:net";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { Server } from "socket.io";
import { PhotonChannel, startEvents, type WireEvent } from "../src/photon.js";

const PROJECT = "pho_prj_test";
const KEY = "pho_sk_test";
const AT = "2026-10-17T20:00:00.000Z";
const CONV = { platform: "imessage", spaceId: "spc_mom", agentId: "usr_agent" };
const PHOTO_BYTES = Buffer.from("fake heic bytes");

const user = (id: string, kind: string, handle: string) => ({ id, kind, handle, platform: "imessage", projectId: PROJECT, details: { type: "shared" }, metadata: {} });
const space = { id: "spc_mom", kind: "direct", platform: "imessage", projectId: PROJECT, participantIds: ["usr_agent", "usr_mom"], details: {}, metadata: {} };
const accepted = (id: string) => ({
  id,
  projectId: PROJECT,
  platform: "imessage",
  status: "accepted",
  content: { type: "text", format: "plain", text: "ok" },
  sentBy: user("usr_agent", "agent", "+13105559999"),
  receivedBy: user("usr_mom", "human", "+13105550101"),
  space,
  metadata: {},
  acceptance: { code: "delivery_confirmation_not_applicable", message: "accepted" },
  timestamps: { createdAt: AT, acceptedAt: AT, dispatchedAt: AT },
  createdAt: AT,
  updatedAt: AT,
});
const attachmentMeta = (id: string, contentType: string, filename: string) => ({ id, projectId: PROJECT, contentType, filename, sizeBytes: 15, createdAt: AT, updatedAt: AT });
const received = (content: { type: string } & Record<string, unknown>, extra: Record<string, unknown> = {}) => ({
  id: "evt_1",
  type: "message.received",
  data: {
    projectId: PROJECT,
    object: { id: "msg_in_1", platform: "imessage", status: "received", content, sentBy: user("usr_mom", "human", "+13105550101"), receivedBy: user("usr_agent", "agent", "+13105559999"), space, ...extra },
  },
}) as WireEvent & { data: { object: { sentBy: unknown } } };

interface Captured {
  method: string;
  url: string;
  headers: IncomingMessage["headers"];
  body: Buffer;
}

async function fakePhoton() {
  const requests: Captured[] = [];
  let sent = 0;
  const server = createServer(async (req, res) => {
    const chunks: Buffer[] = [];
    for await (const c of req) chunks.push(c as Buffer);
    requests.push({ method: req.method!, url: req.url!, headers: req.headers, body: Buffer.concat(chunks) });
    const json = (status: number, body: unknown) => {
      res.writeHead(status, { "content-type": "application/json" });
      res.end(JSON.stringify(body));
    };
    if (req.headers.authorization !== `Bearer ${KEY}`) return json(401, { title: "unauthorized" });
    const base = `/v1/projects/${PROJECT}`;
    if (req.method === "POST" && req.url === `${base}/messages`) return json(202, accepted(`msg_out_${++sent}`));
    if (req.method === "POST" && req.url === `${base}/attachments`) return json(201, attachmentMeta("att_up_1", "image/jpeg", "jar.jpg"));
    if (req.method === "GET" && req.url === `${base}/attachments/att_photo`) return json(200, attachmentMeta("att_photo", "image/heic", "IMG_0001.HEIC"));
    if (req.method === "GET" && req.url === `${base}/attachments/att_voice`) return json(200, attachmentMeta("att_voice", "audio/x-caf", "Audio Message.caf"));
    if (req.method === "GET" && req.url?.endsWith("/content")) {
      res.writeHead(200, { "content-type": "application/octet-stream" });
      return res.end(PHOTO_BYTES);
    }
    json(404, { title: "not found" });
  });
  await new Promise<void>((r) => server.listen(0, "127.0.0.1", r));
  const origin = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
  return { origin, requests, close: () => server.close(), channel: new PhotonChannel({ origin, projectId: PROJECT, apiKey: KEY }) };
}

const lastJson = (requests: Captured[]) => JSON.parse(requests.at(-1)!.body.toString("utf8"));

test("send: a text goes to POST /messages with the space, our agent as sender, and the thread parent", async () => {
  const api = await fakePhoton();
  try {
    const id = await api.channel.send(CONV, { type: "text", text: "Got it: cumin." }, { parentId: "msg_photo", key: "confirm:1" });
    assert.equal(id, "msg_out_1");
    const req = api.requests.at(-1)!;
    assert.equal(req.url, `/v1/projects/${PROJECT}/messages`);
    assert.equal(req.headers["idempotency-key"], "confirm:1");
    assert.deepEqual(lastJson(api.requests), {
      spaceId: "spc_mom",
      senderId: "usr_agent",
      parentMessageId: "msg_photo",
      content: { type: "text", format: "plain", text: "Got it: cumin." },
    });
  } finally {
    api.close();
  }
});

test("send: a photo is uploaded as multipart/related, then sent as an attachment", async () => {
  const api = await fakePhoton();
  const dir = mkdtempSync(join(tmpdir(), "marco-photon-"));
  const path = join(dir, "jar.jpg");
  writeFileSync(path, Buffer.from([0xff, 0xd8, 0xff, 0xe0, 1, 2, 3]));
  try {
    await api.channel.send(CONV, { type: "image", path, mimeType: "image/jpeg" }, { key: "ask:req_1:photo" });
    const [upload, send] = api.requests;
    assert.equal(upload?.url, `/v1/projects/${PROJECT}/attachments`);
    assert.match(String(upload?.headers["content-type"]), /^multipart\/related; type="application\/json"; boundary=marco-/);
    assert.equal(Number(upload?.headers["content-length"]), upload?.body.length);
    const boundary = String(upload?.headers["content-type"]).split("boundary=")[1]!;
    const sections = upload!.body.toString("latin1").split(`--${boundary}`);
    assert.equal(sections.length, 4, "two parts plus preamble and closing marker");
    assert.match(sections[1]!, /Content-Type: application\/json\r\n\r\n\{"contentType":"image\/jpeg","sizeBytes":7,"filename":"jar.jpg"\}/);
    assert.match(sections[2]!, /^\r\nContent-Type: image\/jpeg\r\n\r\n\xff\xd8\xff\xe0\x01\x02\x03\r\n$/);
    assert.equal(sections[3], "--\r\n");
    assert.deepEqual(JSON.parse(send!.body.toString()).content, { type: "attachment", attachmentId: "att_up_1" });
  } finally {
    api.close();
  }
});

test("react: a tapback is a reaction message threaded on its target", async () => {
  const api = await fakePhoton();
  try {
    await api.channel.react(CONV, "msg_in_9", "❤️");
    const body = lastJson(api.requests);
    assert.equal(body.parentMessageId, "msg_in_9");
    assert.deepEqual(body.content, { type: "reaction", action: "add", reaction: "❤️" });
  } finally {
    api.close();
  }
});

test("send: retrying a photo uses identical multipart bytes with the same idempotency key", async () => {
  const api = await fakePhoton();
  const path = join(mkdtempSync(join(tmpdir(), "marco-upload-retry-")), "jar.jpg");
  writeFileSync(path, PHOTO_BYTES);
  try {
    const content = { type: "image" as const, path, mimeType: "image/jpeg" };
    await api.channel.send(CONV, content, { key: "ask:retry:photo" });
    await api.channel.send(CONV, content, { key: "ask:retry:photo" });
    const uploads = api.requests.filter((r) => r.url.endsWith("/attachments"));
    assert.equal(uploads.length, 2);
    assert.equal(uploads[0]!.headers["idempotency-key"], uploads[1]!.headers["idempotency-key"]);
    assert.deepEqual(uploads[0]!.body, uploads[1]!.body, "retries must not change the multipart boundary");
  } finally {
    api.close();
  }
});

test("toInbound: a photo with a caption becomes media + text, with lazily downloaded bytes", async () => {
  const api = await fakePhoton();
  try {
    const event = received({ type: "group", parts: [{ type: "attachment", attachmentId: "att_photo" }, { type: "text", format: "plain", text: "Dad's keys" }] }, { parentMessageId: "msg_out_7" });
    const msg = await api.channel.toInbound(event);
    assert.ok(msg);
    assert.equal(msg.kind, "message");
    assert.equal(msg.from, "+13105550101");
    assert.deepEqual(msg.conversation, CONV);
    assert.equal(msg.parentId, "msg_out_7");
    const [media, text] = msg.parts;
    assert.equal(media?.type, "media");
    assert.equal(media?.type === "media" && media.mimeType, "image/heic");
    assert.deepEqual(text, { type: "text", text: "Dad's keys" });
    assert.ok(!api.requests.some((r) => r.url.endsWith("/content")), "nothing downloaded until read()");
    assert.deepEqual(media?.type === "media" && (await media.read()), PHOTO_BYTES);
  } finally {
    api.close();
  }
});

test("toInbound: voice memos, read receipts, and things to ignore", async () => {
  const api = await fakePhoton();
  try {
    const voice = await api.channel.toInbound(received({ type: "voice", attachmentId: "att_voice" }));
    assert.equal(voice?.parts[0]?.type === "media" && voice.parts[0].mimeType, "audio/x-caf");

    const read = await api.channel.toInbound(received({ type: "message.read" }, { parentMessageId: "msg_out_3" }));
    assert.deepEqual([read?.kind, read?.parentId], ["read", "msg_out_3"]);

    const group = received({ type: "text", format: "plain", text: "hi all" }, { space: { ...space, kind: "group" } });
    assert.equal(await api.channel.toInbound(group), null, "shared lines are direct-only; ignore group spaces");
    const self = received({ type: "text", format: "plain", text: "loop" }, { receivedBy: user("usr_mom", "human", "+13105550101") });
    assert.equal(await api.channel.toInbound(self), null, "sender and receiver are the same user");

    const typing = await api.channel.toInbound(received({ type: "space.typing.update", typing: true }));
    assert.equal(typing, null);
    const fromAgent = received({ type: "text", format: "plain", text: "echo" });
    fromAgent.data.object.sentBy = user("usr_agent", "agent", "+13105559999");
    assert.equal(await api.channel.toInbound(fromAgent), null);
    assert.equal(await api.channel.toInbound({ id: "evt_2", type: "message.delivered", data: {} }), null);
  } finally {
    api.close();
  }
});

test("events: subscribes with the saved cursor, handles deliveries in order, checkpoints each", async () => {
  const http = createServer();
  // Photon accepts the path with or without a trailing slash; our client sends none (as Photon's example does).
  const io = new Server(http, { path: `/v1/projects/${PROJECT}/events/ws`, addTrailingSlash: false, transports: ["websocket"] });
  const subscribes: Array<{ startSeq: number; apiVersion?: string }> = [];
  io.on("connection", (socket) => {
    assert.equal(socket.handshake.headers.authorization, `Bearer ${KEY}`);
    socket.on("subscribe", (payload: { startSeq: number; apiVersion?: string }, ack: (r: unknown) => void) => {
      subscribes.push(payload);
      ack({ ok: true, projectId: PROJECT, apiVersion: "2026-07-01", connectionId: "c1", startSeq: payload.startSeq, limits: { maxFrameBytes: 1e6, maxReplyBodyBytes: 1e6 } });
      socket.emit("delivery", { id: "evt_a", type: "message.received" }, { seq: 41, replyExpected: false });
      socket.emit("delivery", { id: "evt_b", type: "message.received" }, { seq: 43, replyExpected: false });
      socket.emit("delivery", { id: "evt_old", type: "message.received" }, { seq: 40, replyExpected: false });
    });
  });
  await new Promise<void>((r) => http.listen(0, "127.0.0.1", r));
  const origin = `http://127.0.0.1:${(http.address() as AddressInfo).port}`;

  let saved = 40;
  const handled: string[] = [];
  const stream = startEvents({ origin, projectId: PROJECT, apiKey: KEY }, { load: () => saved, save: (seq) => (saved = seq) }, async (event) => {
    await new Promise((r) => setTimeout(r, 20)); // slow handler: order must still hold
    handled.push(event.id);
  });
  try {
    for (let i = 0; i < 100 && handled.length < 2; i++) await new Promise((r) => setTimeout(r, 20));
    await new Promise((r) => setTimeout(r, 60));
    assert.deepEqual(subscribes, [{ startSeq: 40, apiVersion: "2026-07-01" }]);
    assert.deepEqual(handled, ["evt_a", "evt_b"], "in order; the already-handled seq 40 is skipped");
    assert.equal(saved, 43);
  } finally {
    stream.stop();
    io.close();
    http.close();
  }
});

async function fakeEventServer(deliveries: Array<{ id: string; seq: number }>) {
  const http = createServer();
  const io = new Server(http, { path: `/v1/projects/${PROJECT}/events/ws`, addTrailingSlash: false, transports: ["websocket"] });
  const subscribes: number[] = [];
  io.on("connection", (socket) => {
    socket.on("subscribe", (payload: { startSeq: number }, ack: (r: unknown) => void) => {
      subscribes.push(payload.startSeq);
      ack({ ok: true, projectId: PROJECT, apiVersion: "2026-07-01", connectionId: `c${subscribes.length}`, startSeq: payload.startSeq, limits: { maxFrameBytes: 1e6, maxReplyBodyBytes: 1e6 } });
      // Like Photon: replay everything after the subscriber's cursor.
      for (const d of deliveries) if (d.seq > payload.startSeq) socket.emit("delivery", { id: d.id, type: "message.received" }, { seq: d.seq, replyExpected: false });
    });
  });
  await new Promise<void>((r) => http.listen(0, "127.0.0.1", r));
  const origin = `http://127.0.0.1:${(http.address() as AddressInfo).port}`;
  return { origin, subscribes, close: () => (io.close(), http.close()) };
}

const waitFor = async (check: () => boolean, ms = 8000) => {
  const until = Date.now() + ms;
  while (!check() && Date.now() < until) await new Promise((r) => setTimeout(r, 25));
  assert.ok(check(), "timed out waiting");
};

test("events: a failed handler is not checkpointed; the stream resumes from the cursor and redelivers it", async () => {
  const server = await fakeEventServer([{ id: "evt_a", seq: 41 }, { id: "evt_b", seq: 43 }]);
  let saved = 40;
  let failOnce = true;
  const handled: string[] = [];
  const stream = startEvents({ origin: server.origin, projectId: PROJECT, apiKey: KEY }, { load: () => saved, save: (seq) => (saved = seq) }, async (event) => {
    if (event.id === "evt_a" && failOnce) {
      failOnce = false;
      throw new Error("transient");
    }
    handled.push(event.id);
  });
  try {
    await waitFor(() => saved === 43);
    assert.deepEqual(handled, ["evt_a", "evt_b"]);
    assert.deepEqual(server.subscribes.slice(0, 2), [40, 40], "resubscribed from the last checkpoint, not past the failure");
  } finally {
    stream.stop();
    server.close();
  }
});

test("events: an event that keeps failing is skipped after 3 attempts so later messages still arrive", async () => {
  const server = await fakeEventServer([{ id: "evt_bad", seq: 41 }, { id: "evt_ok", seq: 42 }]);
  let saved = 40;
  let badAttempts = 0;
  const handled: string[] = [];
  const stream = startEvents({ origin: server.origin, projectId: PROJECT, apiKey: KEY }, { load: () => saved, save: (seq) => (saved = seq) }, async (event) => {
    if (event.id === "evt_bad") {
      badAttempts++;
      throw new Error("poison");
    }
    handled.push(event.id);
  });
  try {
    await waitFor(() => saved === 42, 15000);
    assert.equal(badAttempts, 3);
    assert.deepEqual(handled, ["evt_ok"]);
  } finally {
    stream.stop();
    server.close();
  }
});
