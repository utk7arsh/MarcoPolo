#### Introduction

Source: https://photon.codes/docs/spectrum-ts/introduction.md
Documentation version: Stable

Welcome to the Spectrum documentation.

If you need support with your integration, email [ryan@photon.codes](mailto:ryan@photon.codes).

Here are some helpful links:

- [Quickstart](https://photon.codes/docs/spectrum-ts/getting-started) - Send your first Spectrum message.
- [iMessage provider](https://photon.codes/docs/spectrum-ts/providers/imessage) - Build with Photon's managed iMessage infrastructure.
- [API reference](https://photon.codes/docs/api-reference/introduction) - Manage Spectrum through the API.
- [Photon CLI](https://photon.codes/docs/cli/spectrum) - Manage Spectrum from your terminal.
- [Spectrum skills](https://www.skills.sh/photon-hq/skills/spectrum) - Add Spectrum knowledge to your AI coding tools.

##### What is Spectrum?

Spectrum lets you build an agent once and connect it to the places your users already are.

A user might message you in iMessage today, WhatsApp tomorrow, and your app next week. Without Spectrum, each interface becomes a separate integration with its own authentication, events, message formats, edge cases, and tools.

With Spectrum, you run one agent server and add providers for the interfaces you want to support. Each provider connects a native interface to the same Spectrum API, so your agent can feel consistent everywhere.

Today, Spectrum supports iMessage, WhatsApp Business, Telegram, terminal
development, and SIP voice calls on iMessage lines. The same model is built for
more interfaces over time: Discord, websites, apps,
voice-only lines, meetings, and hardware like HomePod.

##### Supported interfaces today

Spectrum currently supports these interfaces and development surfaces:

- [**iMessage**](https://photon.codes/docs/spectrum-ts/providers/imessage) — Run production iMessage agents through managed iMessage lines.
- [**WhatsApp Business**](https://photon.codes/docs/spectrum-ts/providers/whatsapp-business) — Connect to the official WhatsApp Business Cloud API.
- [**Telegram**](https://photon.codes/docs/spectrum-ts/providers/telegram) — Build bots on the Telegram Bot API with inbound webhooks through Fusor.
- [**Terminal**](https://photon.codes/docs/spectrum-ts/providers/terminal) — Build, test, and demo agents from your local terminal.
- [**Voice calls**](https://photon.codes/docs/spectrum-ts/providers/voice) — Place and receive calls over SIP using Spectrum iMessage lines.

You can also build custom providers with `definePlatform`. Use custom providers to bring websites, apps, Discord, internal tools, or new device interfaces into Spectrum.

- [**View all providers**](https://photon.codes/docs/spectrum-ts/providers) — See the built-in providers and learn how to combine them.

##### The agent server model

Spectrum is designed around a simple idea: your agent should run once.

Your Spectrum server owns the product behavior: routing, tools, memory, handoff, safety, analytics, and anything else your agent needs. Providers own the interface work: connecting to each platform, receiving events, sending messages, and exposing native features when they exist.

That keeps your code small. You add providers, but the agent loop stays the same:

```ts
import { Spectrum } from "spectrum-ts";
import { imessage, terminal } from "spectrum-ts/providers";

const app = await Spectrum({
  projectId: process.env.PROJECT_ID!,
  projectSecret: process.env.PROJECT_SECRET!,
  providers: [
    imessage.config(),
    terminal.config(),
  ],
});

for await (const [space] of app.messages) {
  await space.send("How can I help?");
}
```

Every provider feeds the same message stream. Your agent can send, react, reply, and use platform-specific features only when it needs them.

##### Built for iMessage

iMessage is where Spectrum is most mature.

Spectrum gives you production iMessage infrastructure with the richest
iMessage feature set we offer today. The batteries-included cloud provider
connects a Node.js or Bun service to managed iMessage lines and supports DMs,
groups, typing indicators, reactions, threaded replies, effects, backgrounds,
per-line routing, dedicated-line auto-scale, and automatic token renewal. For
tools that run directly on your own Mac, install the separate
`@spectrum-ts/imessage-local` provider to access that Mac's Messages database
without bringing its native SQLite dependency into deployed applications.

That matters because iMessage is not a generic SMS fallback. Users expect native behavior, reliable delivery, and conversations that feel like they belong on Apple devices.

- [**Explore the iMessage provider**](https://photon.codes/docs/spectrum-ts/providers/imessage) — Learn how Spectrum connects your agent to managed iMessage lines.

##### Manage Spectrum your way

You do not have to manage Spectrum only from the dashboard. Use the dashboard for setup, the API for automation, and the Photon CLI for terminal workflows and scripts.

- [**Dashboard**](https://app.photon.codes) — Configure projects, users, lines, platforms, and profile settings from the browser.
- [**API reference**](https://photon.codes/docs/api-reference/introduction) — Automate Spectrum management from your own systems and test live requests.
- [**CLI**](https://photon.codes/docs/cli/spectrum) — Script profile updates, users, lines, platform toggles, and avatars from a terminal.

##### Where to go next

- [**Get started**](https://photon.codes/docs/spectrum-ts/getting-started) — Install `spectrum-ts` and send your first message.
- [**Webhooks**](https://photon.codes/docs/spectrum-ts/webhooks) — Receive messages via HTTP with native and Fusor webhook support, plus Hono, Express, and Elysia adapters.
- [**Voice calls**](https://photon.codes/docs/spectrum-ts/providers/voice) — Place and receive calls with SIP over TLS or TCP.
- [**Build a custom platform**](https://photon.codes/docs/spectrum-ts/custom-platforms) — Add a new interface with Spectrum's provider model.


