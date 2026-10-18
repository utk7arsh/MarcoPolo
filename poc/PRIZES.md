# Integration planning: historical note

Earlier versions of this file explored sponsor challenges and optional services before the architecture was agreed. That proposal is superseded by [the hackathon roadmap](../docs/HACKATHON-ROADMAP.md); it is not a list of implemented features or confirmed award eligibility.

The current integrations have defined roles:

- **Apple frameworks:** camera, LiDAR, tracking, accessibility, command recognition and spatial rendering. See [iOS setup](../ios/README.md).
- **Photon:** caretaker photos and typed labels over iMessage. See [the bridge README](../photon/README.md).
- **ElevenLabs:** exact-text spoken responses from the private server, with Apple speech as the phone fallback. See [the speech plan](../docs/SPEECH-OUTPUT-PLAN.md).
- **Vultr and Tailscale:** private server hosting and authenticated device access. See [deployment setup](../deploy/vultr/README.md).
- **Paper:** shared web/iOS design references. See [the frontend design notes](../frontend/docs/design-v3.md).

No additional cloud service, voice cloning, conversational agent or on-device detection deployment is implied by this inventory. Use [STATUS.md](../STATUS.md) for actual checks and remaining limitations. Competition rules and submission decisions belong to the event's current official materials.
