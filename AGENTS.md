# Marco Polo agent rules

Read `STATUS.md`, `docs/HACKATHON-ROADMAP.md`, `docs/INTERFACES.md`, and
`CLAUDE.md` before making project changes. These instructions apply to this repository.

- Treat the user's approved whole-system diagram, recorded in
  `docs/HACKATHON-ROADMAP.md`, as the primary hackathon roadmap. Optimize for
  the complete working demo: finding remembered items through spatial voice,
  fingertip identification, and caretaker labelling through Photon.
- Check each proposed edit against its effect on capture, geometry, latency,
  spatial guidance, accessibility, network contracts, and the other components.
  Explain material tradeoffs plainly. Ask before changing the agreed architecture
  or adding substantial scope; routine fixes within it should proceed.
- Keep the native iOS app a small accessible control/start panel. Keep the web
  dashboard the observer/setup surface. Preserve their approved shared design.
- Keep perception on the private server, raw sensor geometry consistent, frame
  upload at 1 fps with latest-frame-wins, and guidance on the phone at 60 Hz.
- Use existing Apple frameworks for motion and HRTF. An OS spatial-audio flag
  is informational; verify the actual stereo route, audio rendering and motion
  separately. Never present simulation or a successful build as hardware proof.
- Preserve loopback-only servers, private Tailscale access and fail-closed auth.
  Do not introduce public ingress or weaken authentication to make a demo work.
- Treat `docs/INTERFACES.md` as the canonical wire contract. Coordinate protocol
  changes across producers, consumers, tests and generated contract documentation.
- Prefer the smallest change that completes the demo path; measure latency before
  optimizing. Reuse existing code and avoid duplicate pipelines or speculative SDKs.
- Keep planned, implemented, measured and hardware-verified claims distinct.
  Update `STATUS.md` after work and include relevant tests and remaining gaps.
- Follow `CLAUDE.md` for component ownership, testing and repository hygiene.
  Do not push, publish or message others without the user's authorization.
