// Read-only checks before a live run: `npm run doctor`. Sends nothing to anyone.
// Photon 2.0, per the Beta docs: projects.get (api-client/credentials), the iMessage platform and its shared-line
// assignments (get-started/imessage), and one event-stream subscribe (websocket/session).
// The Marco server, per docs/INTERFACES.md §5: GET /v1/items through MARCO_SERVER_URL, and the /v1/photon socket.
import { ApiError, Photon } from "@photon-ai/api";
import { io } from "socket.io-client";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { loadConfig, normalizeHandle } from "./config.js";
import { photonSocketUrl } from "./marco-server.js";

try {
  process.loadEnvFile();
} catch {
  // no .env file
}

let failures = 0;
const ok = (msg: string) => console.log(`  ok    ${msg}`);
const bad = (msg: string) => {
  failures++;
  console.log(`  FAIL  ${msg}`);
};
const skip = (msg: string) => console.log(`  skip  ${msg}`);
// Reading channel settings needs platforms:read, which Marco itself does not use (it needs only project:read and project:write).
const forbidden = (err: unknown) => err instanceof ApiError && err.status === 403;
const NEEDS_PLATFORMS_READ = "this key has no platforms:read (Marco doesn't need it; add it to the key to see Marco's number here, or read it in the dashboard under iMessage)";
const why = (err: unknown) =>
  err instanceof ApiError ? `HTTP ${err.status} ${typeof err.body === "object" ? JSON.stringify(err.body).slice(0, 300) : (err.rawBody ?? "")}` : String(err);

console.log("Photon 2.0");
const serverUrl = (process.env.MARCO_SERVER_URL ?? "").trim().replace(/\/+$/, "");
let config;
try {
  // The server is checked separately below, so a missing MARCO_SERVER_URL doesn't hide the Photon results.
  config = loadConfig({ ...process.env, PHOTON_MODE: process.env.PHOTON_MODE || "photon", MARCO_SERVER_URL: serverUrl || "http://unset.invalid" });
} catch (err) {
  bad(err instanceof Error ? err.message : String(err));
  process.exit(1);
}
const photon = config.photon!;
ok(`project ${photon.projectId.slice(0, 12)}..., key ${photon.apiKey.slice(0, 7)}..., origin ${photon.origin}`);

const client = new Photon({ baseUrl: photon.origin, headers: { Authorization: `Bearer ${photon.apiKey}` } });

// Do not instantiate Store: a diagnostic must not migrate or change saved state.
const stateFile = join(config.dataDir, "marco-photon.json");
if (existsSync(stateFile)) {
  try {
    const state = JSON.parse(readFileSync(stateFile, "utf8")) as { questions?: Record<string, { kind: string; status: string }> };
    const pending = Object.values(state.questions ?? {}).filter((q) => q.kind === "identify" && q.status === "pending").length;
    if (pending) bad(`${pending} identification request(s) still pending: crop/message delivery has not completed. Inspect before retrying; an old request may be test data.`);
    else ok("no incomplete identification sends in local state");
  } catch {
    bad("cannot read saved bridge state");
  }
}
if (!config.caretakerNames.size) bad("CARETAKERS is empty: nobody may label or receive a photo");
if (config.primaryCaretaker && !config.caretakerNames.has(config.primaryCaretaker)) bad("PRIMARY_CARETAKER is not in CARETAKERS");

try {
  const project = (await client.projects.get({ path: { projectId: photon.projectId } })) as { name?: string };
  ok(`credentials accepted (project "${project.name ?? "?"}")`);
} catch (err) {
  bad(`credentials: ${why(err)}`);
}

try {
  await client.projects.platforms.getImessage({ path: { id: photon.projectId } });
  ok("iMessage platform is set up on this project");
} catch (err) {
  if (forbidden(err)) skip(`iMessage platform: ${NEEDS_PLATFORMS_READ}`);
  else bad(`iMessage platform: ${why(err)}`);
}

try {
  const page = await client.projects.platforms.imessage.assignments.list({ path: { id: photon.projectId } });
  const active = page.assignments.filter((a) => !a.releasedAt);
  if (!active.length) bad("no shared iMessage line assigned: dashboard > iMessage > add the caretaker's number");
  for (const a of active) {
    const name = config.caretakerNames.get(normalizeHandle(a.handle));
    ok(`caretaker ${a.handle}${name ? ` (${name})` : " (not in CARETAKERS)"} texts Marco at ${a.assignedPhoneNumber}`);
  }
  for (const [handle, name] of config.caretakerNames) {
    if (!active.some((a) => normalizeHandle(a.handle) === handle)) bad(`${name} (${handle}) is in CARETAKERS but has no assigned line`);
  }
} catch (err) {
  if (forbidden(err)) skip(`assigned numbers: ${NEEDS_PLATFORMS_READ}`);
  else bad(`assignments: ${why(err)}`);
}

await new Promise<void>((resolve) => {
  const socket = io(photon.origin, {
    path: `/v1/projects/${photon.projectId}/events/ws`,
    addTrailingSlash: false,
    transports: ["websocket"],
    extraHeaders: { Authorization: `Bearer ${photon.apiKey}` },
    reconnection: false,
  });
  const done = (msg: string, good: boolean) => {
    (good ? ok : bad)(msg);
    socket.disconnect();
    resolve();
  };
  const timer = setTimeout(() => done("event stream: no answer within 10 s", false), 10_000);
  socket.on("connect_error", (err) => (clearTimeout(timer), done(`event stream: ${err.message}`, false)));
  socket.on("connect", () => {
    socket.emit("subscribe", { startSeq: 0, apiVersion: "2026-07-01" }, (result: { ok: boolean; error?: { code: string }; connectionId?: string }) => {
      clearTimeout(timer);
      done(result.ok ? `event stream subscribed (connection ${result.connectionId})` : `event stream rejected: ${result.error?.code}`, result.ok);
    });
  });
});

console.log("Marco server (docs/INTERFACES.md §5)");
if (!serverUrl) {
  bad("MARCO_SERVER_URL is not set: the Marco server's tailscale serve URL, e.g. https://marco-gpu.<tailnet>.ts.net");
} else {
  ok(`server ${serverUrl}`);
  try {
    const res = await fetch(`${serverUrl}/v1/items`, { signal: AbortSignal.timeout(10_000) });
    if (res.ok) ok(`GET /v1/items: ${((await res.json()) as unknown[]).length} item(s) on the server`);
    else if (res.status === 403) bad("GET /v1/items: 403. Use the tailscale serve URL, and add this machine's tailnet login to TAILSCALE_ALLOWED_LOGINS on the server");
    else bad(`GET /v1/items: HTTP ${res.status}`);
  } catch (err) {
    bad(`GET /v1/items: ${err instanceof Error ? (err.cause instanceof Error ? err.cause.message : err.message) : String(err)}. Is the server up, and is this machine on the tailnet?`);
  }
  await new Promise<void>((resolve) => {
    const ws = new WebSocket(photonSocketUrl(serverUrl));
    const finish = (good: boolean, msg: string) => {
      clearTimeout(timer);
      (good ? ok : bad)(msg);
      ws.onclose = null;
      ws.close();
      resolve();
    };
    const timer = setTimeout(() => finish(false, "/v1/photon: no answer within 10 s"), 10_000);
    ws.onopen = () => setTimeout(() => finish(true, "/v1/photon accepted the socket (connection only; not proof of iMessage delivery)"), 300);
    ws.onclose = (ev) => finish(false, ev.code === 1008 ? "/v1/photon closed with 1008: this machine's login is not in TAILSCALE_ALLOWED_LOGINS" : `/v1/photon closed (${ev.code})`);
    ws.onerror = () => {};
  });
}

console.log(failures ? `\n${failures} problem(s). Fix them before the live test.` : "\nAll good. Have the caretaker text Marco's number, then npm start.");
process.exit(failures ? 1 : 0);
