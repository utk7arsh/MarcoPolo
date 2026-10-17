#### Providers

Source: https://photon.codes/docs/spectrum-ts/providers.md
Documentation version: Stable

SDK providers plug into Spectrum's type system and runtime. Each SDK provider
exports a callable. Call `provider.config(...)` to register it, and call
`provider(app)` or `provider(space)` to
[narrow](https://photon.codes/docs/spectrum-ts/platform-narrowing) into its platform-specific instance.

##### Platform and provider guides

Most platforms connect through a provider package registered with `config()`.
Voice calls currently connect directly over SIP; the Voice guide lives here
because it is a platform integration, while SDK call control is still on the
roadmap.

- [**iMessage**](https://photon.codes/docs/spectrum-ts/providers/imessage) — Use the batteries-included cloud provider, or explicitly install the separate macOS local provider.
- [**Terminal**](https://photon.codes/docs/spectrum-ts/providers/terminal) — Run a local chat interface for development, testing, and CLI-style agents.
- [**WhatsApp Business**](https://photon.codes/docs/spectrum-ts/providers/whatsapp-business) — Use the official WhatsApp Business Cloud API for 1:1 customer conversations.
- [**Voice**](https://photon.codes/docs/spectrum-ts/providers/voice) — Place and receive calls over SIP using a Spectrum iMessage line.
- [**Telegram**](https://photon.codes/docs/spectrum-ts/providers/telegram) — Use the Telegram Bot API with Fusor webhooks, media, reactions, replies, typing, and edits.

##### Combining providers

Call each provider's `config()` method and pass the results to `providers`:

**Aggregate import**

```ts
import { Spectrum } from "spectrum-ts";
import { imessage, terminal, whatsappBusiness } from "spectrum-ts/providers";

const app = await Spectrum({
  projectId: "...",
  projectSecret: "...",
  providers: [
    imessage.config(),
    whatsappBusiness.config({
      accessToken: process.env.WA_TOKEN!,
      phoneNumberId: process.env.WA_NUMBER_ID!,
      appSecret: process.env.WA_SECRET!,
    }),
    terminal.config(),
  ],
});
```

**Individual imports**

```ts
import { Spectrum } from "spectrum-ts";
import { imessage } from "spectrum-ts/providers/imessage";
import { terminal } from "spectrum-ts/providers/terminal";
import { whatsappBusiness } from "spectrum-ts/providers/whatsapp-business";

const app = await Spectrum({
  projectId: "...",
  projectSecret: "...",
  providers: [
    imessage.config(),
    whatsappBusiness.config({
      accessToken: process.env.WA_TOKEN!,
      phoneNumberId: process.env.WA_NUMBER_ID!,
      appSecret: process.env.WA_SECRET!,
    }),
    terminal.config(),
  ],
});
```

`app.messages` merges messages from every provider. The `message.platform` field tells you which provider delivered each message.

  `@spectrum-ts/imessage-local` is not part of the aggregate import. Install it
  explicitly and import `localIMessage` from its scoped package. Cloud iMessage
  uses the `"imessage"` platform ID; local iMessage uses `"local_imessage"`, so
  a macOS application can register both when it needs both transports.

##### Writing your own

If none of the built-ins fit, implement a provider with `definePlatform`. See [Building a custom platform](https://photon.codes/docs/spectrum-ts/custom-platforms).


#### Voice

