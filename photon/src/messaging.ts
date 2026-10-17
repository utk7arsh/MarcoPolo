import { Spectrum, type Message, type Space } from "spectrum-ts";
import { imessage } from "spectrum-ts/providers/imessage";
import { terminal } from "spectrum-ts/providers/terminal";
import type { Config } from "./config.js";
import { log } from "./log.js";
import type { SimPlatform } from "./sim.js";

export interface Messaging {
  /** Reopens a stored conversation by its Spectrum space id (iMessage chat GUID). */
  lookup(platform: string, spaceId: string): Promise<Space | undefined>;
  stop(): Promise<void>;
}

type OnMessage = (space: Space, message: Message) => Promise<void>;

/**
 * imessage: Photon's cloud lines. Credentials come from SPECTRUM_PROJECT_ID / SPECTRUM_PROJECT_SECRET.
 * terminal: Spectrum's chat TUI; you play the caretaker. No credentials.
 */
export async function startSpectrum(config: Config, onMessage: OnMessage): Promise<Messaging> {
  if (config.mode === "imessage") {
    const app = await Spectrum({ providers: [imessage.config()] });
    return consume(app, onMessage, async (spaceId) => (await imessage(app).space.get(spaceId)) as unknown as Space);
  }
  const app = await Spectrum({ providers: [terminal.config()] });
  return consume(app, onMessage, async (spaceId) => (await terminal(app).space.get(spaceId)) as unknown as Space);
}

export function simMessaging(sim: SimPlatform): Messaging {
  return { lookup: async (_platform, spaceId) => sim.spaceById(spaceId), stop: async () => {} };
}

function consume(
  app: { messages: AsyncIterable<readonly [Space, Message]>; stop(): Promise<void> },
  onMessage: OnMessage,
  get: (spaceId: string) => Promise<Space>,
): Messaging {
  // Sequential on purpose: a photo and the caption sent right after it must be handled in order.
  const loop = (async () => {
    for await (const [space, message] of app.messages) {
      try {
        await onMessage(space, message);
      } catch (err) {
        log.error(`failed on message ${message.id}`, err);
      }
    }
  })();
  return {
    lookup: async (_platform, spaceId) => get(spaceId),
    stop: async () => {
      await app.stop();
      await loop.catch(() => {});
    },
  };
}
