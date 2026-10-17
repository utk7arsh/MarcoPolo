import type { Media } from "./media.js";
import type { Item } from "./store.js";

/** Wire shape of an item, shared by HTTP responses and events (snake_case, absolute media URLs). */
export interface ItemView {
  id: string;
  name: string | null;
  origin: Item["origin"];
  /** Same item's id on the main server (POST /items), once registered. */
  server_item_id: string | null;
  photo_url: string | null;
  label: {
    name: string | null;
    text: string | null;
    transcript: string | null;
    /** Play this when present; otherwise speak `text` (or `name`). */
    audio_url: string | null;
    author: string;
    created_at: string;
  } | null;
  created_at: string;
  updated_at: string;
}

export function itemView(item: Item, media: Media): ItemView {
  const label = item.label;
  return {
    id: item.id,
    name: item.name,
    origin: item.origin,
    server_item_id: item.serverItemId ?? null,
    photo_url: media.url(item.photo),
    label: label && {
      name: label.name,
      text: label.text,
      transcript: label.transcript,
      audio_url: media.url(label.audio),
      author: label.author,
      created_at: label.createdAt,
    },
    created_at: item.createdAt,
    updated_at: item.updatedAt,
  };
}

export type MarcoEvent =
  /** A caretaker labeled an item. `request_id` is set when it answers the user's "what is this?". */
  | { type: "label_ready"; request_id: string | null; item: ItemView }
  /** The caretaker answered "I don't know". */
  | { type: "label_unknown"; request_id: string; item_id: string; caretaker: string }
  | { type: "label_request_sent"; request_id: string; item_id: string; caretaker: string }
  /** iMessage read receipt: the caretaker opened the photo. Lets the phone say "Mom is looking at it." */
  | { type: "label_request_seen"; request_id: string; item_id: string; caretaker: string }
  | { type: "caretaker_linked"; caretaker: string };

export type StampedEvent = MarcoEvent & { at: string };

export class EventBus {
  private readonly subscribers = new Set<(event: StampedEvent) => void>();
  readonly recent: StampedEvent[] = [];

  subscribe(fn: (event: StampedEvent) => void): () => void {
    this.subscribers.add(fn);
    return () => this.subscribers.delete(fn);
  }

  emit(event: MarcoEvent) {
    const stamped = { ...event, at: new Date().toISOString() };
    this.recent.push(stamped);
    if (this.recent.length > 100) this.recent.shift();
    for (const fn of this.subscribers) {
      try {
        fn(stamped);
      } catch {
        // one broken socket must not block the others
      }
    }
  }
}
