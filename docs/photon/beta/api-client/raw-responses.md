> ## Documentation Index
> Fetch the complete documentation index at: https://docs.photon.codes/docs/llms.txt
> Use this file to discover all available pages before exploring further.

> ## Agent Instructions
> Use Stable documentation by default. Honor an explicit Beta request or a URL under /docs/beta/. If the requested version conflicts with the installed CLI package or API origin, clarify the target before writing integration code.
> Pages under /docs/beta/ document Beta; other product pages document Stable. Keep the CLI package, commands, API origin, and credentials within the selected version. State the documentation version in your answer.
> For MCP search, always pass version: Stable or version: Beta. Unfiltered search mixes both versions. For filesystem reads, keep Beta queries under /beta/ and exclude /beta/ from Stable queries; discover paths before reading them.
> The public docs base is https://photon.codes/docs. Convert MCP page paths to public URLs under that base, preserving /beta/ when present. Read https://photon.codes/docs/skill.md for version selection and https://photon.codes/docs/llms.txt for the version indexes.

# Raw responses

> Read the status, headers, and request ID of a Photon API response.

A normal call returns only the response body. When you also need the HTTP
status, the response headers, or the request ID, use the raw form of the call:

| Language | Raw call | Result |
| - | - | - |
| TypeScript | `photon.raw.<namespace>.<method>(...)` | `{ data, status, headers, requestId }`. `headers` is a `Headers` object; `requestId` is `undefined` when the response has no `X-Request-ID`. |
| Python | `photon.raw.<namespace>.<method>(...)` | A `RawResponse` with `data`, `status`, `headers`, and `request_id`. `headers` is a `dict` with lowercase names; `request_id` is `None` when the response has no `X-Request-ID`. |
| Rust | Every call | A `ResponseValue<T>`: `status()`, `headers()` (a `reqwest` `HeaderMap`), `inner()` or `into_inner()` for the body, and `map()` to transform the body while keeping the rest. |
| Go | `photonapi.WithResponseInfo(&info)` as a `RequestOption` on any call | Fills a `ResponseInfo` with `StatusCode`, `Header` (an `http.Header`), `RequestID` (empty when the response has no `X-Request-ID`), and `Replayed` (an `Idempotent-Replayed` response). |

`raw` has the same namespaces and methods as the client, takes the same input,
and applies the same retries and errors. `data` is the same body the normal call
returns.

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

  const response = await photon.raw.organizations.projects.list({
    path: { organizationId },
  });
  console.log(response.status, response.requestId);
  console.log(response.headers.get("content-type"));
  console.log(`${response.data.projects.length} projects on this page`);
  ```

  ```python Python theme={null}
  import os

  from photon_api import Photon
  from photon_api.rpc_generated import ListProjectsInput

  api_key = os.environ["PHOTON_API_KEY"]
  organization_id = os.environ["PHOTON_ORGANIZATION_ID"]

  with Photon(headers={"Authorization": f"Bearer {api_key}"}) as photon:
      response = photon.raw.organizations.projects.list(
          ListProjectsInput.model_validate({"path": {"organizationId": organization_id}})
      )
      print(response.status, response.request_id)
      print(response.headers.get("content-type"))
      print(f"{len(response.data.projects)} projects on this page")
  ```

  ```rust Rust theme={null}
  use photon_ai_api::{Credential, PhotonClientBuilder, SecretString};

  #[tokio::main]
  async fn main() -> Result<(), Box<dyn std::error::Error>> {
      let api_key = std::env::var("PHOTON_API_KEY")?;
      let organization_id = std::env::var("PHOTON_ORGANIZATION_ID")?;

      let credential = Credential::Bearer(SecretString::from(api_key));
      let client = PhotonClientBuilder::new()
          .credential("accountServiceKey", credential)
          .build()?;

      let response = client
          .list_projects(organization_id, None)
          .await
          .map_err(|error| format!("{error:?}"))?;
      let request_id = response
          .headers()
          .get("x-request-id")
          .and_then(|value| value.to_str().ok())
          .unwrap_or("none");
      println!("{} {request_id}", response.status());
      println!("{} projects on this page", response.inner().projects.len());
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

  	var info photonapi.ResponseInfo
  	page, err := client.Organizations.Projects.List(
  		context.Background(),
  		&photonapi.ListProjectsParams{OrganizationID: organizationID},
  		photonapi.WithResponseInfo(&info),
  	)
  	if err != nil {
  		log.Fatal(err)
  	}
  	fmt.Println(info.StatusCode, info.RequestID)
  	fmt.Println(info.Header.Get("content-type"))
  	fmt.Printf("%d projects on this page\n", len(page.Projects))
  }
  ```
</CodeGroup>

Errors carry the same details: see [Errors](/docs/beta/api-client/errors#request-ids).


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.