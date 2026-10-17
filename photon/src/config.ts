export type Mode = "imessage" | "terminal" | "sim";

export interface Config {
  mode: Mode;
  port: number;
  dataDir: string;
  /** Base URL the phone and the family page use to fetch /media files. */
  publicBaseUrl: string;
  /** When set, every route except /health and /media requires `Authorization: Bearer <token>` (or `?token=`). */
  bridgeToken: string | null;
  /** How Marco refers to the person it helps, e.g. "Dad". */
  userName: string;
  /** Normalized caretaker handle -> display name, e.g. "+13105550101" -> "Mom". */
  caretakerNames: Map<string, string>;
  /** Handle that receives "what is this?" photos. Defaults to the first caretaker who texted Marco. */
  primaryCaretaker: string | null;
  elevenLabsKey: string | null;
  sttModel: string;
  /** Main FastAPI server. When set, caretaker photos are registered there and labels are forwarded. */
  marcoServerUrl: string | null;
  /** Wait this long after a bare photo before asking "what is this?", so a caption sent right after it wins. */
  promptDelayMs: number;
}

/** Canonical form for an iMessage handle: E.164 for phone numbers, lowercase for emails. */
export function normalizeHandle(raw: string): string {
  const handle = raw.trim();
  if (handle.includes("@")) return handle.toLowerCase();
  const digits = handle.replace(/\D/g, "");
  if (handle.startsWith("+") && digits) return `+${digits}`;
  if (digits.length === 10) return `+1${digits}`;
  if (digits.length === 11 && digits.startsWith("1")) return `+${digits}`;
  return handle;
}

/** Parses `+13105550101=Mom,mom@icloud.com=Mom`. */
export function parseCaretakers(raw: string | undefined): Map<string, string> {
  const names = new Map<string, string>();
  for (const pair of (raw ?? "").split(",")) {
    const [handle, name] = pair.split("=").map((s) => s.trim());
    if (handle && name) names.set(normalizeHandle(handle), name);
  }
  return names;
}

export function loadConfig(env: NodeJS.ProcessEnv = process.env): Config {
  const mode = (env.PHOTON_MODE ?? (env.SPECTRUM_PROJECT_ID ? "imessage" : "sim")) as Mode;
  if (!["imessage", "terminal", "sim"].includes(mode)) {
    throw new Error(`PHOTON_MODE must be imessage, terminal or sim (got "${mode}")`);
  }
  if (mode === "imessage" && !(env.SPECTRUM_PROJECT_ID && env.SPECTRUM_PROJECT_SECRET)) {
    throw new Error("PHOTON_MODE=imessage needs SPECTRUM_PROJECT_ID and SPECTRUM_PROJECT_SECRET (dashboard Settings)");
  }
  const port = Number(env.PORT ?? 8787);
  return {
    mode,
    port,
    dataDir: env.DATA_DIR ?? "./data",
    publicBaseUrl: (env.PUBLIC_BASE_URL ?? `http://localhost:${port}`).replace(/\/$/, ""),
    bridgeToken: env.BRIDGE_TOKEN || null,
    userName: env.MARCO_USER_NAME ?? "Dad",
    caretakerNames: parseCaretakers(env.CARETAKERS),
    primaryCaretaker: env.PRIMARY_CARETAKER ? normalizeHandle(env.PRIMARY_CARETAKER) : null,
    elevenLabsKey: env.ELEVENLABS_API_KEY || null,
    sttModel: env.ELEVENLABS_STT_MODEL ?? "scribe_v2",
    marcoServerUrl: env.MARCO_SERVER_URL ? env.MARCO_SERVER_URL.replace(/\/$/, "") : null,
    promptDelayMs: Number(env.PROMPT_DELAY_MS ?? 2500),
  };
}
