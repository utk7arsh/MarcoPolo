import { readFile } from "node:fs/promises";
import type { ItemView } from "./events.js";
import { log } from "./log.js";
import { contentTypeFor, type Media } from "./media.js";
import type { Item } from "./store.js";

/** POC 26's response: {item_id, quality, reason, box}. item_id is null on retake. */
export interface Registration {
  item_id: string | null;
  quality: "ok" | "retake";
  reason?: string;
}

/**
 * Client for the main FastAPI server (requirements §5 API contract). Every call is a no-op
 * when MARCO_SERVER_URL is unset, so this service also runs on its own.
 */
export class MarcoServer {
  constructor(
    private readonly baseUrl: string | null,
    private readonly media: Media,
  ) {}

  get enabled(): boolean {
    return this.baseUrl !== null;
  }

  /** POST /items: photo + name. The server boxes the item by name and says whether the photo is usable. */
  async registerItem(item: Item): Promise<Registration | null> {
    if (!this.baseUrl || !item.photo || !item.name) return null;
    try {
      const form = new FormData();
      form.append("name", item.name);
      form.append("item_id", item.id);
      form.append("source", "caretaker");
      const photo = await readFile(this.media.path(item.photo));
      form.append("photo", new Blob([photo], { type: contentTypeFor(item.photo) }), item.photo);
      const res = await fetch(`${this.baseUrl}/items`, { method: "POST", body: form, signal: AbortSignal.timeout(15_000) });
      if (!res.ok) {
        log.warn(`POST /items ${res.status}`);
        return null;
      }
      return (await res.json()) as Registration;
    } catch (err) {
      log.warn("POST /items failed", err);
      return null;
    }
  }

  /** POST /labels/reply: hands a caretaker's answer to the main server, which pushes it to the phone. */
  async labelReply(requestId: string | null, item: ItemView): Promise<void> {
    if (!this.baseUrl) return;
    try {
      const res = await fetch(`${this.baseUrl}/labels/reply`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ request_id: requestId, item }),
        signal: AbortSignal.timeout(10_000),
      });
      if (!res.ok) log.warn(`POST /labels/reply ${res.status}`);
    } catch (err) {
      log.warn("POST /labels/reply failed", err);
    }
  }
}
