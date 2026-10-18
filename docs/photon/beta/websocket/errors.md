> ## Documentation Index
> Fetch the complete documentation index at: https://docs.photon.codes/docs/llms.txt
> Use this file to discover all available pages before exploring further.

> ## Agent Instructions
> Use Stable documentation by default. Honor an explicit Beta request or a URL under /docs/beta/. If the requested version conflicts with the installed CLI package or API origin, clarify the target before writing integration code.
> Pages under /docs/beta/ document Beta; other product pages document Stable. Keep the CLI package, commands, API origin, and credentials within the selected version. State the documentation version in your answer.
> For MCP search, always pass version: Stable or version: Beta. Unfiltered search mixes both versions. For filesystem reads, keep Beta queries under /beta/ and exclude /beta/ from Stable queries; discover paths before reading them.
> The public docs base is https://photon.codes/docs. Convert MCP page paths to public URLs under that base, preserving /beta/ when present. Read https://photon.codes/docs/skill.md for version selection and https://photon.codes/docs/llms.txt for the version indexes.

# Errors and reconnection

> Handle typed errors and let Socket.IO manage connection recovery.

Listen for `delivery_error`. Command acknowledgements also return typed failures. Errors include `code`, `message`, `fatal`, and `retryable`. A fatal error is followed by disconnection; the error itself is best-effort if the transport has already failed.

Socket.IO owns heartbeat detection and reconnect backoff. After any automatic reconnect, subscribe with your last successfully processed cursor. A terminal application violation causes an explicit server disconnect: fix its cause before calling `connect()` again. Authentication failures before connection appear as `connect_error`; correct the credential or project rather than retrying indefinitely.

## Fatal errors

| Code | Retryable | Action |
| - | - | - |
| `protocol_violation` | false | Fix the invalid command sequence or excessive input. |
| `subscribe_timeout` | true | Subscribe promptly after connecting. |
| `frame_too_large` | false | Reduce the command size. |
| `slow_consumer` | true | Drain deliveries faster and resume from the processed cursor. |
| `capacity` | true | Allow automatic reconnection with backoff. |
| `server_draining` | true | Reconnect and subscribe with the processed cursor. |
| `upstream_unavailable` | true | Reconnect and resume. |
| `internal` | true | Reconnect; retain the connection ID for diagnostics. |

## Non-fatal errors

| Code | Action |
| - | - |
| `reply_unknown_event` | The expectation expired, was consumed, or belongs to another connection. |
| `reply_invalid` | Correct the reply fields or encoding. |
| `reply_too_large` | Reduce the decoded reply body. |
| `reply_publish_failed` | Forwarding failed; the outcome is not a downstream success. |
| `reply_capacity` | This delivery cannot accept a reply; continue handling events. |
| `reply_forbidden` | Use a credential with project:write to reply. |
| `subscribe_repeated` | Keep using the existing subscription. |
| `frame_invalid` | Correct the event name, payload, or acknowledgement callback. |


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.