import { MarcoAgent, Spaces } from "./agent.js";
import { loadConfig } from "./config.js";
import { EventBus } from "./events.js";
import { startHttp } from "./http.js";
import { log } from "./log.js";
import { MarcoServer } from "./marco-server.js";
import { Media } from "./media.js";
import { simMessaging, startSpectrum, type Messaging } from "./messaging.js";
import { SimPlatform } from "./sim.js";
import { Store } from "./store.js";
import { elevenLabsTranscriber, noTranscriber } from "./transcribe.js";

try {
  process.loadEnvFile();
} catch {
  // no .env file; rely on the environment
}

const config = loadConfig();
const store = new Store(config.dataDir);
const media = new Media(config.dataDir, config.publicBaseUrl);
const events = new EventBus();
const sim = config.mode === "sim" ? new SimPlatform() : null;

let messaging: Messaging | undefined;
const spaces = new Spaces(async (platform, spaceId) => messaging?.lookup(platform, spaceId));
const agent = new MarcoAgent({
  config,
  store,
  media,
  events,
  spaces,
  transcribe: config.elevenLabsKey ? elevenLabsTranscriber(config.elevenLabsKey, config.sttModel) : noTranscriber,
  server: new MarcoServer(config.marcoServerUrl, media),
});

// Bind the port before connecting to Photon: a second copy must exit here, not become a second consumer of the same line.
const http = startHttp({ config, agent, store, media, events, sim });
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
messaging = sim ? simMessaging(sim) : await startSpectrum(config, (space, message) => agent.handle(space, message));

log.info(`Marco x Photon up: mode=${config.mode} http=:${config.port} caretakers=${store.caretakers().length} items=${store.items().length}`);
if (!config.elevenLabsKey) log.warn("ELEVENLABS_API_KEY not set: voice memos are saved and played, but not transcribed into names");
if (config.mode === "sim") log.info("sim mode: POST /dev/inbound to play the caretaker");

let stopping = false;
const shutdown = async () => {
  if (stopping) return;
  stopping = true;
  log.info("shutting down");
  await messaging?.stop();
  await agent.settled();
  http.close();
  process.exit(0);
};
process.once("SIGINT", shutdown);
process.once("SIGTERM", shutdown);
