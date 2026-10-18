// In-process stand-in for Photon 2.0. It records what Marco sends and builds inbound messages the way
// photon.ts does from real events (photos and voice memos as media parts, swipe-replies as parentId),
// so the agent can be exercised without credentials: by tests, and by `npm run sim`.
import type { Channel, Conversation, Inbound, OutContent, Part, SendOptions } from "./channel.js";

export type SimPart = { text: string } | { image: Buffer; mimeType?: string } | { voice: Buffer; mimeType?: string };

export interface OutboxEntry {
  id: string;
  to: string;
  reply_to: string | null;
  type: string;
  text?: string;
  name?: string;
  mime_type?: string;
  emoji?: string;
  at: string;
}

export class SimChannel implements Channel {
  readonly outbox: OutboxEntry[] = [];
  /** Tests: make the next N sends fail, the way a network error would. */
  failSends = 0;
  private seq = 0;

  private nextId(prefix: string) {
    return `${prefix}-${++this.seq}`;
  }

  conversationFor(handle: string): Conversation {
    return { platform: "sim", spaceId: `sim:${handle}`, agentId: "marco" };
  }

  private record(conversation: Conversation, entry: Omit<OutboxEntry, "id" | "to" | "at">): string {
    const id = this.nextId("out");
    this.outbox.push({ id, to: conversation.spaceId.replace(/^sim:/, ""), ...entry, at: new Date().toISOString() });
    return id;
  }

  async send(conversation: Conversation, content: OutContent, options: SendOptions = {}): Promise<string> {
    if (this.failSends > 0) {
      this.failSends--;
      throw new Error("sim: send failed");
    }
    const replyTo = options.parentId ?? null;
    return content.type === "text"
      ? this.record(conversation, { reply_to: replyTo, type: "text", text: content.text })
      : this.record(conversation, { reply_to: replyTo, type: "attachment", name: content.path.split("/").pop() ?? "", mime_type: content.mimeType });
  }

  async react(conversation: Conversation, messageId: string, emoji: string): Promise<void> {
    this.record(conversation, { reply_to: messageId, type: "reaction", emoji });
  }

  /** A message from `from`. Pass `replyTo` for a swipe-reply. */
  inbound(from: string, parts: SimPart[], opts: { replyTo?: string; id?: string } = {}): Inbound {
    return {
      id: opts.id ?? this.nextId("in"),
      kind: "message",
      from,
      conversation: this.conversationFor(from),
      parentId: opts.replyTo ?? null,
      parts: parts.map((p) => this.toPart(p)),
    };
  }

  /** An iMessage read receipt: `from` opened our message `messageId`. */
  readReceipt(from: string, messageId: string): Inbound {
    return { id: this.nextId("read"), kind: "read", from, conversation: this.conversationFor(from), parentId: messageId, parts: [] };
  }

  private toPart(part: SimPart): Part {
    if ("text" in part) return { type: "text", text: part.text };
    if ("image" in part) return { type: "media", mimeType: part.mimeType ?? "image/heic", name: "IMG_0001.HEIC", read: async () => part.image };
    return { type: "media", mimeType: part.mimeType ?? "audio/x-caf", name: "Audio Message.caf", read: async () => part.voice };
  }
}
