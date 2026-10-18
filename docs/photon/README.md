# Photon 2.0 docs (local copy)

Pulled from https://photon.codes/docs/beta on 2026-10-17: every Beta (2.0) page, one Markdown file per page, under `beta/`. Photon's 174-page generated SDK reference is left out. `INDEX-llms.txt` is Photon's full page index.

The machine-readable specs are too large to copy (the OpenAPI spec is 3.3 MB), so fetch them live:
- REST endpoints: https://api.photon.codes/openapi.json
- Event schemas: https://api.photon.codes/asyncapi.yaml

## Which Photon

The LA Hacks track requires **Photon 2.0** ("must be built on Photon 2.0 and live on at least one Photon channel").

- **The guidelines link is wrong.** They link `photon.co/beta`, a parked domain. The real pages are https://photon.codes/beta and the dashboard at https://app.beta.photon.codes.
- **2.0 is not the Spectrum SDK.** The guidelines' "SDK reference" links Spectrum (`spectrum-ts`), but `spectrum-ts` 12.11.0 has no Photon 2.0 support. Photon's docs call Stable and Beta "documentation channels, not interchangeable API versions" ([skill.md](https://photon.codes/docs/skill.md)), and 2.0 uses its own dashboard, `pho_prj_` project IDs and bearer API keys.
- **So `photon/` is built on 2.0 directly.** It uses the official client `@photon-ai/api` 0.5.0 and the Socket.IO event stream.
- **History.** The earlier Spectrum build, and the Stable docs, are in git history at commit `c3ad80f`.

## Read these first

| Page | Why |
|---|---|
| `beta/get-started/project.md` | Project, API key and permissions |
| `beta/get-started/imessage.md` | Shared-line assignment, and a complete send and receive program |
| `beta/websocket/*.md` | The event stream: connect, subscribe, cursors, reconnects |
| `beta/api-client/*.md` | Credentials, errors, retries, idempotency |
| `beta/plans-and-billing.md` | Shared iMessage assignments per plan |
| `beta/cookbooks/voice/*.md` | Voice agents on an SMS number (the separate Best Voice Agent prize) |
