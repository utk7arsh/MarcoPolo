> ## Documentation Index
> Fetch the complete documentation index at: https://docs.photon.codes/docs/llms.txt
> Use this file to discover all available pages before exploring further.

> ## Agent Instructions
> Use Stable documentation by default. Honor an explicit Beta request or a URL under /docs/beta/. If the requested version conflicts with the installed CLI package or API origin, clarify the target before writing integration code.
> Pages under /docs/beta/ document Beta; other product pages document Stable. Keep the CLI package, commands, API origin, and credentials within the selected version. State the documentation version in your answer.
> For MCP search, always pass version: Stable or version: Beta. Unfiltered search mixes both versions. For filesystem reads, keep Beta queries under /beta/ and exclude /beta/ from Stable queries; discover paths before reading them.
> The public docs base is https://photon.codes/docs. Convert MCP page paths to public URLs under that base, preserving /beta/ when present. Read https://photon.codes/docs/skill.md for version selection and https://photon.codes/docs/llms.txt for the version indexes.

# Cookbooks

> Step-by-step guides for building with Photon.

Follow these guides to connect Photon to the services you use.

## Voice

Connect a Photon number to your voice application for incoming and outgoing calls.

<CardGroup cols={2}>
  <Card title="Retell" icon="phone" href="/docs/beta/cookbooks/voice/retell">
    Set up Photon and Retell with SIP trunking.
  </Card>

  <Card title="ElevenLabs" icon="phone" href="/docs/beta/cookbooks/voice/elevenlabs">
    Set up Photon and ElevenLabs with SIP trunking.
  </Card>

  <Card title="LiveKit" icon="phone" href="/docs/beta/cookbooks/voice/livekit">
    Connect Photon calls to LiveKit rooms with SIP trunks and optional agents.
  </Card>

  <Card title="Twilio" icon="phone" href="/docs/beta/cookbooks/voice/twilio">
    Connect Photon to Twilio for call forwarding and outgoing SIP calls.
  </Card>
</CardGroup>


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.