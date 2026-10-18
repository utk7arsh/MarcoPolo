export type Mode = "photon" | "sim";

export interface Config {
  mode: Mode;
  /** Photon 2.0 project (app.beta.photon.codes). Null in sim mode. */
  photon: { origin: string; projectId: string; apiKey: string } | null;
  /** Local status port (/health, and /dev in sim mode). Bound to 127.0.0.1 only. */
  port: number;
  dataDir: string;
  /** How Marco refers to the person it helps, e.g. "Dad". */
  userName: string;
  /** Normalized caretaker handle -> display name, e.g. "+13105550101" -> "Mom". */
  caretakerNames: Map<string, string>;
  /** Handle that receives "what is this?" photos. Defaults to the first caretaker who texted Marco. */
  primaryCaretaker: string | null;
  elevenLabsKey: string | null;
  sttModel: string;
  /** The Marco server's `tailscale serve` URL (docs/INTERFACES.md §5): label_request in, labels and registrations out. */
  marcoServerUrl: string;
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
  const mode = (env.PHOTON_MODE ?? (env.PHOTON_API_KEY ? "photon" : "sim")) as Mode;
  if (!["photon", "sim"].includes(mode)) {
    throw new Error(
      `PHOTON_MODE must be photon or sim (got "${mode}"). This build runs on Photon 2.0: set PHOTON_MODE=photon, ` +
        "PHOTON_PROJECT_ID and PHOTON_API_KEY (see .env.example); the SPECTRUM_* variables are no longer used.",
    );
  }
  let photon: Config["photon"] = null;
  if (mode === "photon") {
    const projectId = env.PHOTON_PROJECT_ID ?? "";
    const apiKey = env.PHOTON_API_KEY ?? "";
    if (!projectId || !apiKey) {
      throw new Error("PHOTON_MODE=photon needs PHOTON_PROJECT_ID and PHOTON_API_KEY from https://app.beta.photon.codes (project Settings and API keys)");
    }
    if (!projectId.startsWith("pho_prj_")) {
      throw new Error(`PHOTON_PROJECT_ID should start with pho_prj_ (a Photon 2.0 project from app.beta.photon.codes). "${projectId.slice(0, 6)}..." looks like an old Spectrum project.`);
    }
    if (!/^(pho_sk_|pho_ask_)/.test(apiKey)) {
      console.warn("PHOTON_API_KEY usually starts with pho_sk_ (project API key) or pho_ask_ (account service key)");
    }
    photon = { origin: (env.PHOTON_API_ORIGIN ?? "https://api.photon.codes").replace(/\/$/, ""), projectId, apiKey };
  }
  const marcoServerUrl = (env.MARCO_SERVER_URL ?? "").trim().replace(/\/+$/, "");
  if (!marcoServerUrl) {
    throw new Error(
      "Set MARCO_SERVER_URL to the Marco server's tailscale serve URL (https://<machine>.<tailnet>.ts.net), " +
        "or http://127.0.0.1:8000 for a local server started with AUTH_TEST_BYPASS=1",
    );
  }
  return {
    mode,
    photon,
    port: Number(env.PORT ?? 8787),
    dataDir: env.DATA_DIR ?? "./data",
    userName: env.MARCO_USER_NAME ?? "Dad",
    caretakerNames: parseCaretakers(env.CARETAKERS),
    primaryCaretaker: env.PRIMARY_CARETAKER ? normalizeHandle(env.PRIMARY_CARETAKER) : null,
    elevenLabsKey: env.ELEVENLABS_API_KEY || null,
    sttModel: env.ELEVENLABS_STT_MODEL ?? "scribe_v2",
    marcoServerUrl,
    promptDelayMs: Number(env.PROMPT_DELAY_MS ?? 2500),
  };
}
