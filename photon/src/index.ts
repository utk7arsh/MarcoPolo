import { MarcoAgent } from "./agent.js";
import { loadConfig } from "./config.js";
import { startHttp } from "./http.js";
import { log } from "./log.js";
import { connectPhotonSocket, MarcoServer, type PhotonSocket } from "./marco-server.js";
import { Media } from "./media.js";
import { PhotonChannel, startEvents, type EventStream } from "./photon.js";
import { SimChannel } from "./sim.js";
import { Store } from "./store.js";
import { elevenLabsTranscriber, noTranscriber } from "./transcribe.js";

try {
  process.loadEnvFile();
} catch {
  // no .env file; rely on the environment
}

const config = loadConfig();
const store = new Store(config.dataDir);
const media = new Media(config.dataDir);
const sim = config.photon ? null : new SimChannel();
const photon = config.photon ? new PhotonChannel(config.photon) : null;
const server = new MarcoServer(config.marcoServerUrl);

const agent = new MarcoAgent({
  config,
  store,
  media,
  channel: photon ?? sim!,
  transcribe: config.elevenLabsKey ? elevenLabsTranscriber(config.elevenLabsKey, config.sttModel) : noTranscriber,
  server,
});

let socket: PhotonSocket | null = null;

// Bind the status port first: a second copy must exit here, not become a second consumer of the same line.
const http = startHttp({ config, agent, store, sim, serverConnected: () => socket?.connected ?? false });
await new Promise<void>((resolve, reject) => {
  http.once("listening", resolve);
  http.once("error", reject);
}).catch((err: NodeJS.ErrnoException) => {
  log.error(
    err.code === "EADDRINUSE"
      ? `port ${config.port} is in use. Is Marco already running? Find it with: lsof -nP -iTCP:${config.port} -sTCP:LISTEN`
      : err,
  );
  process.exit(1);
});

// The Marco server asks; the caretaker answers over iMessage (docs/INTERFACES.md §5).
socket = connectPhotonSocket(config.marcoServerUrl, (request) => agent.onLabelRequest(request));

let stream: EventStream | null = null;
if (config.photon && photon) {
  stream = startEvents(
    config.photon,
    { load: () => store.eventCursor, save: (seq) => (store.eventCursor = seq) },
    async (event) => {
      const message = await photon.toInbound(event);
      if (message) await agent.handle(message);
    },
  );
}

log.info(
  `Marco x Photon 2.0 up: mode=${config.mode} server=${config.marcoServerUrl} status=http://127.0.0.1:${config.port}/health ` +
    `caretakers=${store.caretakers().length}`,
);
if (!config.elevenLabsKey) log.warn("ELEVENLABS_API_KEY not set: voice memos are kept and sent, but not transcribed into names");
if (config.mode === "sim") log.info("sim mode: POST /dev/inbound to play the caretaker");

let stopping = false;
const shutdown = async () => {
  if (stopping) return;
  stopping = true;
  log.info("shutting down");
  socket?.close();
  stream?.stop();
  await agent.settled();
  http.close();
  process.exit(0);
};
process.once("SIGINT", shutdown);
process.once("SIGTERM", shutdown);
