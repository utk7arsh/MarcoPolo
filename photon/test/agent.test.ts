import assert from "node:assert/strict";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { extname, join } from "node:path";
import { test } from "node:test";
import { MarcoAgent } from "../src/agent.js";
import type { Config } from "../src/config.js";
import { MarcoServerError, type LabelPost, type LabelRequest, type MarcoServerApi, type Registration } from "../src/marco-server.js";
import { Media } from "../src/media.js";
import { SimChannel, type SimPart } from "../src/sim.js";
import { Store } from "../src/store.js";

const MOM = "+13105550101";
const JPEG = Buffer.from([0xff, 0xd8, 0xff, 0xe0, 0x00, 0x10, 0x4a, 0x46, 0x49, 0x46]);
const VOICE = Buffer.from("not really audio");
const photo = (): SimPart => ({ image: JPEG, mimeType: "image/jpeg" });
const request = (touchId: string): LabelRequest => ({ type: "label_request", touch_id: touchId, crop_url: `/v1/touch/${touchId}/crop.jpg`, question: "What is this?" });

/** Records what the bridge posts, and answers like server/marco/stub.py. */
class FakeServer implements MarcoServerApi {
  crops: string[] = [];
  labels: Array<LabelPost & { audioExt: string | null }> = [];
  items: Array<{ name: string; photoExt: string }> = [];
  quality: Registration["quality"] = "ok";
  /** Transient failures (network down) for the next N label posts. */
  failLabels = 0;
  /** HTTP status to reject the next label post with (e.g. 404 when the server forgot the touch). */
  rejectLabel: number | null = null;
  private seq = 0;

  async getCrop(cropUrl: string) {
    this.crops.push(cropUrl);
    return JPEG;
  }

  async postLabel(label: LabelPost) {
    if (this.failLabels > 0) {
      this.failLabels--;
      throw new TypeError("fetch failed");
    }
    if (this.rejectLabel) {
      const status = this.rejectLabel;
      this.rejectLabel = null;
      throw new MarcoServerError(`POST /v1/labels: HTTP ${status}`, status);
    }
    this.labels.push({ ...label, audioExt: label.audioPath ? extname(label.audioPath) : null });
    return { status: "ok", item_id: label.itemId ?? `srv_${label.touchId}` };
  }

  async postItem(name: string, photoPath: string): Promise<Registration> {
    this.items.push({ name, photoExt: extname(photoPath) });
    return this.quality === "ok" ? { item_id: `srv_item_${++this.seq}`, quality: "ok", reason: "" } : { item_id: null, quality: "retake", reason: "photo too small" };
  }
}

function setup(transcripts: Array<string | null> = []) {
  const dir = mkdtempSync(join(tmpdir(), "marco-photon-"));
  const config: Config = {
    mode: "sim",
    photon: null,
    port: 0,
    dataDir: dir,
    userName: "Dad",
    caretakerNames: new Map([[MOM, "Mom"]]),
    primaryCaretaker: null,
    elevenLabsKey: null,
    sttModel: "scribe_v2",
    marcoServerUrl: "http://marco.test",
    promptDelayMs: 30,
  };
  const store = new Store(dir);
  const sim = new SimChannel();
  const server = new FakeServer();
  let transcriptions = 0;
  const agent = new MarcoAgent({
    config,
    store,
    media: new Media(dir),
    channel: sim,
    transcribe: async () => (transcriptions++, transcripts.shift() ?? null),
    server,
  });

  const say = async (parts: SimPart[], replyTo?: string) => {
    const message = sim.inbound(MOM, parts, replyTo ? { replyTo } : {});
    await agent.handle(message);
    await agent.settled();
    return message;
  };
  const texts = () => sim.outbox.filter((o) => o.type === "text").map((o) => o.text ?? "");
  const lastText = () => texts().at(-1) ?? "";
  return { store, sim, server, agent, say, texts, lastText, transcriptions: () => transcriptions };
}

/** Links Mom, delivers one label_request, and returns the id of the photo she received. */
async function askMom(t: ReturnType<typeof setup>, touchId: string) {
  if (!t.store.caretaker(MOM)) await t.say([{ text: "hi Marco" }]);
  const result = await t.agent.onLabelRequest(request(touchId));
  assert.equal(result.status, "sent");
  return { result: result as Extract<typeof result, { status: "sent" }>, photoId: t.sim.outbox.findLast((o) => o.type === "attachment")!.id };
}

test("first text links the caretaker and gets a text-only welcome", async () => {
  const t = setup();
  await t.say([{ text: "hi Marco" }]);
  assert.equal(t.store.caretaker(MOM)?.name, "Mom");
  assert.equal(t.sim.outbox.length, 1);
  assert.match(t.lastText(), /^Hi Mom! I'm Marco, Dad's home helper/);
});

test("ask: a label_request fetches the crop and texts it to the caretaker", async () => {
  const t = setup();
  await askMom(t, "t1");
  assert.deepEqual(t.server.crops, ["/v1/touch/t1/crop.jpg"]);
  const sent = t.sim.outbox.slice(-2);
  assert.deepEqual(sent.map((o) => [o.type, o.mime_type ?? null]), [["attachment", "image/jpeg"], ["text", null]]);
  assert.match(sent[1]?.text ?? "", /^Dad just touched this and asked what it is\./);
});

test("ask: a swipe-reply voice memo is posted to /v1/labels with the touch_id before Mom is thanked", async () => {
  const t = setup(["That's the cumin, love."]);
  const { photoId } = await askMom(t, "t1");
  await t.say([{ voice: VOICE }], photoId);
  assert.equal(t.server.labels.length, 1);
  const [label] = t.server.labels;
  assert.deepEqual({ touchId: label?.touchId, itemId: label?.itemId, name: label?.name, text: label?.text }, {
    touchId: "t1",
    itemId: undefined,
    name: "cumin",
    text: "That's the cumin, love.",
  });
  assert.ok(label?.audioExt, "the voice memo is attached");
  const confirmation = t.sim.outbox.at(-1)!;
  assert.equal(confirmation.text, "Got it: cumin. Dad will hear your voice next time.");
  assert.equal(confirmation.reply_to, photoId);
  assert.ok(t.sim.outbox.some((o) => o.type === "reaction" && o.emoji === "❤️"));
});

test("ask: a typed name, then a voice memo, becomes §5's 'voice note after the name' on the same item_id", async () => {
  const t = setup([null]);
  const { photoId } = await askMom(t, "t1");
  await t.say([{ text: "That's the cumin, love" }], photoId);
  await t.say([{ voice: VOICE }]);
  assert.equal(t.server.labels.length, 2);
  const [first, second] = t.server.labels;
  assert.deepEqual([first?.touchId, first?.name, first?.text, first?.audioExt], ["t1", "cumin", "That's the cumin, love", null]);
  assert.deepEqual([second?.itemId, second?.touchId, second?.name, second?.text], ["srv_t1", undefined, "cumin", "That's the cumin, love"]);
  assert.ok(second?.audioExt);
  assert.equal(t.lastText(), "Added your voice to the cumin. Dad will hear it next time.");
});

test("ask: an untranscribed voice memo waits for a name, then goes with it", async () => {
  const t = setup([null]);
  const { photoId } = await askMom(t, "t1");
  await t.say([{ voice: VOICE }], photoId);
  assert.equal(t.server.labels.length, 0, "the server needs a name");
  assert.match(t.lastText(), /^Got your voice note\. What's it called\?/);
  await t.say([{ text: "paprika" }]);
  assert.equal(t.server.labels.length, 1);
  assert.deepEqual([t.server.labels[0]?.touchId, t.server.labels[0]?.name], ["t1", "paprika"]);
  assert.ok(t.server.labels[0]?.audioExt, "the earlier voice memo goes with the name");
});

test("ask: unthreaded answers go to the oldest request; a swipe-reply picks one", async () => {
  const t = setup();
  await askMom(t, "t1");
  const { photoId: secondPhoto } = await askMom(t, "t2");
  await t.say([{ text: "paprika" }], secondPhoto);
  await t.say([{ text: "cumin" }]);
  assert.deepEqual(t.server.labels.map((l) => [l.touchId, l.name]), [["t2", "paprika"], ["t1", "cumin"]]);
});

test("ask: a correction relabels the server's item", async () => {
  const t = setup();
  const { photoId } = await askMom(t, "t1");
  await t.say([{ text: "paprika" }]);
  await t.say([{ text: "no wait, it's cumin" }], photoId);
  assert.deepEqual(t.server.labels.map((l) => [l.touchId ?? null, l.itemId ?? null, l.name]), [["t1", null, "paprika"], [null, "srv_t1", "cumin"]]);
  assert.equal(t.lastText(), 'Updated: "cumin".');
});

test("ask: 'I don't know' posts nothing", async () => {
  const t = setup();
  await askMom(t, "t1");
  await t.say([{ text: "I don't know, sorry" }]);
  assert.equal(t.server.labels.length, 0);
  assert.equal(t.lastText(), "No problem. I'll let Dad know you weren't sure.");
});

test("ask: if the server forgot the touch (404), the item is registered from the crop and labelled", async () => {
  const t = setup();
  await askMom(t, "t1");
  t.server.rejectLabel = 404;
  await t.say([{ text: "cumin" }]);
  assert.deepEqual(t.server.items, [{ name: "cumin", photoExt: ".jpg" }]);
  assert.deepEqual(t.server.labels.map((l) => [l.itemId, l.name]), [["srv_item_1", "cumin"]]);
  assert.equal(t.lastText(), "Got it: cumin. I'll tell Dad.");
});

test("ask: a read receipt on the photo is recorded", async () => {
  const t = setup();
  const { result, photoId } = await askMom(t, "t1");
  await t.agent.handle(t.sim.readReceipt(MOM, photoId));
  assert.ok(t.store.question(result.request_id)?.seenAt);
});

test("ask: no caretaker yet, and a repeated label_request, send nothing extra", async () => {
  const t = setup();
  assert.equal((await t.agent.onLabelRequest(request("t1"))).status, "no_caretaker");
  await askMom(t, "t1");
  const photos = t.sim.outbox.filter((o) => o.type === "attachment").length;
  assert.equal((await t.agent.onLabelRequest(request("t1"))).status, "already_asked");
  assert.equal(t.sim.outbox.filter((o) => o.type === "attachment").length, photos);
});

test("teach: a photo with a caption is registered with POST /v1/items as JPEG", async () => {
  const t = setup();
  await t.say([{ text: "hi" }]);
  await t.say([photo(), { text: "Dad's keys" }]);
  assert.deepEqual(t.server.items, [{ name: "keys", photoExt: ".jpg" }]);
  assert.equal(t.server.labels.length, 0, "a caption alone is just a registration (§5)");
  assert.equal(t.store.items()[0]?.serverItemId, "srv_item_1");
  assert.equal(t.lastText(), 'Saved "keys". Dad can ask me for it by name now.');
});

test("teach: a bare photo gets a threaded prompt; a voice memo names it and is added as its label", async () => {
  const t = setup(["these are Dad's reading glasses"]);
  await t.say([{ text: "hi" }]);
  const photoMsg = await t.say([photo()]);
  const prompt = t.sim.outbox.at(-1)!;
  assert.deepEqual([prompt.text, prompt.reply_to], ["Got it. What is this? Reply with its name or a voice memo.", photoMsg.id]);
  await t.say([{ voice: VOICE }]);
  assert.deepEqual(t.server.items.map((i) => i.name), ["reading glasses"]);
  assert.equal(t.server.labels.length, 1);
  assert.deepEqual([t.server.labels[0]?.itemId, t.server.labels[0]?.name, t.server.labels[0]?.text], ["srv_item_1", "reading glasses", "these are Dad's reading glasses"]);
  assert.match(t.lastText(), /^Saved "reading glasses" with your voice/);
});

test("teach: a caption arriving as its own message beats the prompt", async () => {
  const t = setup();
  await t.say([{ text: "hi" }]);
  await t.agent.handle(t.sim.inbound(MOM, [photo()]));
  await t.agent.handle(t.sim.inbound(MOM, [{ text: "cumin" }]));
  await t.agent.settled();
  assert.deepEqual(t.server.items.map((i) => i.name), ["cumin"]);
  assert.ok(!t.texts().some((s) => s.includes("What is this?")));
});

test("teach: a retake from the server is passed on, and nothing is labelled", async () => {
  const t = setup();
  await t.say([{ text: "hi" }]);
  t.server.quality = "retake";
  await t.say([photo(), { text: "the TV remote" }]);
  assert.equal(t.server.labels.length, 0);
  assert.equal(t.lastText(), "I can't see the TV remote clearly in that photo. Could you send another, a bit closer and on a plain surface?");
});

test("duplicate deliveries are handled once, and thanks gets a tapback not a text", async () => {
  const t = setup();
  for (let i = 0; i < 2; i++) await t.agent.handle(t.sim.inbound(MOM, [{ text: "hi" }], { id: "dup-1" }));
  assert.equal(t.texts().length, 1);
  await t.say([{ text: "thanks!" }]);
  assert.equal(t.texts().length, 1);
  assert.equal(t.sim.outbox.at(-1)?.type, "reaction");
});

test("retry: a failed welcome is sent on redelivery, once", async () => {
  const t = setup();
  const hi = t.sim.inbound(MOM, [{ text: "hi Marco" }]);
  t.sim.failSends = 1;
  await assert.rejects(t.agent.handle(hi));
  await t.agent.handle(hi); // Photon replays the event from the last checkpoint
  await t.agent.handle(hi); // and a duplicate delivery is ignored
  assert.equal(t.texts().length, 1);
  assert.match(t.lastText(), /^Hi Mom!/);
});

test("retry: the server being down fails the event; the replay posts once and thanks Mom once", async () => {
  const t = setup(["That's the cumin, love."]);
  const { photoId } = await askMom(t, "t1");
  const memo = t.sim.inbound(MOM, [{ voice: VOICE }], { replyTo: photoId });
  t.server.failLabels = 1;
  await assert.rejects(t.agent.handle(memo));
  assert.equal(t.server.labels.length, 0);
  assert.ok(!t.texts().some((s) => s.startsWith("Got it")), "Mom isn't thanked for something that didn't arrive");
  await t.agent.handle(memo);
  assert.equal(t.server.labels.length, 1);
  assert.equal(t.transcriptions(), 1, "not transcribed twice");
  assert.equal(t.texts().filter((s) => s.startsWith("Got it: cumin")).length, 1);
});

test("retry: a failed confirmation is re-sent without posting the label again", async () => {
  const t = setup(["That's the cumin, love."]);
  const { photoId } = await askMom(t, "t1");
  const memo = t.sim.inbound(MOM, [{ voice: VOICE }], { replyTo: photoId });
  t.sim.failSends = 2; // the threaded confirmation and its plain-send fallback
  await assert.rejects(t.agent.handle(memo));
  assert.equal(t.server.labels.length, 1, "the phone already has the label");
  await t.agent.handle(memo);
  assert.equal(t.server.labels.length, 1);
  assert.equal(t.texts().filter((s) => s.startsWith("Got it: cumin")).length, 1);
});

test("retry: a redelivered photo with a caption is registered once", async () => {
  const t = setup();
  await t.say([{ text: "hi" }]);
  const keys = t.sim.inbound(MOM, [photo(), { text: "Dad's keys" }]);
  t.sim.failSends = 2;
  await assert.rejects(t.agent.handle(keys));
  await t.agent.handle(keys);
  assert.deepEqual(t.server.items.map((i) => i.name), ["keys"]);
  assert.equal(t.store.items().length, 1);
  assert.equal(t.texts().filter((s) => s.startsWith('Saved "keys"')).length, 1);
});
