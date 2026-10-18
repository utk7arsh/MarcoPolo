// Photon 2.0 (https://photon.codes/docs/beta): REST through the official @photon-ai/api client,
// inbound events over the project's Socket.IO stream with cursor replay.
import { ApiError, Photon } from "@photon-ai/api";
import { createHash, randomUUID } from "node:crypto";
import { readFile } from "node:fs/promises";
import { basename } from "node:path";
import { io, type Socket } from "socket.io-client";
import type { Channel, Conversation, Inbound, OutContent, Part, SendOptions } from "./channel.js";
import { log } from "./log.js";

/** The event contract our parsing is written against; pinned on every subscribe. */
const EVENT_API_VERSION = "2026-07-01";
const MAX_PENDING = 128;
/** Replays of one failing event before it is logged and skipped, so a single bad message cannot stall the line. */
const MAX_ATTEMPTS = 3;

export interface PhotonConfig {
  origin: string;
  projectId: string;
  apiKey: string;
}

/** The fields of a Photon 2.0 Message we rely on (the client validates the full schema on REST calls). */
interface WireContent {
  type: string;
  text?: string;
  attachmentId?: string;
  parts?: WireContent[];
}
interface WireMessage {
  id: string;
  platform: string;
  status: string;
  parentMessageId?: string;
  content: WireContent;
  sentBy: { id: string; kind: string; handle: string };
  receivedBy?: { id: string; kind: string; handle: string };
  addressedTo?: { id: string };
  space: { id: string; kind?: string };
}
export interface WireEvent {
  id: string;
  type: string;
  data?: { object?: WireMessage };
}

export class PhotonChannel implements Channel {
  private readonly photon: Photon;

  constructor(private readonly config: PhotonConfig) {
    this.photon = new Photon({ baseUrl: config.origin, headers: { Authorization: `Bearer ${config.apiKey}` } });
  }

  private get project() {
    return { id: this.config.projectId };
  }

  async send(conversation: Conversation, content: OutContent, options: SendOptions = {}): Promise<string> {
    const key = options.key ?? randomUUID();
    const body =
      content.type === "text"
        ? { type: "text" as const, format: "plain", text: content.text }
        : { type: "attachment" as const, attachmentId: await this.upload(content.path, content.mimeType, `${key}:upload`) };
    const sent = await this.call("sendMessage", () =>
      this.photon.projects.sendMessage({
        path: this.project,
        headers: { "idempotency-key": key },
        body: {
          spaceId: conversation.spaceId,
          senderId: conversation.agentId,
          ...(options.parentId ? { parentMessageId: options.parentId } : {}),
          content: body,
        },
      }),
    );
    // The client's narrowed SentMessage type erases fields; at runtime it is a Message with a string id.
    const id: unknown = (sent as { id?: unknown }).id;
    if (typeof id !== "string") throw new Error(`Photon sendMessage returned no message id: ${JSON.stringify(sent).slice(0, 200)}`);
    return id;
  }

  async react(conversation: Conversation, messageId: string, emoji: string, key?: string): Promise<void> {
    await this.call("sendMessage(reaction)", () =>
      this.photon.projects.sendMessage({
        path: this.project,
        headers: { "idempotency-key": key ?? randomUUID() },
        body: {
          spaceId: conversation.spaceId,
          senderId: conversation.agentId,
          parentMessageId: messageId,
          content: { type: "reaction", action: "add", reaction: emoji },
        },
      }),
    );
  }

  /** POST /attachments takes multipart/related: a JSON part describing the file, then its bytes. */
  private async upload(path: string, mimeType: string, key: string): Promise<string> {
    const bytes = await readFile(path);
    // Retries reuse the upload's idempotency key, so their bytes must also match.
    const boundary = `marco-${createHash("sha256").update(key).digest("hex")}`;
    const meta = JSON.stringify({ contentType: mimeType, sizeBytes: bytes.length, filename: basename(path) });
    const body = new Blob([
      `--${boundary}\r\nContent-Type: application/json\r\n\r\n${meta}\r\n--${boundary}\r\nContent-Type: ${mimeType}\r\n\r\n`,
      new Uint8Array(bytes),
      `\r\n--${boundary}--\r\n`,
    ]);
    const attachment = await this.call("uploadAttachment", () =>
      this.photon.projects.uploadAttachment({
        path: this.project,
        headers: {
          "content-length": String(body.size),
          "content-type": `multipart/related; boundary=${boundary}`,
          "idempotency-key": key,
        },
        body,
      }),
    );
    return attachment.id;
  }

  /** Lazily fetched bytes. Photon answers ATTACHMENT_NOT_READY (Retry-After: 5) while an inbound file is still arriving. */
  private async download(attachmentId: string): Promise<Buffer> {
    for (let attempt = 1; ; attempt++) {
      try {
        const data: unknown = await this.photon.projects.downloadAttachment({ path: { ...this.project, attachmentId } });
        if (data instanceof Blob) return Buffer.from(await data.arrayBuffer());
        if (data instanceof ArrayBuffer || ArrayBuffer.isView(data)) return Buffer.from(data as ArrayBuffer);
        throw new Error(`unexpected attachment body: ${typeof data}`);
      } catch (err) {
        const notReady = err instanceof ApiError && JSON.stringify(err.body ?? "").includes("ATTACHMENT_NOT_READY");
        if (!notReady || attempt >= 4) throw describe(err, "downloadAttachment");
        await new Promise((r) => setTimeout(r, 5_000));
      }
    }
  }

  private async media(attachmentId: string, fallbackMime: string): Promise<Part> {
    let mimeType = fallbackMime;
    let name: string | null = null;
    try {
      const meta = await this.photon.projects.getAttachment({ path: { ...this.project, attachmentId } });
      mimeType = meta.contentType || fallbackMime;
      name = meta.filename ?? null;
    } catch (err) {
      log.warn(String(describe(err, "getAttachment")));
    }
    let bytes: Promise<Buffer> | undefined;
    return { type: "media", mimeType, name, read: () => (bytes ??= this.download(attachmentId)) };
  }

  private async parts(content: WireContent): Promise<Part[]> {
    switch (content.type) {
      case "text":
        return content.text?.trim() ? [{ type: "text", text: content.text }] : [];
      case "attachment":
        return content.attachmentId ? [await this.media(content.attachmentId, "application/octet-stream")] : [];
      case "voice":
        return content.attachmentId ? [await this.media(content.attachmentId, "audio/x-caf")] : [];
      case "group": {
        const nested = await Promise.all((content.parts ?? []).map((p) => this.parts(p)));
        return nested.flat();
      }
      default:
        return [];
    }
  }

  /** Turns a delivered event into an Inbound, or null for anything the agent doesn't act on. */
  async toInbound(event: WireEvent): Promise<Inbound | null> {
    if (event.type === "message.failed") {
      log.warn(`Photon could not deliver message ${event.data?.object?.id}: ${JSON.stringify(event.data?.object).slice(0, 400)}`);
      return null;
    }
    const m = event.data?.object;
    if (event.type !== "message.received" || !m || m.status !== "received") return null;
    // The same checks as the Beta iMessage guide's agent: a human sender, our agent receiving, a direct conversation.
    const agentId = m.receivedBy?.id ?? m.addressedTo?.id;
    if (m.sentBy.kind !== "human" || !agentId || m.sentBy.id === agentId) return null;
    if (m.platform === "imessage" && m.space.kind !== "direct") return null;
    const conversation = { platform: m.platform, spaceId: m.space.id, agentId };
    const base = { id: m.id, from: m.sentBy.handle, conversation, parentId: m.parentMessageId ?? null };
    if (m.content.type === "message.read") return { ...base, kind: "read", parts: [] };
    const parts = await this.parts(m.content);
    return parts.length ? { ...base, kind: "message", parts } : null;
  }

  /** Runs an API call and turns ApiError into a message that says what Photon objected to. */
  private async call<T>(what: string, fn: () => Promise<T>): Promise<T> {
    try {
      return await fn();
    } catch (err) {
      throw describe(err, what);
    }
  }
}

function describe(err: unknown, what: string): Error {
  if (err instanceof ApiError) {
    const detail = typeof err.body === "object" ? JSON.stringify(err.body) : (err.rawBody ?? String(err.body));
    return new Error(`Photon ${what} failed: HTTP ${err.status} (request ${err.requestId ?? "?"}) ${detail.slice(0, 500)}`);
  }
  return err instanceof Error ? err : new Error(String(err));
}

export interface EventStream {
  stop(): void;
}

/**
 * Subscribes to the project's events (https://photon.codes/docs/beta/websocket). Deliveries are handled one at a
 * time, in order, and the cursor is saved after each, so a restart resumes where it left off.
 */
export function startEvents(
  config: PhotonConfig,
  cursor: { load(): number; save(seq: number): void },
  onEvent: (event: WireEvent) => Promise<void>,
): EventStream {
  const socket: Socket = io(config.origin, {
    path: `/v1/projects/${config.projectId}/events/ws`,
    addTrailingSlash: false,
    transports: ["websocket"],
    extraHeaders: { Authorization: `Bearer ${config.apiKey}` },
    autoConnect: false,
  });
  let last = cursor.load();
  let epoch = 0;
  let pending = 0;
  let queue = Promise.resolve();
  const attempts = new Map<number, number>();

  socket.on("connect", () => {
    socket.timeout(10_000).emit("subscribe", { startSeq: last, apiVersion: EVENT_API_VERSION }, (error: unknown, result: { ok: boolean; error?: { code: string; message: string }; connectionId?: string }) => {
      if (error) {
        log.warn("Photon subscribe timed out; reconnecting");
        socket.io.engine.close();
      } else if (!result.ok) {
        log.error(`Photon subscribe rejected: ${result.error?.code} ${result.error?.message}`);
      } else {
        log.info(`Photon events subscribed (connection ${result.connectionId}, from cursor ${last})`);
      }
    });
  });
  socket.on("disconnect", (reason) => {
    epoch++;
    log.warn(`Photon events disconnected: ${reason}`);
  });
  socket.on("connect_error", (err) => log.error(`Photon events connect error: ${err.message}`));
  socket.on("delivery_error", (err: { code: string; message: string }) => log.warn(`Photon delivery error: ${err.code} ${err.message}`));
  socket.on("delivery", (event: WireEvent, meta: { seq: number }) => {
    const generation = epoch;
    if (++pending > MAX_PENDING) {
      // Too far behind: drop the connection; unprocessed deliveries replay from the saved cursor.
      pending--;
      epoch++;
      socket.io.engine.close();
      return;
    }
    queue = queue
      .then(async () => {
        if (generation !== epoch || meta.seq <= last) return;
        try {
          await onEvent(event);
        } catch (err) {
          const tries = (attempts.get(meta.seq) ?? 0) + 1;
          attempts.set(meta.seq, tries);
          if (tries < MAX_ATTEMPTS) {
            // As the Beta docs prescribe: stop this stream without checkpointing; the reconnect replays from `last`.
            log.warn(`event ${event.id} (${event.type}) failed (attempt ${tries}); resuming from cursor ${last}`, err);
            if (generation === epoch) {
              epoch++;
              socket.io.engine.close();
            }
            return;
          }
          log.error(`event ${event.id} (${event.type}) failed ${tries} times; skipping it`, err);
        }
        attempts.delete(meta.seq);
        last = meta.seq;
        cursor.save(last);
      })
      .finally(() => {
        pending--;
      });
  });

  socket.connect();
  return { stop: () => socket.disconnect() };
}
