// The Marco server's Photon routes, exactly as docs/INTERFACES.md §5 (and server/marco/app.py) define them.
// Reach the server through its `tailscale serve` URL, even on the server's own machine: the fail-closed gate admits
// only tailnet logins in TAILSCALE_ALLOWED_LOGINS, and only `tailscale serve` adds that identity.
import { readFile } from "node:fs/promises";
import { basename } from "node:path";
import { log } from "./log.js";
import { contentTypeFor } from "./media.js";

/** Sent on WebSocket /v1/photon when the user asks "what is this?" about something unknown. */
export interface LabelRequest {
  type: "label_request";
  touch_id: string;
  crop_url: string;
  question?: string;
}

/** POST /v1/items reply. `item_id` is null on a retake. */
export interface Registration {
  item_id: string | null;
  quality: "ok" | "retake";
  reason?: string;
}

/** POST /v1/labels reply: the item the label landed on (a later voice note is posted to it). */
export interface LabelResult {
  status: string;
  item_id: string | null;
}

export interface LabelPost {
  /** Label what was touched (the first answer to a label_request). */
  touchId?: string;
  /** Or add to / relabel an item the server already has. */
  itemId?: string;
  /** Short name, e.g. "cumin". Required by the server. */
  name: string;
  /** The caretaker's words, which the phone speaks. */
  text?: string | null;
  /** The voice memo, any format; the server keeps the file's extension. */
  audioPath?: string | null;
}

export interface MarcoServerApi {
  getCrop(cropUrl: string): Promise<Buffer>;
  postLabel(label: LabelPost): Promise<LabelResult>;
  postItem(name: string, photoPath: string): Promise<Registration>;
}

/** An error from the server. `permanent` means retrying the same request cannot help (4xx other than 408/429). */
export class MarcoServerError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "MarcoServerError";
  }

  get permanent(): boolean {
    return this.status >= 400 && this.status < 500 && this.status !== 408 && this.status !== 429;
  }
}

const NOT_AUTHORISED =
  "the Marco server refused this machine (fail-closed gate). Use its tailscale serve URL, and check that this machine's tailnet login is in TAILSCALE_ALLOWED_LOGINS";

export class MarcoServer implements MarcoServerApi {
  readonly base: string;

  constructor(
    base: string,
    private readonly fetchImpl: typeof fetch = fetch,
  ) {
    this.base = base.replace(/\/+$/, "");
  }

  private url(path: string): string {
    return new URL(path, `${this.base}/`).toString();
  }

  private async call(what: string, path: string, init?: RequestInit): Promise<Response> {
    const res = await this.fetchImpl(this.url(path), { ...init, signal: AbortSignal.timeout(20_000) });
    if (res.ok) return res;
    const body = (await res.text()).slice(0, 300);
    throw new MarcoServerError(res.status === 403 ? `${what}: ${NOT_AUTHORISED}` : `${what}: HTTP ${res.status} ${body}`, res.status);
  }

  async getCrop(cropUrl: string): Promise<Buffer> {
    const res = await this.call("GET crop", cropUrl);
    return Buffer.from(await res.arrayBuffer());
  }

  async postLabel({ touchId, itemId, name, text, audioPath }: LabelPost): Promise<LabelResult> {
    const form = new FormData();
    if (touchId) form.append("touch_id", touchId);
    if (itemId) form.append("item_id", itemId);
    form.append("name", name);
    if (text) form.append("text", text);
    if (audioPath) form.append("audio", new Blob([new Uint8Array(await readFile(audioPath))], { type: contentTypeFor(audioPath) }), basename(audioPath));
    const res = await this.call("POST /v1/labels", "/v1/labels", { method: "POST", body: form });
    return (await res.json()) as LabelResult;
  }

  async postItem(name: string, photoPath: string): Promise<Registration> {
    const form = new FormData();
    form.append("name", name);
    form.append("photo", new Blob([new Uint8Array(await readFile(photoPath))], { type: contentTypeFor(photoPath) }), basename(photoPath));
    const res = await this.call("POST /v1/items", "/v1/items", { method: "POST", body: form });
    return (await res.json()) as Registration;
  }
}

export function photonSocketUrl(base: string): string {
  const url = new URL("/v1/photon", `${base.replace(/\/+$/, "")}/`);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  return url.toString();
}

export interface PhotonSocket {
  readonly connected: boolean;
  close(): void;
}

/**
 * The server's /v1/photon WebSocket (server to bridge only), reconnecting with backoff. The server does not queue
 * label requests for a disconnected bridge, so the connection state is surfaced on /health.
 */
export function connectPhotonSocket(
  base: string,
  onRequest: (request: LabelRequest) => Promise<unknown>,
  { WebSocketImpl = globalThis.WebSocket, onState = () => {} }: { WebSocketImpl?: typeof WebSocket; onState?: (up: boolean) => void } = {},
): PhotonSocket {
  if (!WebSocketImpl) throw new Error("no WebSocket implementation: use Node 22 or later");
  const url = photonSocketUrl(base);
  let ws: WebSocket | null = null;
  let up = false;
  let stopped = false;
  let backoff = 500;
  let queue: Promise<unknown> = Promise.resolve();

  const connect = () => {
    const socket = new WebSocketImpl(url);
    ws = socket;
    socket.onopen = () => {
      up = true;
      backoff = 500;
      onState(true);
      log.info(`connected to the Marco server at ${url}`);
    };
    socket.onmessage = (ev: MessageEvent) => {
      let msg: { type?: string };
      try {
        msg = JSON.parse(typeof ev.data === "string" ? ev.data : new TextDecoder().decode(ev.data as ArrayBuffer));
      } catch (err) {
        log.warn("unreadable message on /v1/photon", err);
        return;
      }
      if (msg.type !== "label_request") return;
      const request = msg as LabelRequest;
      // One request at a time, in arrival order.
      queue = queue.then(() => onRequest(request)).catch((err) => log.error(`label_request ${request.touch_id} failed`, err));
    };
    socket.onclose = (ev: CloseEvent) => {
      if (up) onState(false);
      up = false;
      if (ev.code === 1008) log.error(`/v1/photon closed with 1008: ${NOT_AUTHORISED}`);
      if (stopped) return;
      setTimeout(connect, backoff);
      backoff = Math.min(backoff * 2, 8_000);
    };
    socket.onerror = () => {};
  };
  connect();

  return {
    get connected() {
      return up;
    },
    close() {
      stopped = true;
      ws?.close();
    },
  };
}
