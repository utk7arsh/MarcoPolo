// The §5 client against local fakes: exact multipart fields, URL handling, error mapping, and the /v1/photon socket.
import assert from "node:assert/strict";
import { mkdtempSync, writeFileSync } from "node:fs";
import { createServer, type IncomingMessage, type Server } from "node:http";
import type { AddressInfo } from "node:net";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { WebSocketServer } from "ws";
import { connectPhotonSocket, MarcoServer, MarcoServerError, photonSocketUrl, type LabelRequest } from "../src/marco-server.js";

interface Seen {
  method: string;
  url: string;
  type: string;
  form: FormData | null;
}

async function fakeServer(reply: (req: IncomingMessage) => { status: number; body: unknown; type?: string }) {
  const seen: Seen[] = [];
  const server = createServer(async (req, res) => {
    const chunks: Buffer[] = [];
    for await (const c of req) chunks.push(c as Buffer);
    const type = String(req.headers["content-type"] ?? "");
    const form = type.startsWith("multipart/") ? await new Response(Buffer.concat(chunks), { headers: { "content-type": type } }).formData() : null;
    seen.push({ method: req.method!, url: req.url!, type, form });
    const r = reply(req);
    res.writeHead(r.status, { "content-type": r.type ?? "application/json" });
    res.end(Buffer.isBuffer(r.body) ? r.body : JSON.stringify(r.body));
  });
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  return { base: `http://127.0.0.1:${(server.address() as AddressInfo).port}`, seen, close: () => server.close() };
}

const files = () => {
  const dir = mkdtempSync(join(tmpdir(), "marco-client-"));
  const voice = join(dir, "voice_1.m4a");
  const photo = join(dir, "photo_1.jpg");
  writeFileSync(voice, Buffer.from("m4a-bytes"));
  writeFileSync(photo, Buffer.from([0xff, 0xd8, 0xff, 0xe0]));
  return { voice, photo };
};

test("postLabel sends §5's multipart fields: touch_id, name, text, audio with its filename", async () => {
  const api = await fakeServer(() => ({ status: 200, body: { status: "ok", item_id: "i1" } }));
  try {
    const { voice } = files();
    const res = await new MarcoServer(api.base).postLabel({ touchId: "t1", name: "cumin", text: "That's the cumin, love", audioPath: voice });
    assert.deepEqual(res, { status: "ok", item_id: "i1" });
    const [req] = api.seen;
    assert.deepEqual([req?.method, req?.url], ["POST", "/v1/labels"]);
    assert.deepEqual([...req!.form!.keys()].sort(), ["audio", "name", "text", "touch_id"]);
    assert.equal(req!.form!.get("touch_id"), "t1");
    assert.equal(req!.form!.get("name"), "cumin");
    const audio = req!.form!.get("audio") as File;
    assert.equal(audio.name, "voice_1.m4a", "the server keeps the extension from the filename");
    assert.equal(audio.type, "audio/mp4");
    assert.equal(await audio.text(), "m4a-bytes");
  } finally {
    api.close();
  }
});

test("postLabel for a follow-up sends item_id instead of touch_id, and no audio field when there is none", async () => {
  const api = await fakeServer(() => ({ status: 200, body: { status: "ok", item_id: "i1" } }));
  try {
    await new MarcoServer(api.base).postLabel({ itemId: "i1", name: "cumin", text: "cumin" });
    assert.deepEqual([...api.seen[0]!.form!.keys()].sort(), ["item_id", "name", "text"]);
  } finally {
    api.close();
  }
});

test("postItem sends name and a JPEG photo; getCrop resolves the server's relative crop_url", async () => {
  const api = await fakeServer((req) =>
    req.url?.startsWith("/v1/touch/") ? { status: 200, body: Buffer.from([0xff, 0xd8, 1]), type: "image/jpeg" } : { status: 200, body: { item_id: "i2", quality: "ok", reason: "" } },
  );
  try {
    const { photo } = files();
    const client = new MarcoServer(`${api.base}/`);
    assert.deepEqual(await client.postItem("keys", photo), { item_id: "i2", quality: "ok", reason: "" });
    const form = api.seen[0]!.form!;
    assert.deepEqual([...form.keys()].sort(), ["name", "photo"]);
    assert.equal((form.get("photo") as File).type, "image/jpeg");
    assert.deepEqual([...(await client.getCrop("/v1/touch/t1/crop.jpg"))], [0xff, 0xd8, 1]);
    assert.equal(api.seen[1]?.url, "/v1/touch/t1/crop.jpg");
  } finally {
    api.close();
  }
});

test("errors: 403 explains the allow-list, 404 is permanent, 500 and 429 are worth retrying", async () => {
  let status = 403;
  const api = await fakeServer(() => ({ status, body: { detail: "nope" } }));
  try {
    const client = new MarcoServer(api.base);
    const failure = async () => {
      try {
        await client.postLabel({ touchId: "t1", name: "cumin" });
      } catch (err) {
        return err as MarcoServerError;
      }
      throw new Error("expected a failure");
    };
    const forbidden = await failure();
    assert.ok(forbidden instanceof MarcoServerError);
    assert.match(forbidden.message, /TAILSCALE_ALLOWED_LOGINS/);
    assert.equal(forbidden.permanent, true);
    status = 404;
    assert.equal((await failure()).permanent, true);
    status = 500;
    assert.equal((await failure()).permanent, false);
    status = 429;
    assert.equal((await failure()).permanent, false);
  } finally {
    api.close();
  }
});

test("photonSocketUrl turns the tailscale serve URL into its wss:// /v1/photon socket", () => {
  assert.equal(photonSocketUrl("https://marco-gpu.tail1234.ts.net/"), "wss://marco-gpu.tail1234.ts.net/v1/photon");
  assert.equal(photonSocketUrl("http://127.0.0.1:8000"), "ws://127.0.0.1:8000/v1/photon");
});

test("the /v1/photon socket delivers label_requests in order, ignores other messages, and reconnects", async () => {
  const http: Server = createServer();
  const wss = new WebSocketServer({ server: http, path: "/v1/photon" });
  let connections = 0;
  wss.on("connection", (ws) => {
    connections++;
    if (connections === 1) {
      ws.send(JSON.stringify({ type: "label_request", touch_id: "t1", crop_url: "/v1/touch/t1/crop.jpg" }));
      ws.send(JSON.stringify({ type: "something_else" }));
      ws.send(JSON.stringify({ type: "label_request", touch_id: "t2", crop_url: "/v1/touch/t2/crop.jpg" }));
      setTimeout(() => ws.close(1011, "server restart"), 50);
    } else {
      ws.send(JSON.stringify({ type: "label_request", touch_id: "t3", crop_url: "/v1/touch/t3/crop.jpg" }));
    }
  });
  await new Promise<void>((resolve) => http.listen(0, "127.0.0.1", resolve));
  const base = `http://127.0.0.1:${(http.address() as AddressInfo).port}`;
  const got: string[] = [];
  const socket = connectPhotonSocket(base, async (r: LabelRequest) => {
    await new Promise((resolve) => setTimeout(resolve, 10)); // a slow handler must not reorder requests
    got.push(r.touch_id);
  });
  try {
    for (let i = 0; i < 200 && got.length < 3; i++) await new Promise((resolve) => setTimeout(resolve, 25));
    assert.deepEqual(got, ["t1", "t2", "t3"]);
    assert.equal(connections, 2, "reconnected after the server closed the socket");
    assert.equal(socket.connected, true);
  } finally {
    socket.close();
    wss.close();
    http.close();
  }
});
