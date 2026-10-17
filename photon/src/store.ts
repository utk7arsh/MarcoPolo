import { randomUUID } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, renameSync, writeFileSync } from "node:fs";
import { join } from "node:path";

export interface Label {
  /** Short searchable name ("cumin"), or null when only an untranscribed voice note exists. */
  name: string | null;
  /** What the caretaker typed, if anything. */
  text: string | null;
  /** Speech-to-text of the voice note, if any. */
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
  /** The main server's id once POST /items accepted the photo (Flow A). */
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
}

export interface Caretaker {
  handle: string;
  name: string;
  platform: string;
  spaceId: string;
  linkedAt: string;
  lastHelpAt: string | null;
}

interface Data {
  version: 1;
  caretakers: Record<string, Caretaker>;
  items: Record<string, Item>;
  questions: Record<string, Question>;
  /** Inbound message ids already handled; Spectrum delivery is at-least-once. */
  processed: string[];
}

const MAX_PROCESSED = 2000;

export const now = () => new Date().toISOString();
export const newId = (prefix: string) => `${prefix}_${randomUUID().replace(/-/g, "").slice(0, 10)}`;

/** Small JSON-file store. Every write is synchronous and atomic (temp file + rename), which is plenty at household scale. */
export class Store {
  private data: Data;
  private readonly file: string;

  constructor(dataDir: string) {
    mkdirSync(dataDir, { recursive: true });
    this.file = join(dataDir, "marco-photon.json");
    this.data = existsSync(this.file)
      ? (JSON.parse(readFileSync(this.file, "utf8")) as Data)
      : { version: 1, caretakers: {}, items: {}, questions: {}, processed: [] };
  }

  private save() {
    const tmp = `${this.file}.tmp`;
    writeFileSync(tmp, JSON.stringify(this.data, null, 2));
    renameSync(tmp, this.file);
  }

  /** Returns false when this inbound message was already handled. */
  markProcessed(messageId: string): boolean {
    if (this.data.processed.includes(messageId)) return false;
    this.data.processed.push(messageId);
    if (this.data.processed.length > MAX_PROCESSED) this.data.processed.splice(0, this.data.processed.length - MAX_PROCESSED);
    this.save();
    return true;
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

  item(id: string): Item | undefined {
    return this.data.items[id];
  }

  items(): Item[] {
    return Object.values(this.data.items).sort((a, b) => a.createdAt.localeCompare(b.createdAt));
  }

  createItem(fields: Partial<Item> & Pick<Item, "origin">): Item {
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

  createQuestion(fields: Pick<Question, "kind" | "itemId" | "caretaker" | "messageIds" | "status">): Question {
    const question: Question = { id: newId("req"), createdAt: now(), answeredAt: null, seenAt: null, ...fields };
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

  questionByMessageId(messageId: string): Question | undefined {
    return Object.values(this.data.questions).find((q) => q.messageIds.includes(messageId));
  }

  /** Open questions for one caretaker, oldest first. */
  openQuestions(caretaker: string): Question[] {
    return Object.values(this.data.questions)
      .filter((q) => q.caretaker === caretaker && q.status === "open")
      .sort((a, b) => a.createdAt.localeCompare(b.createdAt));
  }

  openIdentifyQuestion(itemId: string): Question | undefined {
    return Object.values(this.data.questions).find(
      (q) => q.itemId === itemId && q.kind === "identify" && (q.status === "open" || q.status === "pending"),
    );
  }

  /** The most recent question answered with a voice note but no name, so a follow-up text can name it. */
  recentUnnamed(caretaker: string, withinMs: number): Question | undefined {
    const cutoff = Date.now() - withinMs;
    return Object.values(this.data.questions)
      .filter((q) => q.caretaker === caretaker && q.status === "answered" && q.answeredAt && Date.parse(q.answeredAt) > cutoff)
      .filter((q) => {
        const label = this.data.items[q.itemId]?.label;
        return label?.audio && !label.name;
      })
      .sort((a, b) => (b.answeredAt ?? "").localeCompare(a.answeredAt ?? ""))[0];
  }
}
