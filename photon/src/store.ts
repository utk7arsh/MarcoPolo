import { createHash, randomUUID } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, renameSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import type { Conversation } from "./channel.js";

export interface Label {
  /** Short searchable name ("cumin"); nullable for saved records from older versions. */
  name: string | null;
  /** What the caretaker typed, if anything. */
  text: string | null;
  /** Legacy stored transcript, retained for reading old data only. */
  transcript: string | null;
  /** Media filename of the caretaker's voice note (m4a when conversion worked). */
  audio: string | null;
  author: string;
  authorHandle: string;
  createdAt: string;
}

export type ItemOrigin = "caretaker_photo" | "user_touch";

export interface Item {
  id: string;
  name: string | null;
  photo: string | null;
  label: Label | null;
  origin: ItemOrigin;
  /** The Marco server's touch this item came from (Flow B label_request). */
  touchId?: string | null;
  /** The Marco server's item_id, once POST /v1/items or POST /v1/labels created it there. */
  serverItemId?: string | null;
  createdAt: string;
  updatedAt: string;
}

/**
 * An open question to a caretaker about one item.
 * - identify: the user touched an unknown item and Marco sent the caretaker its photo.
 * - name_photo: the caretaker sent a photo without saying what it is.
 */
export type QuestionKind = "identify" | "name_photo";
export type QuestionStatus = "pending" | "open" | "answered" | "failed";

export interface Question {
  id: string;
  kind: QuestionKind;
  itemId: string;
  caretaker: string;
  /** Every iMessage id in this thread (our photo, prompt and confirmation, or the caretaker's photo). A swipe-reply to any of them answers this question. */
  messageIds: string[];
  status: QuestionStatus;
  createdAt: string;
  answeredAt: string | null;
  seenAt: string | null;
  /** The inbound message that last answered this, so a redelivered event is recognized as a retry, not a new answer. */
  lastAnswer?: LastAnswer | null;
}

/** How one answer was interpreted, and what reaching the Marco server produced (null until that step finished). */
export interface LastAnswer {
  messageId: string;
  kind: "answer" | "correction" | "naming" | "voice" | "unknown";
  outcome: "posted" | "held" | "retake" | "unreachable" | null;
}

export interface Caretaker {
  handle: string;
  name: string;
  /** Where to text them; captured from their first message (a shared line cannot start a conversation). */
  conversation: Conversation;
  linkedAt: string;
  welcomedAt?: string | null;
  lastHelpAt: string | null;
  /** The last chat command (/restart) and its reply, so a replayed event repeats the reply instead of the command. */
  lastCommand?: { messageId: string; reply: string } | null;
}

interface Data {
  version: 2;
  caretakers: Record<string, Caretaker>;
  items: Record<string, Item>;
  questions: Record<string, Question>;
  /** Inbound message ids already handled; Photon event delivery is at-least-once. */
  processed: string[];
  /** Last Photon event cursor handled, so a restart resumes the stream instead of missing messages. */
  eventCursor: number;
}

const empty = (): Data => ({ version: 2, caretakers: {}, items: {}, questions: {}, processed: [], eventCursor: 0 });

const MAX_PROCESSED = 2000;

export const now = () => new Date().toISOString();
export const newId = (prefix: string) => `${prefix}_${randomUUID().replace(/-/g, "").slice(0, 10)}`;
/** A stable id derived from inbound data, so re-handling a redelivered event creates nothing twice. */
export const stableId = (prefix: string, ...parts: string[]) => `${prefix}_${createHash("sha256").update(parts.join("\0")).digest("hex").slice(0, 10)}`;

/** Small JSON-file store. Every write is synchronous and atomic (temp file + rename), which is plenty at household scale. */
export class Store {
  private data: Data;
  private readonly file: string;

  constructor(dataDir: string) {
    mkdirSync(dataDir, { recursive: true });
    this.file = join(dataDir, "marco-photon.json");
    const saved = existsSync(this.file) ? (JSON.parse(readFileSync(this.file, "utf8")) as { version?: number }) : null;
    if (saved && saved.version !== 2) {
      // Data from the Spectrum build has no Photon 2.0 conversation ids; keep it aside and start clean.
      renameSync(this.file, `${this.file}.v${saved.version ?? 1}.bak`);
    }
    this.data = saved?.version === 2 ? (saved as Data) : empty();
  }

  get eventCursor(): number {
    return this.data.eventCursor;
  }

  set eventCursor(seq: number) {
    this.data.eventCursor = seq;
    this.save();
  }

  private save() {
    const tmp = `${this.file}.tmp`;
    writeFileSync(tmp, JSON.stringify(this.data, null, 2));
    renameSync(tmp, this.file);
  }

  isProcessed(messageId: string): boolean {
    return this.data.processed.includes(messageId);
  }

  /** Called only after a message was fully handled, so a failure leaves it to be retried on redelivery. */
  markProcessed(messageId: string): void {
    if (this.isProcessed(messageId)) return;
    this.data.processed.push(messageId);
    if (this.data.processed.length > MAX_PROCESSED) this.data.processed.splice(0, this.data.processed.length - MAX_PROCESSED);
    this.save();
  }

  caretaker(handle: string): Caretaker | undefined {
    return this.data.caretakers[handle];
  }

  caretakers(): Caretaker[] {
    return Object.values(this.data.caretakers).sort((a, b) => a.linkedAt.localeCompare(b.linkedAt));
  }

  upsertCaretaker(caretaker: Caretaker): Caretaker {
    this.data.caretakers[caretaker.handle] = caretaker;
    this.save();
    return caretaker;
  }

  /** /restart: forget every item and question (caretakers, the event cursor and processed ids stay). */
  resetLabels(): Item[] {
    const items = Object.values(this.data.items);
    this.data.items = {};
    this.data.questions = {};
    this.save();
    return items;
  }

  item(id: string): Item | undefined {
    return this.data.items[id];
  }

  items(): Item[] {
    return Object.values(this.data.items).sort((a, b) => a.createdAt.localeCompare(b.createdAt));
  }

  /** Creates an item, or returns the existing one when `fields.id` is already taken (a retried event). */
  createItem(fields: Partial<Item> & Pick<Item, "origin">): Item {
    const existing = fields.id ? this.data.items[fields.id] : undefined;
    if (existing) return existing;
    const at = now();
    const item: Item = { id: newId("item"), name: null, photo: null, label: null, createdAt: at, updatedAt: at, ...fields };
    this.data.items[item.id] = item;
    this.save();
    return item;
  }

  updateItem(id: string, patch: Partial<Item>): Item {
    const item = this.data.items[id];
    if (!item) throw new Error(`unknown item ${id}`);
    Object.assign(item, patch, { updatedAt: now() });
    this.save();
    return item;
  }

  question(id: string): Question | undefined {
    return this.data.questions[id];
  }

  /** Creates a question, or returns the existing one when `fields.id` is already taken (a retried event). */
  createQuestion(fields: Pick<Question, "kind" | "itemId" | "caretaker" | "messageIds" | "status"> & { id?: string }): Question {
    const existing = fields.id ? this.data.questions[fields.id] : undefined;
    if (existing) return existing;
    const question: Question = { id: newId("req"), createdAt: now(), answeredAt: null, seenAt: null, lastAnswer: null, ...fields };
    this.data.questions[question.id] = question;
    this.save();
    return question;
  }

  updateQuestion(id: string, patch: Partial<Question>): Question {
    const question = this.data.questions[id];
    if (!question) throw new Error(`unknown question ${id}`);
    Object.assign(question, patch);
    this.save();
    return question;
  }

  /** The question an inbound message already answered, if any. */
  questionAnsweredBy(messageId: string): Question | undefined {
    return Object.values(this.data.questions).find((q) => q.lastAnswer?.messageId === messageId);
  }

  questionByMessageId(messageId: string): Question | undefined {
    return Object.values(this.data.questions).find((q) => q.messageIds.includes(messageId));
  }

  /** Open questions for one caretaker, oldest first. */
  openQuestions(caretaker: string): Question[] {
    return Object.values(this.data.questions)
      .filter((q) => q.caretaker === caretaker && (q.status === "open" || (q.status === "pending" && q.messageIds.length > 0)))
      .sort((a, b) => a.createdAt.localeCompare(b.createdAt));
  }

  openIdentifyQuestion(itemId: string): Question | undefined {
    return Object.values(this.data.questions).find(
      (q) => q.itemId === itemId && q.kind === "identify" && (q.status === "open" || q.status === "pending"),
    );
  }

  pendingIdentifyQuestions(): Question[] {
    return Object.values(this.data.questions).filter((q) => q.kind === "identify" && q.status === "pending");
  }

}
