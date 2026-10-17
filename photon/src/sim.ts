// In-process stand-in for a Spectrum provider. It mirrors the message shapes the cloud iMessage
// provider produces (voice memos as `voice`, photo + caption as `group`, swipe-replies as `reply`),
// so the agent can be exercised without Photon credentials: by tests, and by `npm run sim`.
import type { Message, Space } from "spectrum-ts";

type Built = { type: string } & Record<string, unknown>;
type Input = string | Built | { build(): Promise<Built> };

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

const isBuilder = (input: Input): input is { build(): Promise<Built> } => typeof input === "object" && "build" in input;

class SimMessage {
  readonly platform = "sim";
  readonly timestamp = new Date();

  constructor(
    readonly id: string,
    readonly direction: "inbound" | "outbound",
    readonly sender: { id: string; kind?: "agent" },
    readonly space: SimSpace,
    readonly content: Built,
    private readonly sim: SimPlatform,
  ) {}

  async reply(...inputs: Input[]) {
    const sent = [];
    for (const input of inputs) sent.push(await this.sim.deliver(this.space, input, this.id));
    return inputs.length === 1 ? sent[0] : sent;
  }

  async react(emoji: string) {
    return this.sim.deliver(this.space, { type: "reaction", emoji, target: this.id }, null);
  }

  async read() {}
  async edit() {}
  async unsend() {}
}

class SimSpace {
  readonly __platform = "sim";

  constructor(
    readonly id: string,
    readonly handle: string,
    private readonly sim: SimPlatform,
  ) {}

  async send(...inputs: Input[]) {
    const sent = [];
    for (const input of inputs) sent.push(await this.sim.deliver(this, input, null));
    return inputs.length === 1 ? sent[0] : sent;
  }

  async getMessage(id: string) {
    return this.sim.messages.get(id);
  }

  async responding<T>(fn: () => T | Promise<T>) {
    return fn();
  }

  async startTyping() {}
  async stopTyping() {}
}

export class SimPlatform {
  readonly outbox: OutboxEntry[] = [];
  readonly messages = new Map<string, SimMessage>();
  private readonly spaces = new Map<string, SimSpace>();
  private seq = 0;

  private nextId(prefix: string) {
    return `${prefix}-${++this.seq}`;
  }

  spaceById(id: string): Space | undefined {
    return this.spaces.get(id) as unknown as Space | undefined;
  }

  private spaceFor(handle: string): SimSpace {
    const id = `sim;-;${handle}`;
    let space = this.spaces.get(id);
    if (!space) {
      space = new SimSpace(id, handle, this);
      this.spaces.set(id, space);
    }
    return space;
  }

  /** A message from `from`, shaped as Spectrum delivers it. Pass `replyTo` for a swipe-reply. */
  inbound(from: string, parts: SimPart[], opts: { replyTo?: string; id?: string } = {}): [Space, Message] {
    const space = this.spaceFor(from);
    const contents = parts.map((part) => this.toContent(part));
    let content: Built =
      contents.length === 1
        ? contents[0]!
        : { type: "group", items: contents.map((c) => new SimMessage(this.nextId("part"), "inbound", { id: from }, space, c, this)) };
    if (opts.replyTo) {
      const target = this.messages.get(opts.replyTo) ?? { id: opts.replyTo };
      content = { type: "reply", content, target };
    }
    const message = new SimMessage(opts.id ?? this.nextId("in"), "inbound", { id: from }, space, content, this);
    this.messages.set(message.id, message);
    return [space as unknown as Space, message as unknown as Message];
  }

  /** An iMessage read receipt: `from` opened our message `targetId`. */
  readReceipt(from: string, targetId: string): [Space, Message] {
    const space = this.spaceFor(from);
    const target = this.messages.get(targetId) ?? { id: targetId };
    const message = new SimMessage(this.nextId("read"), "inbound", { id: from }, space, { type: "read", target }, this);
    return [space as unknown as Space, message as unknown as Message];
  }

  /** Records an outbound send and returns it as a Message, like `space.send` does. */
  async deliver(space: SimSpace, input: Input, replyTo: string | null): Promise<SimMessage> {
    const content: Built = typeof input === "string" ? { type: "text", text: input } : isBuilder(input) ? await input.build() : input;
    const message = new SimMessage(this.nextId("out"), "outbound", { id: "marco", kind: "agent" }, space, content, this);
    this.messages.set(message.id, message);
    this.outbox.push({
      id: message.id,
      to: space.handle,
      reply_to: replyTo ?? (content.type === "reaction" ? String(content.target) : null),
      type: content.type,
      ...(typeof content.text === "string" ? { text: content.text } : {}),
      ...(typeof content.name === "string" ? { name: content.name } : {}),
      ...(typeof content.mimeType === "string" ? { mime_type: content.mimeType } : {}),
      ...(typeof content.emoji === "string" ? { emoji: content.emoji } : {}),
      at: new Date().toISOString(),
    });
    return message;
  }

  private toContent(part: SimPart): Built {
    if ("text" in part) return { type: "text", text: part.text };
    const bytes = "image" in part ? part.image : part.voice;
    const base = {
      id: this.nextId("att"),
      size: bytes.length,
      read: async () => bytes,
      stream: async () => new Blob([new Uint8Array(bytes)]).stream(),
    };
    if ("image" in part) return { type: "attachment", name: "IMG_0001.HEIC", mimeType: part.mimeType ?? "image/heic", ...base };
    return { type: "voice", name: "Audio Message.caf", mimeType: part.mimeType ?? "audio/x-caf", ...base };
  }
}
