> ## Documentation Index
> Fetch the complete documentation index at: https://docs.photon.codes/docs/llms.txt
> Use this file to discover all available pages before exploring further.

> ## Agent Instructions
> Use Stable documentation by default. Honor an explicit Beta request or a URL under /docs/beta/. If the requested version conflicts with the installed CLI package or API origin, clarify the target before writing integration code.
> Pages under /docs/beta/ document Beta; other product pages document Stable. Keep the CLI package, commands, API origin, and credentials within the selected version. State the documentation version in your answer.
> For MCP search, always pass version: Stable or version: Beta. Unfiltered search mixes both versions. For filesystem reads, keep Beta queries under /beta/ and exclude /beta/ from Stable queries; discover paths before reading them.
> The public docs base is https://photon.codes/docs. Convert MCP page paths to public URLs under that base, preserving /beta/ when present. Read https://photon.codes/docs/skill.md for version selection and https://photon.codes/docs/llms.txt for the version indexes.

# Cursors, replay, and checkpointing

> Resume from the last event your application successfully handled.

Use `startSeq: 0` to start with new events. A positive `startSeq` resumes after that cursor. If your last processed cursor is `42`, subscribe with `42`; do not add one.

Treat cursors as opaque, non-negative safe integers. They may contain gaps. Store them per project and consumer purpose so independent integrations do not overwrite each other’s progress.

Process deliveries serially. Persist a cursor only after its handler succeeds. If processing fails, stop that stream before handling later deliveries and resume from the last successful checkpoint. Saving the highest received cursor can permanently skip unfinished work.

Socket.IO reconnects the connection, but your application must subscribe again using its saved cursor. Session recovery is disabled. Replay is limited to retained history; this is not an unlimited archive or an exactly-once processing guarantee.


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.