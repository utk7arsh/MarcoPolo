import type { Channel, Conversation, Inbound, Part } from "./channel.js";
import { normalizeHandle, type Config } from "./config.js";
import { log } from "./log.js";
import { MarcoServerError, PHOTON_SOURCE, type LabelRequest, type MarcoServerApi } from "./marco-server.js";
import type { Media } from "./media.js";
import { extractName, isDontKnow } from "./names.js";
import { now, stableId, type Caretaker, type Item, type Label, type LastAnswer, type Question, type Store } from "./store.js";

const HELP_COOLDOWN_MS = 10 * 60_000;
const LOVE = "❤️";
const LIKE = "👍";
/** Texted by a caretaker: remove every label Photon gave the Marco server, to test again from scratch. */
const RESTART = /^\/restart[\s.!]*$/i;

export interface AgentDeps {
  config: Config;
  store: Store;
  media: Media;
  channel: Channel;
  /** The Marco server (docs/INTERFACES.md §5): where labels and registrations go, and what tells the phone. */
  server: MarcoServerApi;
}

export type LabelRequestResult =
  | { status: "sent"; request_id: string; touch_id: string; caretaker: string }
  | { status: "already_asked"; request_id: string; touch_id: string; caretaker: string }
  | { status: "no_caretaker"; touch_id: string };

type MediaPart = Extract<Part, { type: "media" }>;
type Answer = { text: string; messageId: string };
type Outcome = NonNullable<LastAnswer["outcome"]>;

const isImage = (p: Part): p is MediaPart => p.type === "media" && /^image\//i.test(p.mimeType);
const isAudio = (p: Part): p is MediaPart => p.type === "media" && /^audio\//i.test(p.mimeType);
const sameConversation = (a: Conversation, b: Conversation) => a.spaceId === b.spaceId && a.agentId === b.agentId;

/**
 * Marco's side of the family conversation in iMessage, feeding the Marco server (docs/INTERFACES.md §5).
 *
 * Ask (Flow B): the server sends label_request on /v1/photon when the user asks "what is this?" about something
 * unknown. Marco texts the caretaker the crop; the typed reply goes to POST /v1/labels, and the
 * server tells the phone (label_ready).
 * Teach (Flow A): the caretaker texts a photo plus a typed name; it goes to POST /v1/items (corrections go to POST /v1/labels on that item).
 */
export class MarcoAgent {
  private readonly pending = new Set<Promise<void>>();

  constructor(private readonly deps: AgentDeps) {}

  /** Resolves once delayed follow-ups (photo prompts) have run. */
  async settled(): Promise<void> {
    while (this.pending.size) await Promise.allSettled([...this.pending]);
  }

  /**
   * Handles one inbound message. Safe to call again with the same message after a failure (Photon delivers at least
   * once and replays from the last checkpoint): it is marked processed only once fully handled, created records use
   * ids derived from the message, every send carries an idempotency key derived from it, and the server is called
   * at most once per answer.
   */
  async handle(message: Inbound): Promise<void> {
    const { store } = this.deps;
    if (store.isProcessed(message.id)) return;
    await this.process(message);
    store.markProcessed(message.id);
  }

  private async process(message: Inbound): Promise<void> {
    const { store, config } = this.deps;
    const handle = normalizeHandle(message.from);
    if (!config.caretakerNames.has(handle)) {
      log.warn("ignoring message from an unconfigured caretaker");
      return;
    }
    if (message.kind === "read") {
      if (message.parentId) this.onRead(handle, message.parentId);
      return;
    }

    let caretaker = store.caretaker(handle);
    const isNew = !caretaker || !caretaker.welcomedAt;
    if (!caretaker) {
      caretaker = this.link(handle, message.conversation);
    } else if (!sameConversation(caretaker.conversation, message.conversation)) {
      caretaker = store.upsertCaretaker({ ...caretaker, conversation: message.conversation });
    }
    if (!caretaker.welcomedAt) caretaker = await this.welcome(caretaker, message.id);

    const images = message.parts.filter(isImage);
    const audio = message.parts.find(isAudio) ?? null;
    const text = message.parts
      .flatMap((p) => (p.type === "text" ? [p.text.trim()] : []))
      .filter(Boolean)
      .join(" ");
    const answer: Answer = { text, messageId: message.id };
    if (audio && !text && !images.length) {
      await this.say(caretaker, "Please type the object's name. Voice labels are no longer supported.", { key: `typed-name:${message.id}` });
      return;
    }

    // Commands come first, so "/restart" is never taken as the answer to an open question.
    if (!images.length && !audio && RESTART.test(text)) return this.restart(caretaker, message.id);
    if (images.length) return this.onPhotos(caretaker, images, answer);
    if (!text) return;
    const question = this.pickQuestion(caretaker, message.parentId, answer);
    if (question) return this.answer(caretaker, question, answer);
    if (!isNew) await this.chat(caretaker, answer);
  }

  /** Flow B: the server's label_request. Texts the touched item's crop to the primary caretaker. */
  async onLabelRequest(request: LabelRequest): Promise<LabelRequestResult> {
    const { store, media, config, channel, server } = this.deps;
    const touchId = request.touch_id;
    const caretaker = this.primaryCaretaker();
    if (!caretaker) {
      log.warn(`label_request for touch ${touchId}, but no caretaker has texted Marco yet`);
      return { status: "no_caretaker", touch_id: touchId };
    }
    const questionId = stableId("req", "touch", touchId);
    const asked = store.question(questionId);
    if (asked && asked.status !== "pending") {
      return { status: "already_asked", request_id: asked.id, touch_id: touchId, caretaker: caretaker.name };
    }

    const itemId = stableId("item", "touch", touchId);
    let item = store.item(itemId);
    if (!item?.photo) {
      const photo = await media.saveImage(await server.getCrop(request.crop_url), "image/jpeg");
      item = store.createItem({ id: itemId, origin: "user_touch", photo, touchId });
    }
    const question = store.createQuestion({ id: questionId, kind: "identify", itemId: item.id, caretaker: caretaker.handle, messageIds: [], status: "pending" });

    const conv = caretaker.conversation;
    // Save each accepted send before the next network operation. A prompt failure
    // must not forget the photo or break a reply to it after a restart.
    let photoId = question.messageIds[0];
    if (!photoId) {
      photoId = await channel.send(conv, { type: "image", path: media.path(item.photo!), mimeType: "image/jpeg" }, { key: `ask:${question.id}:photo` });
      store.updateQuestion(question.id, { messageIds: [photoId] });
    }
    const askId = await channel.send(
      conv,
      { type: "text", text: `${config.userName} just touched this and asked what it is. Reply with the object's name as text.` },
      { key: `ask:${question.id}:text` },
    );
    store.updateQuestion(question.id, { status: "open", messageIds: [photoId, askId] });
    log.info(`asked ${caretaker.name} about touch ${touchId} (${question.id})`);
    return { status: "sent", request_id: question.id, touch_id: touchId, caretaker: caretaker.name };
  }

  primaryCaretaker(): Caretaker | undefined {
    const { store, config } = this.deps;
    const allowed = store.caretakers().filter((caretaker) => config.caretakerNames.has(normalizeHandle(caretaker.handle)));
    return (config.primaryCaretaker && allowed.find((caretaker) => caretaker.handle === config.primaryCaretaker)) || allowed[0];
  }

  private link(handle: string, conversation: Conversation): Caretaker {
    const caretaker = this.deps.store.upsertCaretaker({
      handle,
      name: this.deps.config.caretakerNames.get(handle) ?? "Family",
      conversation,
      linkedAt: now(),
      welcomedAt: null,
      lastHelpAt: null,
    });
    log.info(`linked caretaker ${caretaker.name} (${handle})`);
    return caretaker;
  }

  /** Text only: Apple suppresses links and media in the first message of a conversation. */
  private async welcome(caretaker: Caretaker, messageId: string): Promise<Caretaker> {
    const user = this.deps.config.userName;
    const hi = caretaker.name === "Family" ? "Hi!" : `Hi ${caretaker.name}!`;
    await this.say(
      caretaker,
      `${hi} I'm Marco, ${user}'s home helper. When ${user} touches something I don't recognize, I'll text you a photo. ` +
        `Reply with the object's name as text. You can also teach me anytime: send a photo with its name, like "${user}'s keys".`,
      { key: `welcome:${messageId}` },
    );
    return this.deps.store.upsertCaretaker({ ...caretaker, welcomedAt: now() });
  }

  /** Flow A: the caretaker sent one or more photos, maybe with a typed caption in the same message. */
  private async onPhotos(caretaker: Caretaker, images: MediaPart[], answer: Answer) {
    const { store, media } = this.deps;
    const questions: Question[] = [];
    for (const [i, image] of images.entries()) {
      const itemId = stableId("item", answer.messageId, String(i));
      let item = store.item(itemId);
      if (!item) {
        const photo = await media.saveImage(await image.read(), image.mimeType);
        item = store.createItem({ id: itemId, origin: "caretaker_photo", photo });
      }
      questions.push(
        store.createQuestion({
          id: stableId("req", answer.messageId, String(i)),
          kind: "name_photo",
          itemId: item.id,
          caretaker: caretaker.handle,
          messageIds: [answer.messageId],
          status: "open",
        }),
      );
    }
    const [only] = questions;
    if (only && questions.length === 1 && answer.text) return this.answer(caretaker, only, answer);

    // iMessage often delivers a photo and its caption as two messages. Wait briefly so the caption answers first.
    this.later(async () => {
      const open = questions.filter((q) => store.question(q.id)?.status === "open");
      if (!open.length) return;
      const ask =
        open.length === 1
          ? "Got it. What is this? Reply with its name as text."
          : `Got ${open.length} photos. Swipe to reply on each one with its name as text.`;
      const sentId = await this.say(caretaker, ask, { parentId: answer.messageId, key: `prompt:${answer.messageId}` });
      for (const q of open) store.updateQuestion(q.id, { messageIds: [...q.messageIds, sentId] });
    });
  }

  /** A retried message returns to its question; a swipe-reply names its question; otherwise the oldest open one. */
  private pickQuestion(caretaker: Caretaker, parentId: string | null, answer: Answer): Question | undefined {
    const { store } = this.deps;
    const retried = store.questionAnsweredBy(answer.messageId);
    if (retried) return retried;
    if (parentId) {
      const q = store.questionByMessageId(parentId);
      if (q && q.caretaker === caretaker.handle) return q;
    }
    const open = store.openQuestions(caretaker.handle)[0];
    if (open) return open;
    return undefined;
  }

  private async answer(caretaker: Caretaker, question: Question, { text, messageId }: Answer) {
    const { store, config } = this.deps;
    const item = store.item(question.itemId);
    if (!item) return;
    const user = config.userName;
    const retry = question.lastAnswer?.messageId === messageId;

    if (isDontKnow(text)) {
      store.updateQuestion(question.id, {
        status: "answered",
        answeredAt: question.answeredAt ?? now(),
        lastAnswer: { messageId, kind: "unknown", outcome: "held" },
      });
      log.info(`${caretaker.name} doesn't know what ${item.touchId ? `touch ${item.touchId}` : item.id} is`);
      await this.react(caretaker, messageId, LIKE);
      await this.say(caretaker, `No problem. I'll let ${user} know you weren't sure.`, { key: `unknown:${messageId}` });
      return;
    }

    let label: Label;
    let kind: LastAnswer["kind"];
    if (retry && item.label) {
      // Interpreted on the first attempt; finish the remaining steps with the same idempotency keys.
      label = item.label;
      kind = question.lastAnswer!.kind;
    } else {
      kind = question.status === "answered" ? "correction" : "answer";
      label = {
        name: extractName(text), text, transcript: null, audio: null,
        author: caretaker.name, authorHandle: caretaker.handle, createdAt: now(),
      };
      store.updateItem(item.id, { label, name: label.name ?? item.name });
      store.updateQuestion(question.id, { status: "answered", answeredAt: question.answeredAt ?? now(), lastAnswer: { messageId, kind, outcome: null } });
      log.info(`label for ${item.id}: ${label.name ?? "(unnamed)"} (${kind})`);
    }

    // Reach the Marco server first: that is what tells the phone. A network error throws, so the event is replayed.
    let outcome = store.question(question.id)!.lastAnswer?.outcome ?? null;
    if (!outcome) {
      outcome = await this.deliver(question, store.item(item.id)!, label, kind);
      store.updateQuestion(question.id, { lastAnswer: { messageId, kind, outcome } });
    }

    await this.react(caretaker, messageId, LOVE);
    const sentId = await this.say(caretaker, this.confirmation(question, label, kind, outcome), {
      parentId: question.messageIds[0],
      key: `confirm:${messageId}`,
    });
    const latest = store.question(question.id)!;
    if (!latest.messageIds.includes(sentId)) store.updateQuestion(question.id, { messageIds: [...latest.messageIds, sentId] });
  }

  /**
   * Hands one answer to the Marco server (docs/INTERFACES.md §5). Returns what happened; throws on errors worth
   * retrying (network, 5xx, 408/429), so the event is replayed.
   */
  private async deliver(question: Question, item: Item, label: Label, kind: LastAnswer["kind"]): Promise<Outcome> {
    const { server, store, media } = this.deps;
    const name = label.name;
    if (!name) return "held"; // A searchable typed name is required.
    const text = label.text ?? name;
    const audioPath = null; // New labels are typed; never upload legacy caretaker recordings.
    const photoPath = item.photo ? media.path(item.photo) : null;
    const remember = (serverItemId: string | null | undefined) => {
      if (serverItemId) store.updateItem(item.id, { serverItemId });
    };

    try {
      if (question.kind === "identify") {
        if (item.serverItemId) {
          await server.postLabel({ itemId: item.serverItemId, name, text, audioPath });
          return "posted";
        }
        try {
          remember((await server.postLabel({ touchId: item.touchId ?? undefined, name, text, audioPath })).item_id);
          return "posted";
        } catch (err) {
          // The server no longer knows this touch (it restarted). Keep the label: register the item from the crop.
          if (!(err instanceof MarcoServerError && err.status === 404 && photoPath)) throw err;
          log.warn(`server forgot touch ${item.touchId}; registering "${name}" from its crop instead`);
          const reg = await server.postItem(name, photoPath);
          if (reg.quality !== "ok" || !reg.item_id) return "unreachable";
          remember(reg.item_id);
          await server.postLabel({ itemId: reg.item_id, name, text, audioPath });
          return "posted";
        }
      }

      // Flow A: register the photo once; later corrections go to POST /v1/labels.
      let serverItemId = item.serverItemId ?? null;
      const registeredNow = !serverItemId;
      if (!serverItemId) {
        if (!photoPath) return "unreachable";
        const reg = await server.postItem(name, photoPath);
        if (reg.quality !== "ok" || !reg.item_id) {
          log.info(`server asked for a retake of "${name}": ${reg.reason ?? ""}`);
          return "retake";
        }
        serverItemId = reg.item_id;
        remember(serverItemId);
      }
      if (audioPath || !registeredNow || kind === "correction") {
        await server.postLabel({ itemId: serverItemId, name, text, audioPath });
      }
      return "posted";
    } catch (err) {
      if (err instanceof MarcoServerError && err.permanent) {
        log.error(`the Marco server rejected the label for ${item.id}`, err);
        return "unreachable";
      }
      throw err;
    }
  }

  private confirmation(question: Question, label: Label, kind: LastAnswer["kind"], outcome: Outcome): string {
    const user = this.deps.config.userName;
    const name = label.name;
    if (outcome === "unreachable") return `Thanks! I couldn't get that to ${user}'s phone just now, but I saved it here.`;
    if (outcome === "retake") return `I can't see the ${name} clearly in that photo. Could you send another, a bit closer and on a plain surface?`;
    if (outcome === "held" || !name) return "Please type the object's name.";
    if (kind === "correction") return `Updated: "${name}".`;
    if (question.kind === "identify") return `Got it: ${name}. I'll tell ${user}.`;
    return `Saved "${name}". ${user} can ask me for it by name now.`;
  }

  /**
   * /restart: remove every item and label Photon gave the Marco server (DELETE /v1/items?source=photon), and forget
   * them here too, so testing starts afresh. The phone's own setup items are untouched. Safe to replay: the reply is
   * stored before it is sent, and a replay only re-sends it.
   */
  private async restart(caretaker: Caretaker, messageId: string) {
    const { server, store, media } = this.deps;
    let reply = caretaker.lastCommand?.messageId === messageId ? caretaker.lastCommand.reply : null;
    if (!reply) {
      try {
        const { removed } = await server.removeItems(PHOTON_SOURCE);
        for (const item of store.resetLabels()) {
          media.remove(item.photo);
          media.remove(item.label?.audio);
        }
        const names = removed.map((r) => r.name);
        const shown = names.length > 8 ? `${names.slice(0, 8).join(", ")} and ${names.length - 8} more` : names.join(", ");
        reply = removed.length
          ? `Fresh start: I removed ${removed.length} label${removed.length === 1 ? "" : "s"} from Marco (${shown}). Send photos to teach me again.`
          : "Fresh start: Marco had no labels from you, so there was nothing to remove.";
        log.info(`/restart from ${caretaker.name}: removed ${removed.length} item(s) from the Marco server`);
      } catch (err) {
        if (!(err instanceof MarcoServerError && err.permanent)) throw err; // network or 5xx: the event is replayed
        log.error("/restart: the Marco server refused", err);
        reply = `I couldn't clear Marco's labels just now (the server said HTTP ${err.status}).`;
      }
      caretaker = store.upsertCaretaker({ ...caretaker, lastCommand: { messageId, reply } });
    }
    await this.say(caretaker, reply, { key: `restart:${messageId}` });
  }

  /** Read receipt on our photo: the caretaker is looking at it right now. (§5 has no message for this yet.) */
  private onRead(handle: string, targetId: string) {
    const { store } = this.deps;
    const q = store.questionByMessageId(targetId);
    if (!q || q.kind !== "identify" || q.status !== "open" || q.seenAt || q.caretaker !== handle) return;
    store.updateQuestion(q.id, { seenAt: now() });
    log.info(`${store.caretaker(handle)?.name ?? "the caretaker"} opened the photo for ${q.id}`);
  }

  /** Anything that is not a photo and not an answer. */
  private async chat(caretaker: Caretaker, { text, messageId }: Answer) {
    const { store, config } = this.deps;
    const user = config.userName;
    if ((!/[\p{L}\p{N}]/u.test(text) || /^(thanks|thank you|ty|ok|okay|cool|great|perfect|nice|love you|got it)\b/i.test(text))) {
      await this.react(caretaker, messageId, LOVE);
      return;
    }
    if (/^(list|items|what do you know)\b/i.test(text)) {
      const names = store.items().flatMap((i) => (i.name ? [i.name] : []));
      await this.say(caretaker, names.length ? `I know ${names.length}: ${names.join(", ")}.` : "Nothing yet. Send me a photo with its name to start.", {
        key: `list:${messageId}`,
      });
      return;
    }
    if (caretaker.lastHelpAt && Date.now() - Date.parse(caretaker.lastHelpAt) < HELP_COOLDOWN_MS) return;
    await this.say(
      caretaker,
      `To teach me something, send a photo of it with its name. When ${user} finds something I don't know, I'll text you a photo to label.`,
      { key: `help:${messageId}` },
    );
    store.upsertCaretaker({ ...caretaker, lastHelpAt: now() });
  }

  /** Sends text, threaded under `parentId` when given; falls back to a plain send if threading fails. */
  private async say(caretaker: Caretaker, text: string, { parentId, key }: { parentId?: string | undefined; key: string }): Promise<string> {
    const { channel } = this.deps;
    if (parentId) {
      try {
        return await channel.send(caretaker.conversation, { type: "text", text }, { parentId, key });
      } catch (err) {
        log.warn("threaded reply failed; sending normally", err);
      }
    }
    return channel.send(caretaker.conversation, { type: "text", text }, { key: parentId ? `${key}:plain` : key });
  }

  private async react(caretaker: Caretaker, messageId: string, emoji: string) {
    await this.deps.channel.react(caretaker.conversation, messageId, emoji, `react:${messageId}`).catch((err) => log.warn("tapback failed", err));
  }

  private later(fn: () => Promise<void>) {
    const task: Promise<void> = new Promise((resolve) => setTimeout(resolve, this.deps.config.promptDelayMs))
      .then(fn)
      .catch((err) => log.error("follow-up failed", err))
      .finally(() => this.pending.delete(task));
    this.pending.add(task);
  }
}
