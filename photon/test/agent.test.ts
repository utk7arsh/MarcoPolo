import assert from "node:assert/strict";
import { mkdtempSync } from "node:fs";
import { createServer } from "node:http";
import type { AddressInfo } from "node:net";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { Readable } from "node:stream";
import { test } from "node:test";
import { MarcoAgent, Spaces } from "../src/agent.js";
import type { Config } from "../src/config.js";
import { EventBus, type StampedEvent } from "../src/events.js";
import { MarcoServer } from "../src/marco-server.js";
import { Media } from "../src/media.js";
import { SimPlatform, type SimPart } from "../src/sim.js";
import { Store } from "../src/store.js";

const MOM = "+13105550101";
const JPEG = Buffer.from([0xff, 0xd8, 0xff, 0xe0, 0x00, 0x10, 0x4a, 0x46, 0x49, 0x46]);
const VOICE = Buffer.from("not really audio");
const photo = (): SimPart => ({ image: JPEG, mimeType: "image/jpeg" });

function setup(transcripts: Array<string | null> = [], marcoServerUrl: string | null = null) {
  const dir = mkdtempSync(join(tmpdir(), "marco-photon-"));
  const config: Config = {
    mode: "sim",
    port: 0,
    dataDir: dir,
    publicBaseUrl: "http://bridge.test",
    bridgeToken: null,
    userName: "Dad",
    caretakerNames: new Map([[MOM, "Mom"]]),
    primaryCaretaker: null,
    elevenLabsKey: null,
    sttModel: "scribe_v2",
    marcoServerUrl,
    promptDelayMs: 30,
  };
  const store = new Store(dir);
  const media = new Media(dir, config.publicBaseUrl);
  const events = new EventBus();
  const sim = new SimPlatform();
  const seen: StampedEvent[] = [];
  events.subscribe((e) => seen.push(e));
  const agent = new MarcoAgent({
    config,
    store,
    media,
    events,
    spaces: new Spaces(async (_platform, id) => sim.spaceById(id)),
    transcribe: async () => transcripts.shift() ?? null,
    server: new MarcoServer(marcoServerUrl, media),
  });

  const say = async (parts: SimPart[], replyTo?: string) => {
    const [space, message] = sim.inbound(MOM, parts, replyTo ? { replyTo } : {});
    await agent.handle(space, message);
    await agent.settled();
    return message;
  };
  const texts = () => sim.outbox.filter((o) => o.type === "text").map((o) => o.text ?? "");
  const lastText = () => texts().at(-1) ?? "";
  const ofType = <T extends StampedEvent["type"]>(type: T) => seen.filter((e): e is Extract<StampedEvent, { type: T }> => e.type === type);
  return { store, sim, agent, seen, say, texts, lastText, ofType };
}

/** Links Mom and returns the photo + question message ids of one "what is this?" request. */
async function askMom(t: ReturnType<typeof setup>, itemId: string) {
  if (!t.store.caretaker(MOM)) await t.say([{ text: "hi Marco" }]);
  const result = await t.agent.requestLabel({ itemId, image: JPEG, mimeType: "image/jpeg" });
  assert.equal(result.status, "sent");
  const photoMsg = t.sim.outbox.findLast((o) => o.type === "attachment")!;
  return { result: result as Extract<typeof result, { status: "sent" }>, photoId: photoMsg.id };
}

test("first text links the caretaker and gets a text-only welcome", async () => {
  const t = setup();
  await t.say([{ text: "hi Marco" }]);
  assert.equal(t.store.caretaker(MOM)?.name, "Mom");
  assert.equal(t.sim.outbox.length, 1);
  assert.match(t.lastText(), /^Hi Mom! I'm Marco, Dad's home helper/);
  assert.equal(t.ofType("caretaker_linked").length, 1);
});

test("Flow A: a photo with a caption registers a named item", async () => {
  const t = setup();
  await t.say([{ text: "hi" }]);
  await t.say([photo(), { text: "Dad's keys" }]);
  const [item] = t.store.items();
  assert.equal(item?.name, "keys");
  assert.equal(item?.origin, "caretaker_photo");
  assert.equal(item?.label?.text, "Dad's keys");
  assert.ok(!t.texts().some((s) => s.includes("What is this?")));
  assert.match(t.lastText(), /Saved "keys"\. Dad can ask me for it by name now\./);
  assert.ok(t.sim.outbox.some((o) => o.type === "reaction" && o.emoji === "❤️"));
  const [ready] = t.ofType("label_ready");
  assert.equal(ready?.request_id, null);
  assert.match(ready?.item.photo_url ?? "", /^http:\/\/bridge\.test\/media\/photo_.*\.jpg$/);
});

test("Flow A: a bare photo gets a threaded prompt, then a voice memo names it", async () => {
  const t = setup(["these are Dad's reading glasses"]);
  await t.say([{ text: "hi" }]);
  const photoMsg = await t.say([photo()]);
  const prompt = t.sim.outbox.at(-1)!;
  assert.equal(prompt.text, "Got it. What is this? Reply with its name or a voice memo.");
  assert.equal(prompt.reply_to, photoMsg.id);

  await t.say([{ voice: VOICE }]);
  const [item] = t.store.items();
  assert.equal(item?.name, "reading glasses");
  assert.equal(item?.label?.transcript, "these are Dad's reading glasses");
  assert.ok(item?.label?.audio);
  assert.match(t.ofType("label_ready")[0]?.item.label?.audio_url ?? "", /^http:\/\/bridge\.test\/media\/voice_/);
  assert.match(t.lastText(), /Saved "reading glasses" with your voice/);
});

test("Flow A: a caption arriving as its own message beats the prompt", async () => {
  const t = setup();
  await t.say([{ text: "hi" }]);
  const [s1, m1] = t.sim.inbound(MOM, [photo()]);
  await t.agent.handle(s1, m1);
  const [s2, m2] = t.sim.inbound(MOM, [{ text: "cumin" }]);
  await t.agent.handle(s2, m2);
  await t.agent.settled();
  assert.equal(t.store.items()[0]?.name, "cumin");
  assert.ok(!t.texts().some((s) => s.includes("What is this?")));
});

test("Flow A: an untranscribed voice note stays playable and a follow-up text names it", async () => {
  const t = setup([null]);
  await t.say([{ text: "hi" }]);
  await t.say([photo()]);
  await t.say([{ voice: VOICE }]);
  assert.match(t.lastText(), /Saved your voice note\. Text me its name too/);
  assert.equal(t.store.items()[0]?.name, null);

  await t.say([{ text: "the remote" }]);
  const [item] = t.store.items();
  assert.equal(item?.name, "remote");
  assert.ok(item?.label?.audio, "the voice note is kept");
  assert.equal(t.lastText(), 'Saved "remote" with your voice. Dad can ask me for it by name now.');
});

test("Flow A: registers with the vision server (POC 26 /items) and relays a retake", async () => {
  const received: Array<{ name: unknown; hasPhoto: boolean }> = [];
  let quality: "ok" | "retake" = "ok";
  const server = createServer(async (req, res) => {
    const form = await new Request("http://x", { method: "POST", headers: req.headers as HeadersInit, body: Readable.toWeb(req) as ReadableStream, duplex: "half" } as RequestInit).formData();
    received.push({ name: form.get("name"), hasPhoto: form.get("photo") instanceof File });
    res.setHeader("content-type", "application/json");
    res.end(JSON.stringify(quality === "ok" ? { item_id: "srv-1", quality, reason: "", box: [1, 2, 3, 4] } : { item_id: null, quality, reason: "low score", box: null }));
  });
  await new Promise<void>((resolve) => server.listen(0, resolve));
  const { port } = server.address() as AddressInfo;
  try {
    const t = setup([], `http://127.0.0.1:${port}`);
    await t.say([{ text: "hi" }]);
    await t.say([photo(), { text: "Dad's keys" }]);
    assert.deepEqual(received, [{ name: "keys", hasPhoto: true }]);
    assert.equal(t.store.items()[0]?.serverItemId, "srv-1");

    quality = "retake";
    await t.say([photo(), { text: "the TV remote" }]);
    assert.equal(t.lastText(), "I can't see the TV remote clearly in that photo. Could you send another, a bit closer and on a plain surface?");
  } finally {
    server.close();
  }
});

test("Flow B: touch, photo to Mom, swipe-reply voice memo, label_ready for the phone", async () => {
  const t = setup(["That's the cumin, love."]);
  const { result, photoId } = await askMom(t, "jar-2");
  const sent = t.sim.outbox.slice(-2);
  assert.deepEqual(
    sent.map((o) => o.type),
    ["attachment", "text"],
  );
  assert.equal(sent[0]?.mime_type, "image/jpeg");
  assert.match(sent[1]?.text ?? "", /^Dad just touched this and asked what it is\./);
  assert.equal(t.ofType("label_request_sent")[0]?.request_id, result.request_id);

  await t.say([{ voice: VOICE }], photoId);
  const [ready] = t.ofType("label_ready");
  assert.equal(ready?.request_id, result.request_id);
  assert.equal(ready?.item.id, "jar-2");
  assert.equal(ready?.item.label?.name, "cumin");
  assert.equal(ready?.item.label?.author, "Mom");
  assert.ok(ready?.item.label?.audio_url);
  const confirmation = t.sim.outbox.at(-1)!;
  assert.equal(confirmation.text, "Got it: cumin. Dad will hear your voice next time.");
  assert.equal(confirmation.reply_to, photoId);
});

test("Flow B: unthreaded answers go to the oldest request; a swipe-reply picks one", async () => {
  const t = setup();
  await askMom(t, "jar-1");
  const { photoId: jar2Photo } = await askMom(t, "jar-2");
  await t.say([{ text: "paprika" }], jar2Photo);
  await t.say([{ text: "cumin" }]);
  assert.equal(t.store.item("jar-2")?.name, "paprika");
  assert.equal(t.store.item("jar-1")?.name, "cumin");
});

test("Flow B: a swipe-reply on an answered request corrects the label", async () => {
  const t = setup();
  const { photoId } = await askMom(t, "jar-1");
  await t.say([{ text: "paprika" }]);
  await t.say([{ text: "no wait, it's cumin" }], photoId);
  assert.equal(t.store.item("jar-1")?.name, "cumin");
  assert.equal(t.lastText(), 'Updated: "cumin".');
  assert.equal(t.ofType("label_ready").length, 2);
});

test("Flow B: 'I don't know' tells the phone instead of saving a label", async () => {
  const t = setup();
  const { result } = await askMom(t, "jar-1");
  await t.say([{ text: "I don't know, sorry" }]);
  assert.equal(t.ofType("label_unknown")[0]?.request_id, result.request_id);
  assert.equal(t.ofType("label_ready").length, 0);
  assert.equal(t.store.item("jar-1")?.label, null);
});

test("Flow B: a read receipt on the photo tells the phone Mom is looking", async () => {
  const t = setup();
  const { result, photoId } = await askMom(t, "jar-1");
  const [space, receipt] = t.sim.readReceipt(MOM, photoId);
  await t.agent.handle(space, receipt);
  assert.equal(t.ofType("label_request_seen")[0]?.request_id, result.request_id);
});

test("requestLabel guards: no caretaker, already asked, already labeled", async () => {
  const t = setup();
  assert.equal((await t.agent.requestLabel({ itemId: "jar-1", image: JPEG, mimeType: "image/jpeg" })).status, "no_caretaker");
  const { result } = await askMom(t, "jar-1");
  const again = await t.agent.requestLabel({ itemId: "jar-1", image: JPEG, mimeType: "image/jpeg" });
  assert.deepEqual(again, { ...result, status: "already_asked" });
  await t.say([{ text: "cumin" }]);
  assert.equal((await t.agent.requestLabel({ itemId: "jar-1", image: JPEG, mimeType: "image/jpeg" })).status, "already_labeled");
});

test("duplicate deliveries are handled once, and thanks gets a tapback not a text", async () => {
  const t = setup();
  for (let i = 0; i < 2; i++) {
    const [space, message] = t.sim.inbound(MOM, [{ text: "hi" }], { id: "dup-1" });
    await t.agent.handle(space, message);
  }
  assert.equal(t.texts().length, 1);
  await t.say([{ text: "thanks!" }]);
  assert.equal(t.texts().length, 1);
  assert.equal(t.sim.outbox.at(-1)?.type, "reaction");
});
