> ## Documentation Index
> Fetch the complete documentation index at: https://docs.photon.codes/docs/llms.txt
> Use this file to discover all available pages before exploring further.

> ## Agent Instructions
> Use Stable documentation by default. Honor an explicit Beta request or a URL under /docs/beta/. If the requested version conflicts with the installed CLI package or API origin, clarify the target before writing integration code.
> Pages under /docs/beta/ document Beta; other product pages document Stable. Keep the CLI package, commands, API origin, and credentials within the selected version. State the documentation version in your answer.
> For MCP search, always pass version: Stable or version: Beta. Unfiltered search mixes both versions. For filesystem reads, keep Beta queries under /beta/ and exclude /beta/ from Stable queries; discover paths before reading them.
> The public docs base is https://photon.codes/docs. Convert MCP page paths to public URLs under that base, preserving /beta/ when present. Read https://photon.codes/docs/skill.md for version selection and https://photon.codes/docs/llms.txt for the version indexes.

# Retries, timeouts, and idempotency

> What the Photon API clients retry, how long they wait, and how to make writes safe to retry.

The clients retry a request only when sending it again cannot repeat a change:
`GET` requests, and requests that carry an `Idempotency-Key` header. Every other
request is sent once.

## What is retried

| | TypeScript | Python | Rust | Go |
| - | - | - | - | - |
| Requests retried | `GET`, and requests with an `Idempotency-Key` header | `GET`, and requests with an `Idempotency-Key` header | `GET`, and requests with an `Idempotency-Key` header whose body can be resent | `GET`, and requests with an `Idempotency-Key` header whose body can be resent: a one-shot reader body is buffered up to 8 MiB, larger ones are sent once (the client fills an empty key field itself) |
| Statuses retried | `408`, `429`, `502`, `503`, `504` (configurable) | `408`, `429`, `502`, `503`, `504` | `408`, `429`, `502`, `503`, `504` | `408`, `429`, `502`, `503`, `504` |
| Network errors and timeouts, before or while the response body arrives | Retried | Retried | Not retried | Retried until the response arrives; a failure while reading the body is not |
| Attempts | 3, including the first | 3, including the first | 3, including the first | 3, including the first |
| Timeout | 30 seconds for each attempt | 30 seconds for each phase of an attempt: connecting, writing, reading, and waiting for a pooled connection | 30 seconds for each attempt | None of its own: cancel a call through its `context`, or set `Timeout` on the `http.Client` you pass in |

`500` and other errors are not retried. The `Idempotency-Key` header can come
from the call's input or from headers configured on the client. The clients
retry any request that carries one, so send it only to endpoints that declare
an `Idempotency-Key` header; many endpoints that change data do not.

Between attempts, a client waits for the delay in the response's `Retry-After`
header, given in seconds or as an HTTP date. Without one, it waits a random
time between zero and `min(2 s, 250 ms × 2^(attempt - 1))`: up to 250 ms before
the second attempt and up to 500 ms before the third. The Go client's backoff
base and cap are 500 ms and 8 s (`WithRetryDelay`).

If `Retry-After` asks for more than the client's limit, 60 seconds by default,
the client does not wait and does not shorten the delay: it stops retrying and
handles that response as the result, which is an error for an error status. When
attempts run out, the last response is handled the same way. When a network
error or timeout ends the call, TypeScript throws `TransportError`, Python
raises `TransportError`, Rust returns `Error::Transport` or
`Error::Timeout`, and Go returns a `*TransportError`.

## Timeouts

No client limits the whole call: the timeout applies within each attempt, so a
call that is retried can take longer than one timeout.

* **TypeScript**: `timeoutMs` aborts an attempt that has not finished in time.
  To cancel a whole call, pass an `AbortSignal` as `signal` in the call's second
  argument. Cancelling stops the current attempt and any wait, and the call
  throws `TransportError` with the signal's abort reason as its `cause`.
* **Python**: `timeout` is passed to `httpx` for each attempt, which applies it
  separately to connecting, writing, reading, and waiting for a pooled
  connection.
* **Rust**: `timeout` limits each attempt from sending to the end of the
  response body. The default HTTP client also uses it as its connect timeout.
* **Go**: the client sets no timeout of its own. Cancel a whole call with
  `context.WithTimeout`, or limit each attempt with the `Timeout` of an
  `http.Client` passed through `WithHTTPClient`.

## Configure retries and timeouts

| Setting | TypeScript | Python | Rust | Go |
| - | - | - | - | - |
| Timeout | `timeoutMs` per attempt (default `30000`) | `timeout` in seconds per phase of an attempt (default `30.0`) | `.timeout(Duration)` per attempt (default 30 s) | The `context`, or the `http.Client`'s `Timeout` |
| Attempts | `retry.maxAttempts` (default `3`) | `max_attempts` (default `3`) | `.max_attempts(usize)` (default `3`) | `WithMaxRetries(n)` retries after the first attempt (default `2`) |
| Longest `Retry-After` to wait for | `retry.maximumRetryAfterMs` (default `60000`) | `max_retry_after` in seconds (default `60.0`) | `.maximum_retry_after(Duration)` (default 60 s) | `WithMaxRetryAfter(d)` (default 60 s) |
| Retried statuses | `retry.statuses` | Not configurable | Not configurable | Not configurable |
| Backoff | `retry.baseDelayMs` (default `250`), `retry.maximumDelayMs` (default `2000`) | Not configurable | Not configurable | `WithRetryDelay(base, maximum)` (default 500 ms, 8 s) |
| Turn retries off | `retry: false` | `max_attempts=1` | `.max_attempts(1)` | `WithMaxRetries(0)` |

In TypeScript, Python, and Rust, attempts are limited to between 1 and 3; a
larger value means 3. Go's `WithMaxRetries` counts retries after the first
attempt and has no upper cap.

<CodeGroup>
  ```typescript TypeScript theme={null}
  import { Photon } from "@photon-ai/api";

  const apiKey = process.env.PHOTON_API_KEY;
  const organizationId = process.env.PHOTON_ORGANIZATION_ID;
  if (!apiKey || !organizationId) {
    throw new Error("Set PHOTON_API_KEY and PHOTON_ORGANIZATION_ID");
  }

  const photon = new Photon({
    headers: { Authorization: `Bearer ${apiKey}` },
    timeoutMs: 10_000,
    retry: { maxAttempts: 2, maximumRetryAfterMs: 5_000 },
  });

  const controller = new AbortController();
  const result = await photon.organizations.projects.count(
    { path: { organizationId } },
    { signal: controller.signal },
  );
  console.log(result.count);
  ```

  ```python Python theme={null}
  import os

  from photon_api import Photon
  from photon_api.rpc_generated import CountProjectsInput

  api_key = os.environ["PHOTON_API_KEY"]
  organization_id = os.environ["PHOTON_ORGANIZATION_ID"]

  with Photon(
      headers={"Authorization": f"Bearer {api_key}"},
      timeout=10.0,
      max_attempts=2,
      max_retry_after=5.0,
  ) as photon:
      result = photon.organizations.projects.count(
          CountProjectsInput.model_validate({"path": {"organizationId": organization_id}})
      )
      print(result.count)
  ```

  ```rust Rust theme={null}
  use std::time::Duration;

  use photon_ai_api::{Credential, PhotonClientBuilder, SecretString};

  #[tokio::main]
  async fn main() -> Result<(), Box<dyn std::error::Error>> {
      let api_key = std::env::var("PHOTON_API_KEY")?;
      let organization_id = std::env::var("PHOTON_ORGANIZATION_ID")?;

      let credential = Credential::Bearer(SecretString::from(api_key));
      let client = PhotonClientBuilder::new()
          .credential("accountServiceKey", credential)
          .timeout(Duration::from_secs(10))
          .max_attempts(2)
          .maximum_retry_after(Duration::from_secs(5))
          .build()?;

      let result = client
          .count_projects(organization_id, None)
          .await
          .map_err(|error| format!("{error:?}"))?;
      println!("{}", result.inner().count);
      Ok(())
  }
  ```

  ```go Go theme={null}
  package main

  import (
  	"context"
  	"fmt"
  	"log"
  	"os"
  	"time"

  	photonapi "github.com/photon-hq/api/packages/go"
  )

  func main() {
  	apiKey := os.Getenv("PHOTON_API_KEY")
  	organizationID := os.Getenv("PHOTON_ORGANIZATION_ID")
  	if apiKey == "" || organizationID == "" {
  		log.Fatal("Set PHOTON_API_KEY and PHOTON_ORGANIZATION_ID")
  	}

  	client := photonapi.NewClient(
  		photonapi.WithAPIKey(apiKey),
  		photonapi.WithMaxRetries(1),
  		photonapi.WithMaxRetryAfter(5*time.Second),
  	)

  	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
  	defer cancel()
  	result, err := client.Organizations.Projects.Count(ctx, &photonapi.CountProjectsParams{
  		OrganizationID: organizationID,
  	})
  	if err != nil {
  		log.Fatal(err)
  	}
  	fmt.Println(result.Count)
  }
  ```
</CodeGroup>

## Idempotency keys

Endpoints that create or change something often take an `Idempotency-Key`
header, which identifies one logical change across retries. Most of them
require it, and the API answers `400` with `IDEMPOTENCY_KEY_REQUIRED` when it is
missing. The key is 1 to 255 visible ASCII characters, without spaces. When the API answers
with a stored result for a key it has already seen, the response has
`Idempotent-Replayed: true`.

The TypeScript, Python, and Rust clients do not create keys. Pass one in the
call's input:

* **TypeScript**: `headers: { idempotencyKey }`, or `headers: { "idempotency-key": key }`
  where the contract spells the header that way, as for `uploadAttachment`.
* **Python**: `"headers": { "Idempotency-Key": key }` in the input model, with the
  header name spelled as the contract spells it.
* **Rust**: a positional argument when the endpoint requires the key, or the
  `idempotency_key` setter of the operation's `Params` when it is optional.
* **Go**: the `IdempotencyKey` field of the operation's `Params`. Left empty,
  the client generates a key and reuses it across its own retries; set it
  yourself when you also retry the change outside the client.

Use a new key for each change you make, such as a random UUID, and keep it
while you retry that change yourself, for example after a timeout or a restart.
A request that carries a key is retried by the client, with the same key on
every attempt. [Making requests](/docs/beta/api-client/making-requests#send-a-body-and-headers)
shows a complete call.

Do not set `Idempotency-Key` in the client's `headers` option: every call would
share one key.


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.