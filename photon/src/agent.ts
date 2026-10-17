import { attachment, Emoji, type Content, type Message, type Space } from "spectrum-ts";
import { nativeContactCard } from "spectrum-ts/providers/imessage";
import { normalizeHandle, type Config } from "./config.js";
import { itemView, type EventBus, type ItemView } from "./events.js";
import { log } from "./log.js";
import type { MarcoServer } from "./marco-server.js";
import type { Media } from "./media.js";
import { extractName, isDontKnow } from "./names.js";
import { now, type Caretaker, type Label, type Question, type Store } from "./store.js";
import type { Transcriber } from "./transcribe.js";

const HELP_COOLDOWN_MS = 10 * 60_000;
const NAME_FOLLOWUP_MS = 10 * 60_000;

/** Finds the live conversation with a caretaker, including after a restart. */
export interface SpaceDirectory {
  remember(handle: string, space: Space): void;
  resolve(caretaker: Caretaker): Promise<Space | null>;
}

export class Spaces implements SpaceDirectory {
  private readonly live = new Map<string, Space>();

  constructor(private readonly lookup: (platform: string, spaceId: string) => Promise<Space | undefined>) {}

  remember(handle: string, space: Space) {
    this.live.set(handle, space);
  }

  async resolve(caretaker: Caretaker): Promise<Space | null> {
    const live = this.live.get(caretaker.handle);
    if (live) return live;
    const space = await this.lookup(caretaker.platform, caretaker.spaceId).catch((err) => {
      log.warn(`could not reopen the conversation with ${caretaker.name}`, err);
      return undefined;
    });
    if (space) this.live.set(caretaker.handle, space);
    return space ?? null;
  }
}

export interface AgentDeps {
  config: Config;
  store: Store;
  media: Media;
  transcribe: Transcriber;
  events: EventBus;
  spaces: SpaceDirectory;
  server: MarcoServer;
}

export type LabelRequestResult =
  | { status: "sent"; request_id: string; item_id: string; caretaker: string }
  | { status: "already_asked"; request_id: string; item_id: string; caretaker: string }
  | { status: "already_labeled"; item: ItemView }
  | { status: "no_caretaker" }
  | { status: "failed"; error: string };

type Binary = { mimeType: string; read(): Promise<Buffer> };
type Answer = { text: string; audio: Binary | null; message: Message };

const isImage = (c: Content): c is Extract<Content, { type: "attachment" }> =>
  c.type === "attachment" && /^image\//i.test(c.mimeType);
const isAudio = (c: Content): c is Extract<Content, { type: "attachment" | "voice" }> =>
  c.type === "voice" || (c.type === "attachment" && /^audio\//i.test(c.mimeType));

/** A swipe-reply wraps the real content; a photo with a caption arrives as a group of parts. */
function unpack(content: Content): { targetId: string | null; parts: Content[] } {
  let targetId: string | null = null;
  let inner = content;
  if (inner.type === "reply") {
    targetId = inner.target.id;
    inner = inner.content;
  }
  const parts = inner.type === "group" ? inner.items.map((m) => m.content) : [inner];
  return { targetId, parts };
}

/**
 * Marco's side of the family conversation in iMessage.
 *
 * Flow A (setup): a caretaker texts a photo plus a name or voice memo, and Marco learns the item.
 * Flow B (ask): the user touches something unknown, Marco texts the caretaker its photo,
 * and the caretaker's reply (ideally a voice memo) becomes the label the user hears.
 */
export class MarcoAgent {
  private readonly pending = new Set<Promise<void>>();
  private readonly recent = new Map<string, Message>();

  constructor(private readonly deps: AgentDeps) {}

  /** Resolves once delayed follow-ups (photo prompts) have run. */
  async settled(): Promise<void> {
    while (this.pending.size) await Promise.allSettled([...this.pending]);
  }

  async handle(space: Space, message: Message): Promise<void> {
    if (message.direction === "outbound") {
      this.remember(message);
      return;
    }
    const { store } = this.deps;
    if (!store.markProcessed(message.id)) return;
    const handle = message.sender?.id ? normalizeHandle(message.sender.id) : null;
    if (!handle) return;

    const content = message.content;
    if (content.type === "read") return this.onRead(handle, content.target.id);
    if (content.type === "reaction" || content.type === "typing") return;

    this.remember(message);
    this.deps.spaces.remember(handle, space);
    let caretaker = store.caretaker(handle);
    const isNew = !caretaker;
    if (!caretaker) {
      caretaker = this.link(handle, space, message.platform);
      await this.welcome(space, caretaker);
    } else if (caretaker.spaceId !== space.id) {
      caretaker = store.upsertCaretaker({ ...caretaker, spaceId: space.id, platform: message.platform });
    }

    const { targetId, parts } = unpack(content);
    const images = parts.filter(isImage);
    const audio = parts.find(isAudio) ?? null;
    const text = parts
      .flatMap((p) => (p.type === "text" ? [p.text.trim()] : []))
      .filter(Boolean)
      .join(" ");
    const answer: Answer = { text, audio, message };

    if (images.length) return this.onPhotos(space, caretaker, images, answer);
    if (!text && !audio) return;
    const question = this.pickQuestion(caretaker, targetId);
    if (question) return this.answer(space, caretaker, question, answer);
    if (!isNew) await this.chat(space, caretaker, answer);
  }

  /** Flow B: the user touched an unknown item. Texts its photo to the primary caretaker. */
  async requestLabel(input: { itemId?: string; image: Buffer; mimeType: string }): Promise<LabelRequestResult> {
    const { store, media, events, config, spaces } = this.deps;
    const caretaker = this.primaryCaretaker();
    if (!caretaker) return { status: "no_caretaker" };

    const existing = input.itemId ? store.item(input.itemId) : undefined;
    if (existing?.label && (existing.label.audio || existing.label.name)) {
      return { status: "already_labeled", item: itemView(existing, media) };
    }
    const asked = existing && store.openIdentifyQuestion(existing.id);
    if (asked) return { status: "already_asked", request_id: asked.id, item_id: asked.itemId, caretaker: caretaker.name };

    const space = await spaces.resolve(caretaker);
    if (!space) return { status: "failed", error: `no conversation with ${caretaker.name} yet` };

    const photo = await media.saveImage(input.image, input.mimeType);
    const item = existing
      ? store.updateItem(existing.id, { photo })
      : store.createItem({ ...(input.itemId ? { id: input.itemId } : {}), origin: "user_touch", photo });
    const question = store.createQuestion({ kind: "identify", itemId: item.id, caretaker: caretaker.handle, messageIds: [], status: "pending" });

    try {
      const sent = await space.send(
        attachment(media.path(photo)),
        `${config.userName} just touched this and asked what it is. Reply with a voice memo and your voice becomes its label.`,
      );
      sent.forEach((m) => this.remember(m));
      store.updateQuestion(question.id, { status: "open", messageIds: sent.map((m) => m.id) });
    } catch (err) {
      store.updateQuestion(question.id, { status: "failed" });
      log.error("could not send the label request", err);
      return { status: "failed", error: String(err) };
    }

    events.emit({ type: "label_request_sent", request_id: question.id, item_id: item.id, caretaker: caretaker.name });
    log.info(`asked ${caretaker.name} about ${item.id} (${question.id})`);
    return { status: "sent", request_id: question.id, item_id: item.id, caretaker: caretaker.name };
  }

  primaryCaretaker(): Caretaker | undefined {
    const { store, config } = this.deps;
    return (config.primaryCaretaker && store.caretaker(config.primaryCaretaker)) || store.caretakers()[0];
  }

  private link(handle: string, space: Space, platform: string): Caretaker {
    const caretaker = this.deps.store.upsertCaretaker({
      handle,
      name: this.deps.config.caretakerNames.get(handle) ?? "Family",
      platform,
      spaceId: space.id,
      linkedAt: now(),
      lastHelpAt: null,
    });
    this.deps.events.emit({ type: "caretaker_linked", caretaker: caretaker.name });
    log.info(`linked caretaker ${caretaker.name} (${handle})`);
    return caretaker;
  }

  /** Text only: Apple suppresses links and media in the first message of a conversation. */
  private async welcome(space: Space, caretaker: Caretaker) {
    const user = this.deps.config.userName;
    const hi = caretaker.name === "Family" ? "Hi!" : `Hi ${caretaker.name}!`;
    await space.send(
      `${hi} I'm Marco, ${user}'s home helper. When ${user} touches something I don't recognize, I'll text you a photo. ` +
        `Reply with a voice memo and your voice becomes its label. You can also teach me anytime: send a photo with its name, like "${user}'s keys".`,
    );
    if (caretaker.platform === "imessage") {
      // Saving the contact removes Apple's "Report Junk" banner for good.
      await space.send(nativeContactCard()).catch((err) => log.warn("contact card not sent", err));
    }
  }

  /** Flow A: the caretaker sent one or more photos, maybe with a caption or voice memo in the same message. */
  private async onPhotos(space: Space, caretaker: Caretaker, images: Binary[], answer: Answer) {
    const { store, media } = this.deps;
    const questions: Question[] = [];
    for (const image of images) {
      const photo = await media.saveImage(await image.read(), image.mimeType);
      const item = store.createItem({ origin: "caretaker_photo", photo });
      questions.push(
        store.createQuestion({ kind: "name_photo", itemId: item.id, caretaker: caretaker.handle, messageIds: [answer.message.id], status: "open" }),
      );
    }
    const [only] = questions;
    if (only && questions.length === 1 && (answer.text || answer.audio)) return this.answer(space, caretaker, only, answer);

    // iMessage often delivers a photo and its caption as two messages. Wait briefly so the caption answers first.
    this.later(async () => {
      const open = questions.filter((q) => store.question(q.id)?.status === "open");
      if (!open.length) return;
      const ask =
        open.length === 1
          ? "Got it. What is this? Reply with its name or a voice memo."
          : `Got ${open.length} photos. Swipe to reply on each one with its name or a voice memo.`;
      const sent = await this.replyTo(space, answer.message.id, ask);
      if (sent) for (const q of open) store.updateQuestion(q.id, { messageIds: [...q.messageIds, sent.id] });
    });
  }

  /** A swipe-reply names its question exactly; otherwise answer the oldest open question. */
  private pickQuestion(caretaker: Caretaker, targetId: string | null): Question | undefined {
    const { store } = this.deps;
    if (targetId) {
      const q = store.questionByMessageId(targetId);
      if (q && q.caretaker === caretaker.handle) return q;
    }
    return store.openQuestions(caretaker.handle)[0] ?? store.recentUnnamed(caretaker.handle, NAME_FOLLOWUP_MS);
  }

  private async answer(space: Space, caretaker: Caretaker, question: Question, { text, audio, message }: Answer) {
    const { store, media, transcribe, events, server, config } = this.deps;
    const item = store.item(question.itemId);
    if (!item) return;
    const user = config.userName;

    if (!audio && isDontKnow(text)) {
      store.updateQuestion(question.id, { status: "answered", answeredAt: now() });
      if (question.kind === "identify") {
        events.emit({ type: "label_unknown", request_id: question.id, item_id: item.id, caretaker: caretaker.name });
      }
      await this.react(message, Emoji.like);
      await space.send(`No problem. I'll let ${user} know you weren't sure.`);
      return;
    }

    let audioFile: string | null = null;
    let transcript: string | null = null;
    if (audio) {
      audioFile = await media.saveAudio(await audio.read(), audio.mimeType);
      transcript = await transcribe(media.path(audioFile));
    }

    const previous = item.label;
    // A text right after an unnamed voice note names it and keeps the voice.
    const naming = !audio && !!previous?.audio && !previous.name;
    const correcting = question.status === "answered" && !naming;
    const label: Label = naming
      ? { ...previous, text, name: extractName(text), createdAt: now() }
      : {
          name: extractName(text) ?? extractName(transcript),
          text: text || null,
          transcript,
          audio: audioFile,
          author: caretaker.name,
          authorHandle: caretaker.handle,
          createdAt: now(),
        };
    const updated = store.updateItem(item.id, { label, name: label.name ?? item.name });
    store.updateQuestion(question.id, { status: "answered", answeredAt: question.answeredAt ?? now() });

    // The user is waiting on this; tell the phone before acknowledging the caretaker.
    const view = itemView(updated, media);
    const requestId = question.kind === "identify" ? question.id : null;
    events.emit({ type: "label_ready", request_id: requestId, item: view });
    log.info(`label for ${item.id}: ${label.name ?? "(voice only)"}${label.audio ? " + voice" : ""}`);

    await this.react(message, Emoji.love);
    const confirmation = this.confirmation(question, label, correcting);
    const sent = await this.replyTo(space, question.messageIds[0], confirmation);
    if (sent) store.updateQuestion(question.id, { messageIds: [...question.messageIds, sent.id] });

    if (question.kind === "identify") {
      void server.labelReply(requestId, view);
    } else if (label.name && server.enabled) {
      const registration = await server.registerItem(updated);
      if (registration?.item_id) store.updateItem(item.id, { serverItemId: registration.item_id });
      if (registration?.quality === "retake") {
        await space.send(`I can't see the ${label.name} clearly in that photo. Could you send another, a bit closer and on a plain surface?`);
      }
    }
  }

  private confirmation(question: Question, label: Label, correcting: boolean): string {
    const user = this.deps.config.userName;
    const name = label.name;
    if (correcting && name) return `Updated: "${name}".`;
    if (question.kind === "identify") {
      if (!name) return `Got your voice note. ${user} will hear it next time.`;
      return label.audio ? `Got it: ${name}. ${user} will hear your voice next time.` : `Got it: ${name}. I'll tell ${user}.`;
    }
    if (!name) return `Saved your voice note. Text me its name too, so ${user} can ask for it.`;
    return label.audio
      ? `Saved "${name}" with your voice. ${user} can ask me for it by name now.`
      : `Saved "${name}". ${user} can ask me for it by name now.`;
  }

  /** Read receipt on our photo: the caretaker is looking at it right now. */
  private onRead(handle: string, targetId: string) {
    const { store, events } = this.deps;
    const q = store.questionByMessageId(targetId);
    if (!q || q.kind !== "identify" || q.status !== "open" || q.seenAt || q.caretaker !== handle) return;
    store.updateQuestion(q.id, { seenAt: now() });
    events.emit({ type: "label_request_seen", request_id: q.id, item_id: q.itemId, caretaker: store.caretaker(handle)?.name ?? "Family" });
  }

  /** Anything that is not a photo and not an answer. */
  private async chat(space: Space, caretaker: Caretaker, { text, audio, message }: Answer) {
    const { store, config } = this.deps;
    const user = config.userName;
    if (!audio && (!/[\p{L}\p{N}]/u.test(text) || /^(thanks|thank you|ty|ok|okay|cool|great|perfect|nice|love you|got it)\b/i.test(text))) {
      await this.react(message, Emoji.love);
      return;
    }
    if (!audio && /^(list|items|what do you know)\b/i.test(text)) {
      const names = store.items().flatMap((i) => (i.name ? [i.name] : []));
      await space.send(names.length ? `I know ${names.length}: ${names.join(", ")}.` : "Nothing yet. Send me a photo with its name to start.");
      return;
    }
    if (caretaker.lastHelpAt && Date.now() - Date.parse(caretaker.lastHelpAt) < HELP_COOLDOWN_MS) return;
    store.upsertCaretaker({ ...caretaker, lastHelpAt: now() });
    await space.send(
      audio
        ? "I got a voice note but I'm not sure which item it's for. Send a photo first, then your voice memo."
        : `To teach me something, send a photo of it with its name. When ${user} finds something I don't know, I'll text you a photo to label.`,
    );
  }

  /** Threads under `messageId` when possible, else sends normally. */
  private async replyTo(space: Space, messageId: string | undefined, body: string): Promise<Message | undefined> {
    const target = messageId ? (this.recent.get(messageId) ?? (await space.getMessage(messageId).catch(() => undefined))) : undefined;
    if (target) {
      try {
        const sent = await target.reply(body);
        if (sent) return sent;
      } catch (err) {
        log.warn("threaded reply failed; sending normally", err);
      }
    }
    return space.send(body);
  }

  private async react(message: Message, emoji: string) {
    await message.react(emoji).catch((err) => log.warn("tapback failed", err));
  }

  private remember(message: Message) {
    this.recent.set(message.id, message);
    if (this.recent.size > 500) this.recent.delete(this.recent.keys().next().value!);
  }

  private later(fn: () => Promise<void>) {
    const task: Promise<void> = new Promise((resolve) => setTimeout(resolve, this.deps.config.promptDelayMs))
      .then(fn)
      .catch((err) => log.error("follow-up failed", err))
      .finally(() => this.pending.delete(task));
    this.pending.add(task);
  }
}
