> ## Documentation Index
> Fetch the complete documentation index at: https://docs.photon.codes/docs/llms.txt
> Use this file to discover all available pages before exploring further.

> ## Agent Instructions
> Use Stable documentation by default. Honor an explicit Beta request or a URL under /docs/beta/. If the requested version conflicts with the installed CLI package or API origin, clarify the target before writing integration code.
> Pages under /docs/beta/ document Beta; other product pages document Stable. Keep the CLI package, commands, API origin, and credentials within the selected version. State the documentation version in your answer.
> For MCP search, always pass version: Stable or version: Beta. Unfiltered search mixes both versions. For filesystem reads, keep Beta queries under /beta/ and exclude /beta/ from Stable queries; discover paths before reading them.
> The public docs base is https://photon.codes/docs. Convert MCP page paths to public URLs under that base, preserving /beta/ when present. Read https://photon.codes/docs/skill.md for version selection and https://photon.codes/docs/llms.txt for the version indexes.

# API reference

> Photon API reference.

The Photon API is a REST API over JSON. Use it to manage projects, provision and
operate messaging and voice lines, handle 10DLC and call registry compliance,
configure webhooks, and administer accounts, members, and billing.

## Base URL

```
https://api.photon.codes
```

Every endpoint is versioned under `/v1`.

## Authentication

Send your credential as a bearer token on every request:

```
Authorization: Bearer <credential>
```

Photon accepts three kinds of credential and tells them apart by their prefix:

| Credential | Looks like | Use it for |
| - | - | - |
| Account service key | `pho_ask_...` | Any endpoint your account can reach. |
| Project API key | `pho_sk_...` | One project, under `/v1/projects/{projectId}`. |
| Access token | A JWT | Dashboard sessions and OAuth grants. |

A project API key only works under `/v1/projects/{projectId}`, for the project it
was issued for. Every other endpoint needs an account credential — all of
`/v1/account`, the `/v1/projects` collection, and invitations.

Pick the narrowest credential that reaches what you are testing. A project API
key is enough for most endpoints, and limits the damage if you leak it. Reach for
an account service key only when you need `/v1/account` or the project
collection.

Create an account service key through `POST /v1/account/service-keys`, using
an account access token or an existing account service key. Give the key a
name and an explicit expiry. Save the returned credential when you create it;
you cannot retrieve it again. To replace a lost key, revoke it and create another.

<Warning>
  The playground sends real requests, so anything you paste is a live credential.
  Use a dedicated key with only the permissions you need, and revoke it when you
  are done.
</Warning>

A handful of endpoints under `/v1/auth` are public and ignore the header.

## Timestamps

Timestamps are RFC 3339 date-times in UTC with an upper-case `T` and `Z`, for
example `2026-01-01T00:00:00Z`. Responses always use this form; send timestamps
the same way.

## Errors

Every error is an [RFC 9457](https://www.rfc-editor.org/rfc/rfc9457) problem
document served as `application/problem+json`, carrying a stable `type` URI and
`code` you can match on:

```json theme={null}
{
  "type": "https://photon.codes/docs/problems/validation-failed",
  "code": "VALIDATION_FAILED",
  "title": "Request Validation Failed",
  "status": 422
}
```

Each `type` URI resolves to the page documenting that problem. See
[Problems](/docs/beta/problems/catalog) for the envelope and the full catalogue.

## Browse the endpoints

The **Endpoints** group in the sidebar lists every operation, grouped by the area
it belongs to. Each page documents the parameters, request body, and responses,
and lets you send a request from the interactive playground.

You can also read the schema directly at
[`/openapi.json`](https://api.photon.codes/openapi.json).

The **WebSocket** group below it covers
[event delivery over WebSocket](/docs/beta/websocket): how to connect, start a session,
receive events, and read the [frame reference](/docs/beta/websocket/frames).


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.