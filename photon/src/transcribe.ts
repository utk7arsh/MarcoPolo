import { readFile } from "node:fs/promises";
import { basename } from "node:path";
import { log } from "./log.js";

/** Returns the transcript of an audio file, or null when unavailable. Never throws. */
export type Transcriber = (path: string) => Promise<string | null>;

export const noTranscriber: Transcriber = async () => null;

/** ElevenLabs Scribe (POST /v1/speech-to-text). Language is auto-detected, so a label in Hindi or Spanish works too. */
export function elevenLabsTranscriber(apiKey: string, model: string): Transcriber {
  return async (path) => {
    try {
      const form = new FormData();
      form.append("model_id", model);
      form.append("tag_audio_events", "false");
      form.append("file", new Blob([await readFile(path)]), basename(path));
      const res = await fetch("https://api.elevenlabs.io/v1/speech-to-text", {
        method: "POST",
        headers: { "xi-api-key": apiKey },
        body: form,
        signal: AbortSignal.timeout(20_000),
      });
      if (!res.ok) {
        log.warn(`ElevenLabs STT ${res.status}: ${(await res.text()).slice(0, 300)}`);
        return null;
      }
      const body = (await res.json()) as { text?: string };
      return body.text?.trim() || null;
    } catch (err) {
      log.warn("ElevenLabs STT failed", err);
      return null;
    }
  };
}
