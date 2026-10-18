> ## Documentation Index
> Fetch the complete documentation index at: https://docs.photon.codes/docs/llms.txt
> Use this file to discover all available pages before exploring further.

> ## Agent Instructions
> Use Stable documentation by default. Honor an explicit Beta request or a URL under /docs/beta/. If the requested version conflicts with the installed CLI package or API origin, clarify the target before writing integration code.
> Pages under /docs/beta/ document Beta; other product pages document Stable. Keep the CLI package, commands, API origin, and credentials within the selected version. State the documentation version in your answer.
> For MCP search, always pass version: Stable or version: Beta. Unfiltered search mixes both versions. For filesystem reads, keep Beta queries under /beta/ and exclude /beta/ from Stable queries; discover paths before reading them.
> The public docs base is https://photon.codes/docs. Convert MCP page paths to public URLs under that base, preserving /beta/ when present. Read https://photon.codes/docs/skill.md for version selection and https://photon.codes/docs/llms.txt for the version indexes.

# Errors

> Handle API errors, transport failures, and unreadable responses in the Photon API clients.

A call can fail in three ways:

* **API error**: the API answered with an error status, such as `404` or `422`.
  The body is a [problem document](/docs/beta/problems/handling-errors) with a `code`, a
  `title`, the `status`, and usually a `detail` and a `requestId`.
* **Transport error**: no response arrived, because of a network failure or a
  timeout.
* **Response error**: a successful response that the client could not read as
  the contract describes, for example a status the contract does not list or a
  body of the wrong shape.

Before an error reaches you, the client retries the requests it can retry. See
[Retries and timeouts](/docs/beta/api-client/retries-and-timeouts).

## Error types

<Tabs>
  <Tab title="TypeScript">
    Every error the client throws extends `PhotonError`, which has `operationId`
    and `requestId` when they are known.

    | Class | Thrown when | Fields |
    | - | - | - |
    | `ApiError` | The API returns an error status. The message is the problem's `detail`, or `Photon API returned HTTP <status>`. | `status`, `headers`, `body` (the parsed JSON, or the text), `rawBody` (the body as text; for a JSON body, the parsed body serialized again), `requestId` |
    | `TransportError` | The request did not complete: a network failure or an attempt that exceeded `timeoutMs`, before or while the body arrived, or a call cancelled through its `signal`. | `cause`, the underlying error or the signal's abort reason |
    | `ResponseValidationError` | A successful response has a status the contract does not list, cannot be decoded, or does not match its schema. | `status`, `issues` (Zod issues), `requestId`, `cause` |

    `error.body` is typed `unknown`: the client does not check error bodies against
    the contract. The contract's error types are exported for reference, per
    operation, such as `GetProjectErrors`.
  </Tab>

  <Tab title="Python">
    Every error the client raises extends `PhotonError`, which has `operation_id`
    and `request_id` when they are known.

    | Class | Raised when | Attributes |
    | - | - | - |
    | `ApiError` | The API returns an error status. The message is the problem's `detail`, or `Photon API returned HTTP <status>`. | `status`, `headers`, `body` (the parsed JSON, or `None`), `raw_body`, `request_id` |
    | `TransportError` | The request failed in `httpx`, for example a connection error or a timeout, on its last attempt. | the `httpx` error is in `__cause__` |
    | `ResponseValidationError` | A successful response has a status the contract does not list, is not empty when it should be, or does not match its model. | `status`, `raw_body`, `request_id` |

    Building an input model with values of the wrong type raises
    `pydantic.ValidationError` before anything is sent.
  </Tab>

  <Tab title="Rust">
    Every operation returns `Result<ResponseValue<T>, Error<E>>`. `E` is the
    operation's error type, usually an enum with one variant per documented error
    status, such as `GetProjectError::Status404`. `Error` is non-exhaustive.

    | Variant | When |
    | - | - |
    | `Api(ResponseValue<E>)` | The API returned an error status the operation documents. The body is decoded into `E`, with the status and headers. |
    | `UnexpectedStatus { status, headers, body }` | The API returned a status the operation does not document. The raw body is kept. |
    | `Transport` | DNS, connection, or TLS failure. |
    | `Timeout` | The request timeout elapsed. |
    | `Decode { status, headers, path, body, truncated }` | A response body did not match its model. |
    | `RequestConstruction` | The request could not be built, for example because no registered credential matches the operation. Nothing was sent. |
    | `Protocol`, `Redirect`, `InterruptedBody` | Malformed HTTP, an exhausted redirect policy, or a connection dropped while reading the body. |

    An error status is `Api` only when the operation documents it. Others arrive as
    `UnexpectedStatus`: `429`, for example, is documented on some operations and
    not on others. Check both variants when you act on a status code.

    `Error::is_transient()` reports whether a failure is a transport error, a
    timeout, an interrupted body, a `429`, or a `5xx`.

    Operation error types implement `Debug` but not `Display` or
    `std::error::Error`, so `?` cannot turn `Error<E>` into
    `Box<dyn std::error::Error>` directly. Match on the error, or convert it first,
    for example with `.map_err(|error| format!("{error:?}"))?`.
  </Tab>

  <Tab title="Go">
    Operations return an `error`; inspect it with `errors.As`.

    | Type | Returned when | Fields |
    | - | - | - |
    | `*APIError` | The API returns an error status. | `StatusCode`, `Problem` (the parsed problem document, `nil` when the body is not one), `RequestID`, `Header`, `Body` (the raw body, capped at 64 KiB). `Code()` returns the problem's code, or `""`. |
    | `*TransportError` | The request did not complete: a network failure, a cancelled context, or a timeout on the `http.Client`, on its last attempt. | `OperationID`, `Err` (the underlying error). |
    | `*ResponseDecodeError` | A successful response could not be read as the contract describes. | `OperationID`, `StatusCode`, `Body` (the full response body), `RequestID`, `Err`. |

    Problem documents are not generated as per-operation types: read
    `APIError.Problem` and match on its `Code`.
  </Tab>
</Tabs>

## Handle an API error

Match on the problem's `code` (or its `type` URI). Both are stable. Do not match
on `title` or `detail`: they are written for people and can change. Every code
is listed in the [problem catalog](/docs/beta/problems/catalog).

This example asks for a project that does not exist, so the API answers `404`
with `PROJECT_NOT_FOUND`:

<CodeGroup>
  ```typescript TypeScript theme={null}
  import { ApiError, Photon } from "@photon-ai/api";

  const apiKey = process.env.PHOTON_API_KEY;
  if (!apiKey) throw new Error("Set PHOTON_API_KEY");

  const photon = new Photon({
    headers: { Authorization: `Bearer ${apiKey}` },
  });

  function problemCode(body: unknown): string | undefined {
    if (typeof body === "object" && body !== null && "code" in body) {
      return typeof body.code === "string" ? body.code : undefined;
    }
    return undefined;
  }

  // A project ID that does not exist.
  const projectId = "pho_prj_00000000000000000000000000";

  try {
    await photon.projects.get({ path: { projectId } });
  } catch (error) {
    if (error instanceof ApiError && problemCode(error.body) === "PROJECT_NOT_FOUND") {
      console.log(`No such project (request ${error.requestId})`);
    } else {
      throw error;
    }
  }
  ```

  ```python Python theme={null}
  import os

  from photon_api import ApiError, Photon
  from photon_api.rpc_generated import GetProjectInput

  api_key = os.environ["PHOTON_API_KEY"]
  # A project ID that does not exist.
  project_id = "pho_prj_00000000000000000000000000"

  with Photon(headers={"Authorization": f"Bearer {api_key}"}) as photon:
      try:
          photon.projects.get(GetProjectInput.model_validate({"path": {"projectId": project_id}}))
      except ApiError as error:
          code = error.body.get("code") if isinstance(error.body, dict) else None
          if code != "PROJECT_NOT_FOUND":
              raise
          print(f"No such project (request {error.request_id})")
  ```

  ```rust Rust theme={null}
  use photon_ai_api::{Credential, Error, GetProjectError, PhotonClientBuilder, SecretString};

  #[tokio::main]
  async fn main() -> Result<(), Box<dyn std::error::Error>> {
      let api_key = std::env::var("PHOTON_API_KEY")?;
      let credential = Credential::Bearer(SecretString::from(api_key));
      let client = PhotonClientBuilder::new()
          .credential("accountServiceKey", credential)
          .build()?;

      // A project ID that does not exist.
      let project_id = "pho_prj_00000000000000000000000000".to_owned();
      match client.get_project(project_id).await {
          Ok(response) => println!("{}", response.into_inner().name),
          Err(Error::Api(response)) => match response.into_inner() {
              GetProjectError::Status404(problem) => {
                  let request_id = problem.request_id.as_deref().unwrap_or("none");
                  println!("No such project (request {request_id})");
              }
              other => return Err(format!("API error: {other:?}").into()),
          },
          Err(other) => return Err(format!("{other:?}").into()),
      }
      Ok(())
  }
  ```

  ```go Go theme={null}
  package main

  import (
  	"context"
  	"errors"
  	"fmt"
  	"log"
  	"os"

  	photonapi "github.com/photon-hq/api/packages/go"
  )

  func main() {
  	apiKey := os.Getenv("PHOTON_API_KEY")
  	if apiKey == "" {
  		log.Fatal("Set PHOTON_API_KEY")
  	}

  	client := photonapi.NewClient(photonapi.WithAPIKey(apiKey))

  	// A project ID that does not exist.
  	projectID := "pho_prj_00000000000000000000000000"

  	project, err := client.Projects.Get(context.Background(), &photonapi.GetProjectParams{
  		ProjectID: projectID,
  	})
  	var apiErr *photonapi.APIError
  	switch {
  	case err == nil:
  		fmt.Println(project.Name)
  	case errors.As(err, &apiErr) && apiErr.Code() == "PROJECT_NOT_FOUND":
  		fmt.Printf("No such project (request %s)\n", apiErr.RequestID)
  	default:
  		log.Fatal(err)
  	}
  }
  ```
</CodeGroup>

## Request IDs

Every API response has an `X-Request-ID` header that identifies that HTTP
attempt, and problem documents usually repeat it as `requestId`. Log it, and
quote it when you contact Photon support about a failed call. When the client
retried a call, the request ID is the one from the last attempt.

* **TypeScript**: `error.requestId` on `ApiError` and `ResponseValidationError`.
* **Python**: `error.request_id` on `ApiError` and `ResponseValidationError`.
* **Rust**: `response.headers().get("x-request-id")` on the `ResponseValue` in
  `Error::Api`, `headers` in `Error::UnexpectedStatus` and `Error::Decode`, or
  the problem's `request_id` field.
* **Go**: `RequestID` on `*APIError`; for successful calls, pass
  `photonapi.WithResponseInfo(&info)` to the call and read `info.RequestID`.

For successful calls, read the request ID from the
[raw response](/docs/beta/api-client/raw-responses).


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.