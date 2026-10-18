// End to end against the real Marco server (server/, MARCO_MODE=stub, loopback, AUTH_TEST_BYPASS=1), with this
// service running as its own process in sim mode (the caretaker is played over /dev/inbound):
//   phone asks "what is this?" -> server label_request on /v1/photon -> Photon texts the crop to Mom ->
//   Mom replies by text, then by voice memo -> POST /v1/labels -> the phone gets label_ready with playable audio;
//   Mom sends a setup photo -> POST /v1/items -> GET /v1/items has it;
//   the server restarts -> the labels, voice memo and registration are still there (marco/registry.py);
//   Mom texts /restart -> DELETE /v1/items?source=photon -> none of Photon's items remain, even after another restart.
// Skips unless a Python with the server's stub dependencies is available (MARCO_SERVER_PYTHON, server/.venv or poc/.venv).
import assert from "node:assert/strict";
import { execFileSync, spawn, spawnSync, type ChildProcess } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync } from "node:fs";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { deflateRawSync } from "node:zlib";

const PHOTON_DIR = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const SERVER_DIR = resolve(PHOTON_DIR, "..", "server");
const MOM = "+13105550101";

function serverPython(): string | null {
  const candidates = [process.env.MARCO_SERVER_PYTHON, join(SERVER_DIR, ".venv/bin/python"), resolve(SERVER_DIR, "../poc/.venv/bin/python")];
  for (const py of candidates) {
    if (!py || !existsSync(py)) continue;
    const ok = spawnSync(py, ["-c", "import fastapi, uvicorn, multipart, PIL, numpy"], { stdio: "ignore" }).status === 0;
    if (ok) return py;
  }
  return null;
}
const has = (bin: string) => spawnSync("which", [bin], { stdio: "ignore" }).status === 0;
const PYTHON = serverPython();
const SKIP = !PYTHON ? "no Python with the server's stub dependencies (set MARCO_SERVER_PYTHON)" : !has("ffmpeg") ? "needs ffmpeg for fixtures" : false;

const freePort = () =>
  new Promise<number>((done) => {
    const s = createServer().listen(0, "127.0.0.1", () => {
      const port = (s.address() as { port: number }).port;
      s.close(() => done(port));
    });
  });

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
async function waitFor<T>(what: string, fn: () => Promise<T | undefined | null | false> | T | undefined | null | false, ms = 20_000): Promise<T> {
  const until = Date.now() + ms;
  while (Date.now() < until) {
    try {
      const v = await fn();
      if (v) return v;
    } catch {
      // not ready yet
    }
    await sleep(100);
  }
  throw new Error(`timed out waiting for ${what}`);
}

function start(cmd: string, args: string[], cwd: string, env: Record<string, string>, logs: string[]): ChildProcess {
  const child = spawn(cmd, args, { cwd, env: { ...process.env, ...env }, stdio: ["ignore", "pipe", "pipe"] });
  child.stdout?.on("data", (d) => logs.push(String(d)));
  child.stderr?.on("data", (d) => logs.push(String(d)));
  return child;
}

/** One valid §3.1 frame: a 960x720 sensor-orientation JPEG, depth and confidence, identity pose. */
function frameForm(jpeg: Buffer): FormData {
  const n = 256 * 192;
  const depth = Buffer.alloc(n * 2);
  for (let i = 0; i < n; i++) depth.writeUInt16LE(0x3e00, i * 2); // float16 1.5 m
  const conf = Buffer.alloc(n, 2);
  const meta = {
    session_id: "photon-e2e",
    map_id: "m1",
    frame_id: 1,
    t_device: 1000,
    t_wall: new Date().toISOString(),
    tracking: "normal",
    camera_transform: [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1],
    intrinsics: [1500, 0, 0, 0, 1500, 0, 960, 720, 1],
    image_resolution: [1920, 1440],
    jpeg_scale: 0.5,
  };
  const form = new FormData();
  form.append("meta", JSON.stringify(meta));
  form.append("image", new Blob([new Uint8Array(jpeg)], { type: "image/jpeg" }), "f.jpg");
  form.append("depth", new Blob([new Uint8Array(deflateRawSync(depth))]), "f.depth");
  form.append("confidence", new Blob([new Uint8Array(deflateRawSync(conf))]), "f.conf");
  return form;
}

test("end to end with the real Marco server: label_request -> iMessage -> /v1/labels -> label_ready; setup photo -> /v1/items; persistence; /restart", { skip: SKIP, timeout: 180_000 }, async () => {
  const dir = mkdtempSync(join(tmpdir(), "marco-e2e-"));
  const jpegPath = join(dir, "frame.jpg");
  execFileSync("ffmpeg", ["-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=960x720", "-frames:v", "1", jpegPath]);
  const memoPath = join(dir, "memo.caf");
  execFileSync("ffmpeg", ["-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=1", "-c:a", "libopus", "-ar", "48000", memoPath]);
  let setupPhoto = readFileSync(jpegPath);
  let setupMime = "image/jpeg";
  if (has("sips")) {
    execFileSync("sips", ["-s", "format", "heic", jpegPath, "--out", join(dir, "keys.heic")], { stdio: "ignore" });
    setupPhoto = readFileSync(join(dir, "keys.heic"));
    setupMime = "image/heic";
  }

  const serverPort = await freePort();
  const photonPort = await freePort();
  const base = `http://127.0.0.1:${serverPort}`;
  const bridge = `http://127.0.0.1:${photonPort}`;
  const logs: string[] = [];
  const children: ChildProcess[] = [];
  let phone: WebSocket | null = null;
  try {
    const serverEnv = { AUTH_TEST_BYPASS: "1", MARCO_MODE: "stub", MARCO_AUTH: "closed", MARCO_DATA: join(dir, "server-data"), HOST: "127.0.0.1", PORT: String(serverPort) };
    let server = start(PYTHON!, ["-m", "marco.app"], SERVER_DIR, serverEnv, logs);
    children.push(server);
    const restartServer = async () => {
      const exited = new Promise((r) => server.once("exit", r));
      server.kill("SIGTERM");
      await exited;
      server = start(PYTHON!, ["-m", "marco.app"], SERVER_DIR, serverEnv, logs);
      children.push(server);
      await waitFor("the Marco server after a restart", async () => (await fetch(`${base}/v1/items`)).ok);
    };
    await waitFor("the Marco server", async () => (await fetch(`${base}/v1/items`)).ok);
    assert.equal((await fetch(`${base}/v1/frames`, { method: "POST", body: frameForm(readFileSync(jpegPath)) })).status, 202);

    // Every variable photon/.env might set is given explicitly, so the developer's real credentials never load here.
    children.push(
      start(
        process.execPath,
        ["--import", "tsx", "src/index.ts"],
        PHOTON_DIR,
        {
          PHOTON_MODE: "sim",
          PHOTON_PROJECT_ID: "",
          PHOTON_API_KEY: "",
          PORT: String(photonPort),
          DATA_DIR: join(dir, "photon-data"),
          MARCO_SERVER_URL: base,
          CARETAKERS: `${MOM}=Mom`,
          PRIMARY_CARETAKER: "",
          MARCO_USER_NAME: "Grandpa",
          ELEVENLABS_API_KEY: "",
          PROMPT_DELAY_MS: "100",
        },
        logs,
      ),
    );
    await waitFor("Photon connected to /v1/photon", async () => (await (await fetch(`${bridge}/health`)).json()).marco_server.connected);

    const mom = async (body: Record<string, string>) => {
      const res = await fetch(`${bridge}/dev/inbound`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ from: MOM, ...body }) });
      assert.equal(res.status, 200, await res.clone().text());
      return ((await res.json()) as { marco_sent: Array<{ type: string; text?: string }> }).marco_sent;
    };
    assert.match((await mom({ text: "hi Marco" })).find((m) => m.type === "text")?.text ?? "", /^Hi Mom! I'm Marco, Grandpa's home helper/);

    // The phone: pose, then "what is this?".
    const fromServer: Array<Record<string, unknown>> = [];
    phone = new WebSocket(`ws://127.0.0.1:${serverPort}/v1/phone`);
    phone.onmessage = (ev) => fromServer.push(JSON.parse(String(ev.data)));
    await waitFor("the phone socket", () => phone?.readyState === WebSocket.OPEN);
    phone.send(JSON.stringify({ type: "pose", session_id: "photon-e2e", map_id: "m1", t_device: 1000, camera_transform: [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1], head_yaw_deg: 0, head_source: "phone" }));
    phone.send(JSON.stringify({ type: "query", session_id: "photon-e2e", query_id: "q1", kind: "what_is_this" }));
    const unknown = await waitFor("the what_is_this answer", () => fromServer.find((m) => m.query_id === "q1"));
    assert.equal(unknown.status, "unknown");

    // Photon got label_request, fetched the crop and texted it to Mom.
    const outbox = async () => (await (await fetch(`${bridge}/dev/outbox`)).json()) as Array<{ id: string; type: string; mime_type?: string; text?: string }>;
    const cropMsg = await waitFor("the crop on Mom's iMessage", async () => (await outbox()).find((m) => m.type === "attachment"));
    assert.equal(cropMsg.mime_type, "image/jpeg");

    // Mom answers by text (swipe-reply), then adds a voice memo.
    const thanks = await mom({ text: "That's the cumin, love", reply_to: cropMsg.id });
    assert.equal(thanks.find((m) => m.type === "text")?.text, "Got it: cumin. I'll tell Grandpa.");
    const first = await waitFor("label_ready (text)", () => fromServer.find((m) => m.type === "label_ready"));
    assert.deepEqual([first.name, first.label_text, first.label_audio_url], ["cumin", "That's the cumin, love", null]);

    const added = await mom({ voice_base64: readFileSync(memoPath).toString("base64"), voice_mime: "audio/x-caf" });
    assert.equal(added.find((m) => m.type === "text")?.text, "Added your voice to the cumin. Grandpa will hear it next time.");
    const second = await waitFor("label_ready (voice)", () => fromServer.filter((m) => m.type === "label_ready")[1]);
    assert.equal(second.item_id, first.item_id, "the voice note lands on the same item");
    const audio = await fetch(`${base}${second.label_audio_url}`);
    assert.equal(audio.headers.get("content-type"), "audio/mp4", "sent as m4a, which the phone and the dashboard can both play");
    assert.equal(Buffer.from(await audio.arrayBuffer()).toString("latin1", 4, 8), "ftyp");

    // The phone asks again: now the server knows it, in Mom's voice.
    phone.send(JSON.stringify({ type: "query", session_id: "photon-e2e", query_id: "q2", kind: "what_is_this" }));
    const known = await waitFor("the second what_is_this answer", () => fromServer.find((m) => m.query_id === "q2"));
    assert.deepEqual([known.status, known.name, known.label_audio_url], ["known", "cumin", second.label_audio_url]);

    // Teach: a setup photo with a caption is registered on the server.
    const saved = await mom({ image_base64: setupPhoto.toString("base64"), image_mime: setupMime, text: "These are Grandpa's keys" });
    assert.equal(saved.find((m) => m.type === "text")?.text, 'Saved "keys". Grandpa can ask me for it by name now.');
    type ServerItem = { item_id: string; name: string; source?: string; label_text?: string; label_audio_url?: string | null };
    const serverItems = async () => (await (await fetch(`${base}/v1/items`)).json()) as ServerItem[];
    const fromPhoton = async () => (await serverItems()).filter((i) => i.source === "photon");
    assert.deepEqual((await fromPhoton()).map((i) => i.name).sort(), ["cumin", "keys"]);

    // Persistence: a fresh server process on the same data folder (what a redeploy is) still has them.
    await restartServer();
    const kept = await fromPhoton();
    assert.deepEqual(kept.map((i) => i.name).sort(), ["cumin", "keys"]);
    const cumin = kept.find((i) => i.name === "cumin")!;
    assert.equal(cumin.item_id, first.item_id);
    assert.equal(cumin.label_text, "That's the cumin, love");
    const keptAudio = await fetch(`${base}${cumin.label_audio_url}`);
    assert.equal(keptAudio.headers.get("content-type"), "audio/mp4");
    assert.equal(Buffer.from(await keptAudio.arrayBuffer()).toString("latin1", 4, 8), "ftyp");
    await waitFor("Photon reconnected to /v1/photon", async () => (await (await fetch(`${bridge}/health`)).json()).marco_server.connected);

    // /restart from the caretaker's chat removes exactly what Photon added, for good.
    const cleared = (await mom({ text: "/restart" })).find((m) => m.type === "text")?.text ?? "";
    assert.match(cleared, /^Fresh start: I removed 2 labels from Marco \((cumin, keys|keys, cumin)\)\./);
    assert.deepEqual(await fromPhoton(), []);
    await restartServer();
    assert.deepEqual(await fromPhoton(), [], "still gone after a restart");
  } catch (err) {
    console.error(logs.join("").slice(-4000));
    throw err;
  } finally {
    phone?.close();
    for (const child of children) child.kill("SIGTERM");
    await sleep(300);
  }
});
