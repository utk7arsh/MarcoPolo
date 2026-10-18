# Marco Polo: concept and current scope

Marco helps blind and low-vision users find remembered items with spatial audio and identify touched items with spoken labels.

This file originally held an exploratory proposal. Its alternative hardware, prize planning, event assumptions and proposed features are superseded by the team's approved implementation plan.

- [Hackathon roadmap](docs/HACKATHON-ROADMAP.md): system architecture and constraints.
- [Team interfaces](docs/INTERFACES.md): current messages, geometry and ownership.
- [STATUS.md](STATUS.md): dated implementation and verification records.
- [POC report](poc/REPORT.md): experimental evidence, including rejected approaches.

The demo uses a chest-mounted LiDAR iPhone, headphones, a private server, Photon photo/typed-name labels and an observer dashboard. ElevenLabs supplies spoken output, with Apple speech as the phone fallback.

The server stores session recordings, registration photos and detector templates for debugging and replay. Raw recordings and credentials stay outside Git. Object identity and localization remain imperfect; the prototype does not establish reliable recognition of identical items or unseen movement.
