> ## Documentation Index
> Fetch the complete documentation index at: https://docs.photon.codes/docs/llms.txt
> Use this file to discover all available pages before exploring further.

> ## Agent Instructions
> Use Stable documentation by default. Honor an explicit Beta request or a URL under /docs/beta/. If the requested version conflicts with the installed CLI package or API origin, clarify the target before writing integration code.
> Pages under /docs/beta/ document Beta; other product pages document Stable. Keep the CLI package, commands, API origin, and credentials within the selected version. State the documentation version in your answer.
> For MCP search, always pass version: Stable or version: Beta. Unfiltered search mixes both versions. For filesystem reads, keep Beta queries under /beta/ and exclude /beta/ from Stable queries; discover paths before reading them.
> The public docs base is https://photon.codes/docs. Convert MCP page paths to public URLs under that base, preserving /beta/ when present. Read https://photon.codes/docs/skill.md for version selection and https://photon.codes/docs/llms.txt for the version indexes.

# Get started

> Build your first agent on iMessage, email, or voice, from channel setup to a real conversation.

Give your agent a number or an email address, then have a conversation with it.
Start with one channel: **iMessage** for a quick text exchange, **email** for an
agent on your own domain, or **voice** for an agent that answers the phone.

## Choose your starting point

<CardGroup cols={3}>
  <Card title="iMessage agent" icon="comment" href="/docs/beta/get-started/imessage">
    Text a shared line and get a reply from your code. No domain or public
    server needed.
  </Card>

  <Card title="Email agent" icon="envelope" href="/docs/beta/get-started/email">
    Connect your domain and reply to incoming mail. Requires access to your
    domain's DNS.
  </Card>

  <Card title="Voice agent" icon="phone" href="/docs/beta/get-started/voice">
    Call an ElevenLabs agent over SIP. Requires a published agent and an
    eligible Photon number.
  </Card>
</CardGroup>

## Make your first API request

Start with [Set up your project](/docs/beta/get-started/project): select a project,
create a server-side API key, and install the client for your language. The
messaging guides include complete TypeScript, Python, Rust, and Go programs.

<Steps>
  <Step title="Connect one channel">
    Follow the dashboard instructions and use your own number, domain, or SIP
    destination. Screenshots show sample data, not values to copy.
  </Step>

  <Step title="Run a small, predictable agent">
    For messaging, start with a program that answers only **ping** from your
    test sender. For voice, test your agent's greeting before connecting it.
  </Step>

  <Step title="Verify the conversation">
    Receive the reply on your device, or hear the voice agent and speak back.
    A saved configuration or an accepted API request is not the finish line.
  </Step>
</Steps>

<Note>
  The published API clients support channel setup. Until their messaging methods
  are released, these guides read and send messages through the **HTTP API**.
  Those examples are labeled separately from client calls.
</Note>

## Add more channels

Once your first conversation works, reuse what you built for other channels.
Review each channel's account, plan, and compliance requirements before
connecting it.

| Channel | Prepare before connecting it |
| - | - |
| **Telegram** | A bot you control and its token. Open Telegram in your project and follow its connection flow. |
| **WhatsApp Business** | Access to the business account and phone number you will connect; follow the business onboarding flow. |
| **SMS** | An eligible number and any required sender registration. Buying a number does not complete messaging compliance. |
| **Apple Messages for Business** | A business approved for the channel and its connection details. |

Open your project in the [Beta dashboard](https://app.beta.photon.codes) to see
its available channel connections. Personal WhatsApp availability is separate
from WhatsApp Business; do not assume one connection enables both. For other
voice stacks, follow the [LiveKit, Retell, or Twilio cookbooks](/docs/beta/cookbooks).

## Keep building

<CardGroup cols={2}>
  <Card title="API clients" icon="code" href="/docs/beta/api-client">
    Learn client authentication, retries, pagination, and error handling.
  </Card>

  <Card title="Receive events live" icon="bolt" href="/docs/beta/websocket">
    Move from tutorial polling to Socket.IO subscriptions with replay cursors.
  </Card>

  <Card title="Handling errors" icon="life-ring" href="/docs/beta/problems/handling-errors">
    Understand API errors and build recovery into your application.
  </Card>

  <Card title="API reference" icon="book-open" href="/docs/beta/api-reference">
    Explore endpoints, parameters, and response schemas.
  </Card>
</CardGroup>

Compare [plans and billing](/docs/beta/plans-and-billing) to find the right fit for your
team. For help getting started, email [support@photon.codes](mailto:support@photon.codes)
or join [Discord](https://discord.gg/4mr54mqQN).


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.