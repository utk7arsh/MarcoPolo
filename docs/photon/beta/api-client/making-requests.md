> ## Documentation Index
> Fetch the complete documentation index at: https://docs.photon.codes/docs/llms.txt
> Use this file to discover all available pages before exploring further.

> ## Agent Instructions
> Use Stable documentation by default. Honor an explicit Beta request or a URL under /docs/beta/. If the requested version conflicts with the installed CLI package or API origin, clarify the target before writing integration code.
> Pages under /docs/beta/ document Beta; other product pages document Stable. Keep the CLI package, commands, API origin, and credentials within the selected version. State the documentation version in your answer.
> For MCP search, always pass version: Stable or version: Beta. Unfiltered search mixes both versions. For filesystem reads, keep Beta queries under /beta/ and exclude /beta/ from Stable queries; discover paths before reading them.
> The public docs base is https://photon.codes/docs. Convert MCP page paths to public URLs under that base, preserving /beta/ when present. Read https://photon.codes/docs/skill.md for version selection and https://photon.codes/docs/llms.txt for the version indexes.

# Making requests

> Call Photon API endpoints from TypeScript, Python, Rust, and Go, and read the responses.

Create one client and reuse it for every call. Each endpoint in the
[API reference](/docs/beta/api-reference) is a method on the client, and each endpoint
page shows its call in all four languages.

## Your first request

This program lists the projects in an organization. Set `PHOTON_API_KEY` to an
account service key or a service identity credential, and
`PHOTON_ORGANIZATION_ID` to the ID of an organization it can access.

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
  });

  const page = await photon.organizations.projects.list({
    path: { organizationId },
    query: { pageSize: 10 },
  });
  for (const project of page.projects) {
    console.log(project.projectId, project.name);
  }
  ```

  ```python Python theme={null}
  import os

  from photon_api import Photon
  from photon_api.rpc_generated import ListProjectsInput

  api_key = os.environ["PHOTON_API_KEY"]
  organization_id = os.environ["PHOTON_ORGANIZATION_ID"]

  with Photon(headers={"Authorization": f"Bearer {api_key}"}) as photon:
      page = photon.organizations.projects.list(
          ListProjectsInput.model_validate(
              {
                  "path": {"organizationId": organization_id},
                  "query": {"pageSize": 10},
              }
          )
      )
      for project in page.projects:
          print(project.projectId, project.name)
  ```

  ```rust Rust theme={null}
  use photon_ai_api::{Credential, ListProjectsParams, PhotonClientBuilder, SecretString};

  #[tokio::main]
  async fn main() -> Result<(), Box<dyn std::error::Error>> {
      let api_key = std::env::var("PHOTON_API_KEY")?;
      let organization_id = std::env::var("PHOTON_ORGANIZATION_ID")?;

      let credential = Credential::Bearer(SecretString::from(api_key));
      let client = PhotonClientBuilder::new()
          .credential("accountServiceKey", credential)
          .build()?;

      let page = client
          .list_projects(
              organization_id,
              Some(ListProjectsParams::default().page_size(10)),
          )
          .await
          .map_err(|error| format!("{error:?}"))?
          .into_inner();
      for project in page.projects {
          println!("{} {}", project.project_id, project.name);
      }
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

  	photonapi "github.com/photon-hq/api/packages/go"
  )

  func main() {
  	apiKey := os.Getenv("PHOTON_API_KEY")
  	organizationID := os.Getenv("PHOTON_ORGANIZATION_ID")
  	if apiKey == "" || organizationID == "" {
  		log.Fatal("Set PHOTON_API_KEY and PHOTON_ORGANIZATION_ID")
  	}

  	client := photonapi.NewClient(photonapi.WithAPIKey(apiKey))

  	page, err := client.Organizations.Projects.List(context.Background(), &photonapi.ListProjectsParams{
  		OrganizationID: organizationID,
  		PageSize:       photonapi.Ptr(int64(10)),
  	})
  	if err != nil {
  		log.Fatal(err)
  	}
  	for _, project := range page.Projects {
  		fmt.Println(project.ProjectID, project.Name)
  	}
  }
  ```
</CodeGroup>

If you use a service identity credential in Rust, register it as
`"serviceIdentityBearer"` instead. See [Credentials](/docs/beta/api-client/credentials).

## How calls are shaped

<Tabs>
  <Tab title="TypeScript">
    Methods are grouped into namespaces that follow the API paths, such as
    `photon.organizations.projects.list`. Each method takes one object with the
    members the endpoint declares:

    * `path`: path parameters, such as `{ organizationId }`.
    * `query`: query parameters, such as `{ pageSize: 10 }`.
    * `headers`: header parameters, under the contract's names. Where the contract
      spells the header `Idempotency-Key`, write it `idempotencyKey`; other header
      names are written as the contract spells them, such as
      `"idempotency-key"`, `"content-type"`, and `"content-length"` for
      `uploadAttachment`.
    * `body`: the request body.

    Other names are the contract's own, which are camelCase. A method resolves to the response
    body, typed with the contract's fields. An optional second argument takes
    `{ signal, headers }` for one call: an `AbortSignal` to cancel it, and extra
    headers to send.
  </Tab>

  <Tab title="Python">
    Methods are grouped into namespaces that follow the API paths, in snake\_case,
    such as `photon.organizations.projects.list` or `photon.projects.agent_profile.get`.
    Each method takes one input model from `photon_api.rpc_generated`, named
    after the operation: `ListProjectsInput` for `listProjects`. Build it with
    `model_validate` from a dictionary that uses the contract's names, with
    `path`, `query`, `headers`, and `body` keys as the endpoint declares. Header
    names are spelled as the contract spells them, such as `"Idempotency-Key"`, or
    `"idempotency-key"` for `uploadAttachment`.

    Building the input checks types and required fields and raises
    `pydantic.ValidationError` if they do not match. Responses are Pydantic models
    whose fields keep the contract's names, such as `page.nextPageToken`. Dates and
    date-times are strings, as the API sends them.

    An optional field the response leaves out is `MISSING`, Pydantic's sentinel
    from `pydantic.experimental.missing_sentinel`, not `None`. `MISSING` is truthy,
    so test for it with `is not MISSING`, or check the value's type, as in
    `isinstance(page.nextPageToken, str)`. `None` means the API sent `null`.

    `Photon` is synchronous. `AsyncPhoton` has the same methods as coroutines. Close
    a client to release its connections: use `with` or `async with`, or call
    `close()`.
  </Tab>

  <Tab title="Rust">
    Each operation is a method on `Client`, named after the operation in
    snake\_case: `list_projects` for `listProjects`. Path parameters, required header
    parameters, and the request body are positional arguments; the method's
    signature on [docs.rs](https://docs.rs/photonhq-api) gives their order. Optional
    query and header parameters go in a `<Operation>Params` builder, such as
    `ListProjectsParams`, passed as `Some(params)` or `None`.

    Models are in `photon_ai_api::types`, with snake\_case fields. A call returns
    `Result<ResponseValue<T>, Error<E>>`: `into_inner()` gives the body, and
    [Raw responses](/docs/beta/api-client/raw-responses) covers the rest. When an operation
    has more than one success status, `T` is an enum with a variant for each, such
    as `CreateProjectResponse::Status201` and `CreateProjectResponse::Status202`.

    With the optional `blocking` feature, the crate also provides `BlockingClient`,
    a synchronous wrapper. It is built directly rather than with
    `PhotonClientBuilder`, so the builder's timeout and retry settings do not apply
    to it.
  </Tab>

  <Tab title="Go">
    Services mirror the API namespaces: `client.Organizations.Projects.List`,
    `client.Projects.Get`. A method takes a `context.Context`, a pointer to its
    `<Operation>Params` struct when the operation has parameters or a body, and
    optional `RequestOption`s; it returns the typed response body and an `error`.
    Path, query, and header parameters and `Body` are the params struct's fields,
    under the contract's names in Go's exported casing (`organizationId` becomes
    `OrganizationID`). Optional parameters are pointers; set them with
    `photonapi.Ptr`.

    Enums are plain string types, so unknown values pass through. Unions keep
    their raw JSON: branch on the union's `Kind()` method where it declares a
    discriminator (every message, space and user union does), or on
    `Discriminator(field)`, then decode with the union's `As<Member>` methods.
    Timestamps are `photonapi.Timestamp` values in UTC with millisecond
    precision.
  </Tab>
</Tabs>

| Operation | TypeScript | Python | Rust | Go |
| - | - | - | - | - |
| `listProjects` | `photon.organizations.projects.list` | `photon.organizations.projects.list` | `client.list_projects` | `client.Organizations.Projects.List` |
| `createProject` | `photon.organizations.projects.create` | `photon.organizations.projects.create` | `client.create_project` | `client.Organizations.Projects.Create` |
| `getProject` | `photon.projects.get` | `photon.projects.get` | `client.get_project` | `client.Projects.Get` |

Request values are typed by the contract and sent as given. Rules such as
patterns, lengths, and ranges are checked by the API, which answers with an
error such as `VALIDATION_FAILED` when a value breaks one. See
[Errors](/docs/beta/api-client/errors).

## Send a body and headers

Creating a project takes a path parameter, an `Idempotency-Key` header, and a
JSON body. [Retries and timeouts](/docs/beta/api-client/retries-and-timeouts#idempotency-keys)
explains the idempotency key. The Rust example generates the key with the
[`rand`](https://crates.io/crates/rand) crate; add it with `cargo add rand`.
The Go client generates a key itself when the params leave the field empty,
and reuses it across its own retries.

<CodeGroup>
  ```typescript TypeScript theme={null}
  import { randomUUID } from "node:crypto";
  import { Photon } from "@photon-ai/api";

  const apiKey = process.env.PHOTON_API_KEY;
  const organizationId = process.env.PHOTON_ORGANIZATION_ID;
  if (!apiKey || !organizationId) {
    throw new Error("Set PHOTON_API_KEY and PHOTON_ORGANIZATION_ID");
  }

  const photon = new Photon({
    headers: { Authorization: `Bearer ${apiKey}` },
  });

  const project = await photon.organizations.projects.create({
    path: { organizationId },
    headers: { idempotencyKey: randomUUID() },
    body: { name: "Support", slug: "support" },
  });
  console.log(project.projectId);
  ```

  ```python Python theme={null}
  import os
  import uuid

  from photon_api import Photon
  from photon_api.rpc_generated import CreateProjectInput

  api_key = os.environ["PHOTON_API_KEY"]
  organization_id = os.environ["PHOTON_ORGANIZATION_ID"]

  with Photon(headers={"Authorization": f"Bearer {api_key}"}) as photon:
      project = photon.organizations.projects.create(
          CreateProjectInput.model_validate(
              {
                  "path": {"organizationId": organization_id},
                  "headers": {"Idempotency-Key": str(uuid.uuid4())},
                  "body": {"name": "Support", "slug": "support"},
              }
          )
      )
      print(project.projectId)
  ```

  ```rust Rust theme={null}
  use photon_ai_api::{CreateProjectResponse, Credential, PhotonClientBuilder, SecretString, types};

  #[tokio::main]
  async fn main() -> Result<(), Box<dyn std::error::Error>> {
      let api_key = std::env::var("PHOTON_API_KEY")?;
      let organization_id = std::env::var("PHOTON_ORGANIZATION_ID")?;

      let credential = Credential::Bearer(SecretString::from(api_key));
      let client = PhotonClientBuilder::new()
          .credential("accountServiceKey", credential)
          .build()?;

      let body = types::CreateProjectRequest {
          name: "Support".to_owned(),
          slug: "support".to_owned(),
      };
      // Any unique key works; this one is 32 random hex digits.
      let idempotency_key = format!("{:032x}", rand::random::<u128>());
      let response = client
          .create_project(idempotency_key, organization_id, &body)
          .await
          .map_err(|error| format!("{error:?}"))?
          .into_inner();
      // 202: the project exists, but its billing is still being set up.
      let project = match response {
          CreateProjectResponse::Status201(project) | CreateProjectResponse::Status202(project) => {
              project
          }
      };
      println!("{}", project.project_id);
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

  	photonapi "github.com/photon-hq/api/packages/go"
  )

  func main() {
  	apiKey := os.Getenv("PHOTON_API_KEY")
  	organizationID := os.Getenv("PHOTON_ORGANIZATION_ID")
  	if apiKey == "" || organizationID == "" {
  		log.Fatal("Set PHOTON_API_KEY and PHOTON_ORGANIZATION_ID")
  	}

  	client := photonapi.NewClient(photonapi.WithAPIKey(apiKey))

  	// IdempotencyKey is left empty, so the client generates one.
  	project, err := client.Organizations.Projects.Create(context.Background(), &photonapi.CreateProjectParams{
  		OrganizationID: organizationID,
  		Body: photonapi.CreateProjectRequest{
  			Name: "Support",
  			Slug: "support",
  		},
  	})
  	if err != nil {
  		log.Fatal(err)
  	}
  	fmt.Println(project.ProjectID)
  }
  ```
</CodeGroup>

## Change the base URL

The clients call `https://api.photon.codes`. To call another address, such as a
local mock server in tests, set the base URL when you create the client.

<CodeGroup>
  ```typescript TypeScript theme={null}
  import { Photon } from "@photon-ai/api";

  const apiKey = process.env.PHOTON_API_KEY;
  const organizationId = process.env.PHOTON_ORGANIZATION_ID;
  if (!apiKey || !organizationId) {
    throw new Error("Set PHOTON_API_KEY and PHOTON_ORGANIZATION_ID");
  }

  const photon = new Photon({
    baseUrl: "http://localhost:8080",
    headers: { Authorization: `Bearer ${apiKey}` },
  });

  const result = await photon.organizations.projects.count({ path: { organizationId } });
  console.log(result.count);
  ```

  ```python Python theme={null}
  import os

  from photon_api import Photon
  from photon_api.rpc_generated import CountProjectsInput

  api_key = os.environ["PHOTON_API_KEY"]
  organization_id = os.environ["PHOTON_ORGANIZATION_ID"]

  with Photon(
      base_url="http://localhost:8080",
      headers={"Authorization": f"Bearer {api_key}"},
  ) as photon:
      result = photon.organizations.projects.count(
          CountProjectsInput.model_validate({"path": {"organizationId": organization_id}})
      )
      print(result.count)
  ```

  ```rust Rust theme={null}
  use photon_ai_api::{Credential, PhotonClientBuilder, SecretString};

  #[tokio::main]
  async fn main() -> Result<(), Box<dyn std::error::Error>> {
      let api_key = std::env::var("PHOTON_API_KEY")?;
      let organization_id = std::env::var("PHOTON_ORGANIZATION_ID")?;

      let credential = Credential::Bearer(SecretString::from(api_key));
      let client = PhotonClientBuilder::new()
          .base_url("http://localhost:8080")
          .credential("accountServiceKey", credential)
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

  	photonapi "github.com/photon-hq/api/packages/go"
  )

  func main() {
  	apiKey := os.Getenv("PHOTON_API_KEY")
  	organizationID := os.Getenv("PHOTON_ORGANIZATION_ID")
  	if apiKey == "" || organizationID == "" {
  		log.Fatal("Set PHOTON_API_KEY and PHOTON_ORGANIZATION_ID")
  	}

  	client := photonapi.NewClient(
  		photonapi.WithBaseURL("http://localhost:8080"),
  		photonapi.WithAPIKey(apiKey),
  	)

  	result, err := client.Organizations.Projects.Count(context.Background(), &photonapi.CountProjectsParams{
  		OrganizationID: organizationID,
  	})
  	if err != nil {
  		log.Fatal(err)
  	}
  	fmt.Println(result.Count)
  }
  ```
</CodeGroup>

You can also bring your own HTTP client: the `fetch` option in TypeScript,
`client=` (an `httpx.Client` for `Photon`, an `httpx.AsyncClient` for
`AsyncPhoton`) in Python, `reqwest_client` on the Rust builder, and
`WithHTTPClient` (an `*http.Client`, which is also where a Go timeout lives)
in Go. The base URL,
timeout, and retry settings still apply, except that in Rust the builder's
timeout is no longer also the connect timeout: configure that on your
`reqwest::Client`. In Python, a client you pass in is not closed for you.


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.