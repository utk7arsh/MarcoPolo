> ## Documentation Index
> Fetch the complete documentation index at: https://docs.photon.codes/docs/llms.txt
> Use this file to discover all available pages before exploring further.

> ## Agent Instructions
> Use Stable documentation by default. Honor an explicit Beta request or a URL under /docs/beta/. If the requested version conflicts with the installed CLI package or API origin, clarify the target before writing integration code.
> Pages under /docs/beta/ document Beta; other product pages document Stable. Keep the CLI package, commands, API origin, and credentials within the selected version. State the documentation version in your answer.
> For MCP search, always pass version: Stable or version: Beta. Unfiltered search mixes both versions. For filesystem reads, keep Beta queries under /beta/ and exclude /beta/ from Stable queries; discover paths before reading them.
> The public docs base is https://photon.codes/docs. Convert MCP page paths to public URLs under that base, preserving /beta/ when present. Read https://photon.codes/docs/skill.md for version selection and https://photon.codes/docs/llms.txt for the version indexes.

# Handling errors

> How Photon reports errors, and what every field means.

Every Photon API error is an [RFC 9457](https://www.rfc-editor.org/rfc/rfc9457)
problem document, served as `application/problem+json`. One shape covers every
failure, so you write the handling once.

```json theme={null}
{
  "type": "https://photon.codes/docs/problems/validation-failed",
  "code": "VALIDATION_FAILED",
  "title": "Request Validation Failed",
  "status": 422,
  "detail": "expiresAt must be in the future.",
  "requestId": "01JAV6R2K9XQ0YB3M7T4E8N5PD"
}
```

## Fields

| Field | Always present | What it is |
| - | - | - |
| `type` | Yes | A URI identifying the problem. Stable, and the page you are reading this on. |
| `code` | Yes | A `SCREAMING_SNAKE_CASE` identifier for the same problem. Stable. |
| `title` | Yes | A short human-readable summary. Do not match on it. |
| `status` | Yes | The HTTP status code, repeated in the body. |
| `detail` | No | What went wrong on this specific request. Do not match on it. |
| `instance` | No | The request path that produced the problem. |
| `remediation` | No | An `action` describing how to fix it, and sometimes a `documentation` URL. |
| `requestId` | No | Quote this when you contact support. |

A problem may also carry extension fields specific to it — `validation-failed`
adds `issues`, listing every field that failed. The generated catalog lists the extensions declared by the deployed API and shared error registry.

## Handle problems by type or code

`type` and `code` are wire contracts: once published, neither changes without a
breaking change. Match on either one.

```ts theme={null}
const res = await fetch(url, { headers })
if (!res.ok) {
  const problem = await res.json()
  if (problem.code === 'RATE_LIMITED') {
    // Retry-After carries the delay, as a header rather than a body field.
    const retryAfter = Number(res.headers.get('Retry-After') ?? 1)
    await new Promise(r => setTimeout(r, retryAfter * 1000))
  }
}
```

Never branch on `title` or `detail`. Both are written for people, and both
change without notice.

## Look up a type URI

Every problem the API publishes is listed in the [catalog](/docs/beta/problems/catalog),
with its code, status, and any extension fields it carries.

Each slug there is anchored, and a `type` URI redirects onto it. Open
`https://photon.codes/docs/problems/rate-limited` and you land on that row with
it highlighted, whatever filter was set.


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.