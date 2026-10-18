# Photon 2.0 vendor reference archive

These vendor documentation snapshots were copied from [Photon's Beta documentation](https://photon.codes/docs/beta/photon) on October 17, 2026. They are reference material, not Marco's implementation or a promise that Marco uses every documented feature. Original vendor attribution is retained.

Start with [the Marco bridge README](../../photon/README.md) for the implemented photo/typed-name flows and required configuration. Use the [canonical team interfaces](../INTERFACES.md) for Marco's server contract. ElevenLabs TTS belongs to the Marco server, not this bridge; vendor voice-agent cookbook examples are outside the demo's scope.

The archived `beta/` pages retain vendor site-root links and documentation components that GitHub may not render. Read them on the [Photon documentation site](https://photon.codes/docs/beta/photon) when necessary. `INDEX-llms.txt` is the vendor's page index; SDK and API details may have changed since the snapshot.

## Relevant archived sections

- `beta/get-started/project.md`: project, API key and permissions.
- `beta/get-started/imessage.md`: iMessage setup and send/receive examples.
- `beta/websocket/`: event streams, cursors and reconnects.
- `beta/api-client/`: credentials, retries and idempotency.

Machine-readable vendor specifications are available from [OpenAPI](https://api.photon.codes/openapi.json) and [event schemas](https://api.photon.codes/asyncapi.yaml); they are not bundled here. Consult current vendor documentation before changing dependencies or API behavior.
