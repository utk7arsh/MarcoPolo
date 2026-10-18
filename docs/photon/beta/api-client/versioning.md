> ## Documentation Index
> Fetch the complete documentation index at: https://docs.photon.codes/docs/llms.txt
> Use this file to discover all available pages before exploring further.

> ## Agent Instructions
> Use Stable documentation by default. Honor an explicit Beta request or a URL under /docs/beta/. If the requested version conflicts with the installed CLI package or API origin, clarify the target before writing integration code.
> Pages under /docs/beta/ document Beta; other product pages document Stable. Keep the CLI package, commands, API origin, and credentials within the selected version. State the documentation version in your answer.
> For MCP search, always pass version: Stable or version: Beta. Unfiltered search mixes both versions. For filesystem reads, keep Beta queries under /beta/ and exclude /beta/ from Stable queries; discover paths before reading them.
> The public docs base is https://photon.codes/docs. Convert MCP page paths to public URLs under that base, preserving /beta/ when present. Read https://photon.codes/docs/skill.md for version selection and https://photon.codes/docs/llms.txt for the version indexes.

# Versioning

> How the Photon API clients are versioned and released, and where to find their changelog and references.

The TypeScript, Python, Rust, and Go clients share one version number. Every
release publishes `@photon-ai/api` to npm, `photonhq-api` to PyPI, and
`photonhq-api` to crates.io at the same version, and tags the Go module
`github.com/photon-hq/api/packages/go` as `packages/go/v<version>`, even when one of them has no
changes. A version of one package therefore matches the same version of the
others and was generated from the same API contract.

## Semantic versioning

Releases follow [semantic versioning](https://semver.org). While the version is
below 1.0:

* a release with breaking changes increases the minor version, for example from
  0.2.1 to 0.3.0;
* every other release increases the patch version, for example from 0.2.0 to
  0.2.1.

Breaking changes include renamed or removed methods, types, and fields. Pin
your dependency to one minor version and upgrade on purpose:

| Package manager | Range that stays within one minor version |
| - | - |
| npm | The default `^0.x.y` range already does. |
| pip | Use a compatible-release specifier, such as `photonhq-api~=0.x.y`. |
| Cargo | The default `0.x.y` requirement already does. |
| Go modules | `go get github.com/photon-hq/api/packages/go@v0.x.y` records the exact version in `go.mod`; it changes only when you run `go get` again. |

Because responses are read leniently, an installed client keeps working when the
API adds fields or enum values. All four clients accept new fields: TypeScript
and Python keep them, Go ignores them, and Rust ignores them unless the object
allows extra members. Upgrade to use new endpoints and to get typed access to
new fields.

## Changelog and releases

Every release is listed in
[`CHANGELOG.md`](https://github.com/photon-hq/api/blob/main/CHANGELOG.md)
and tagged `v<version>` in [photon-hq/api](https://github.com/photon-hq/api).
Each release's GitHub page carries the exact files published to npm, PyPI, and
crates.io, with their SHA-256 checksums. Their build provenance attestations are
in the repository's
[attestations](https://github.com/photon-hq/api/attestations); verify a file
with `gh attestation verify FILE --repo photon-hq/api`.

## API references

* **Rust**: the full API reference is on
  [docs.rs/photonhq-api](https://docs.rs/photonhq-api).
* **Go**: the full API reference is on
  [pkg.go.dev/github.com/photon-hq/api/packages/go](https://pkg.go.dev/github.com/photon-hq/api/packages/go).
* **TypeScript**: the package ships its type declarations, and the generated
  methods carry each endpoint's summary and description as documentation
  comments, so your editor shows them.
* **Python**: the package is typed (`py.typed`), and each method's docstring
  carries the endpoint's summary and description.

The [API reference](/docs/beta/api-reference) on this site describes every endpoint, with
its call in TypeScript, Python, Rust, and Go.


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.