// The agent's view of a messaging channel. Photon 2.0 implements it (photon.ts); so does the in-process sim (sim.ts).

/** Where a caretaker conversation lives: the Photon Space, and our agent's user id in it (every Photon 2.0 send needs both). */
export interface Conversation {
  platform: string;
  spaceId: string;
  agentId: string;
}

/** One piece of an inbound message. Media bytes are downloaded only when read. */
export type Part =
  | { type: "text"; text: string }
  | { type: "media"; mimeType: string; name: string | null; read(): Promise<Buffer> };

export interface Inbound {
  id: string;
  /** "read" is an iMessage read receipt: `parentId` is the message of ours that was read. */
  kind: "message" | "read";
  /** Sender handle: a phone number in E.164 or an Apple ID email. */
  from: string;
  conversation: Conversation;
  /** Photon's parentMessageId: the message this one swipe-replies to. */
  parentId: string | null;
  parts: Part[];
}

export type OutContent = { type: "text"; text: string } | { type: "image"; path: string; mimeType: string };

export interface SendOptions {
  /** Thread under this message (an iMessage swipe-reply). */
  parentId?: string;
  /** Idempotency key: reuse it when retrying the same send. */
  key?: string;
}

export interface Channel {
  /** Sends one message and returns its id. */
  send(conversation: Conversation, content: OutContent, options?: SendOptions): Promise<string>;
  /** Tapback on a message. */
  react(conversation: Conversation, messageId: string, emoji: string, key?: string): Promise<void>;
}
