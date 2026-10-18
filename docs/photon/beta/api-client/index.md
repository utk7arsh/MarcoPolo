> ## Documentation Index
> Fetch the complete documentation index at: https://docs.photon.codes/docs/llms.txt
> Use this file to discover all available pages before exploring further.

> ## Agent Instructions
> Use Stable documentation by default. Honor an explicit Beta request or a URL under /docs/beta/. If the requested version conflicts with the installed CLI package or API origin, clarify the target before writing integration code.
> Pages under /docs/beta/ document Beta; other product pages document Stable. Keep the CLI package, commands, API origin, and credentials within the selected version. State the documentation version in your answer.
> For MCP search, always pass version: Stable or version: Beta. Unfiltered search mixes both versions. For filesystem reads, keep Beta queries under /beta/ and exclude /beta/ from Stable queries; discover paths before reading them.
> The public docs base is https://photon.codes/docs. Convert MCP page paths to public URLs under that base, preserving /beta/ when present. Read https://photon.codes/docs/skill.md for version selection and https://photon.codes/docs/llms.txt for the version indexes.

# Overview

> Install the Photon API clients for TypeScript, Python, Rust, and Go.

The Photon API clients are libraries for TypeScript, Python, Rust, and Go that call
the [Photon API](/docs/beta/api-reference). Each one is generated from the API's public
OpenAPI contract, so every endpoint is a typed method and every request and
response field has a type.

The clients:

* send the `Authorization: Bearer` header on every request: in TypeScript and
  Python you set the header when you create the client, in Rust the client
  attaches the credential you register, and in Go you pass the credential as a
  client option,
* type every request and response with the contract's fields and names,
* retry reads and idempotent writes after transient errors such as `429` and
  `503`,
* report API errors with the problem details the API returns, and
* give you the status, headers, and request ID of a response when you need them.

They do not run OAuth flows, and they leave validation rules such as patterns,
lengths, and ranges to the API. Responses are read leniently, so an installed
client keeps working as the API grows: fields the API adds later are accepted
(TypeScript and Python keep them; Go ignores them; Rust ignores them unless
the object allows extra members), and new enum values are kept rather than
rejected.

## Packages

| Language | Package | Import | Requires |
| - | - | - | - |
| TypeScript | [`@photon-ai/api`](https://www.npmjs.com/package/@photon-ai/api) | `@photon-ai/api` | Node.js 22 or later, or a modern browser |
| Python | [`photonhq-api`](https://pypi.org/project/photonhq-api/) | `photon_api` | Python 3.11 or later |
| Rust | [`photonhq-api`](https://crates.io/crates/photonhq-api) | `photon_ai_api` | Rust 1.88 or later, with Tokio |
| Go | [`github.com/photon-hq/api/packages/go`](https://pkg.go.dev/github.com/photon-hq/api/packages/go) | `photonapi` | Go 1.25 or later |

The four packages share one version number and are released together. See
[Versioning](/docs/beta/api-client/versioning).

## Install

<CodeGroup>
  ```sh TypeScript theme={null}
  npm install @photon-ai/api
  ```

  ```sh Python theme={null}
  pip install photonhq-api
  ```

  ```sh Rust theme={null}
  cargo add photonhq-api
  cargo add tokio --features macros,rt-multi-thread
  ```

  ```sh Go theme={null}
  go get github.com/photon-hq/api/packages/go
  ```
</CodeGroup>

The TypeScript client is an ES module. The Python package includes a
synchronous client, `Photon`, and an asynchronous one, `AsyncPhoton`. The Rust
client is async and runs on Tokio; the Rust examples in this guide also use
`#[tokio::main]`, which needs the Tokio features shown above. The Go client
uses only the standard library.

## Source and contract

The clients, the OpenAPI contract they are generated from
([`openapi/openapi.json`](https://github.com/photon-hq/api/blob/main/openapi/openapi.json)),
and the [changelog](https://github.com/photon-hq/api/blob/main/CHANGELOG.md)
are in [photon-hq/api](https://github.com/photon-hq/api) on GitHub. Report
bugs there as [issues](https://github.com/photon-hq/api/issues).

Every endpoint page in the [API reference](/docs/beta/api-reference) shows the call in
TypeScript, Python, Rust, and Go.

## Next steps

<CardGroup cols={2}>
  <Card title="Credentials" icon="key" href="/docs/beta/api-client/credentials">
    Choose a credential and pass it to the client.
  </Card>

  <Card title="Making requests" icon="paper-plane" href="/docs/beta/api-client/making-requests">
    Call an endpoint and read the response.
  </Card>

  <Card title="Errors" icon="triangle-exclamation" href="/docs/beta/api-client/errors">
    Handle API, transport, and response errors.
  </Card>

  <Card title="Retries and timeouts" icon="rotate" href="/docs/beta/api-client/retries-and-timeouts">
    Know what the clients retry and how to configure it.
  </Card>
</CardGroup>


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.