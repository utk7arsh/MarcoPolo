> ## Documentation Index
> Fetch the complete documentation index at: https://docs.photon.codes/docs/llms.txt
> Use this file to discover all available pages before exploring further.

> ## Agent Instructions
> Use Stable documentation by default. Honor an explicit Beta request or a URL under /docs/beta/. If the requested version conflicts with the installed CLI package or API origin, clarify the target before writing integration code.
> Pages under /docs/beta/ document Beta; other product pages document Stable. Keep the CLI package, commands, API origin, and credentials within the selected version. State the documentation version in your answer.
> For MCP search, always pass version: Stable or version: Beta. Unfiltered search mixes both versions. For filesystem reads, keep Beta queries under /beta/ and exclude /beta/ from Stable queries; discover paths before reading them.
> The public docs base is https://photon.codes/docs. Convert MCP page paths to public URLs under that base, preserving /beta/ when present. Read https://photon.codes/docs/skill.md for version selection and https://photon.codes/docs/llms.txt for the version indexes.

# Pagination

> Page through list results with page sizes and next-page tokens in the Photon API clients.

List endpoints such as `listProjects` return one page at a time. A page has the
items and, when more items follow, a `nextPageToken`. To get the next page, send
that token back as the `pageToken` query parameter. When a page has no
`nextPageToken`, it is the last one.

`pageSize` sets how many items a page holds, up to the limit the endpoint
documents; for `listProjects` it is 1 to 100. Each list endpoint's parameters,
including its own filters, are in the [API reference](/docs/beta/api-reference). The
clients do not page automatically, so you write the loop.

## List every project

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

  let pageToken: string | undefined;
  do {
    const page = await photon.organizations.projects.list({
      path: { organizationId },
      query: { pageSize: 100, pageToken },
    });
    for (const project of page.projects) {
      console.log(project.projectId, project.name);
    }
    pageToken = page.nextPageToken;
  } while (pageToken);
  ```

  ```python Python theme={null}
  import os
  from typing import Any

  from photon_api import Photon
  from photon_api.rpc_generated import ListProjectsInput

  api_key = os.environ["PHOTON_API_KEY"]
  organization_id = os.environ["PHOTON_ORGANIZATION_ID"]

  with Photon(headers={"Authorization": f"Bearer {api_key}"}) as photon:
      query: dict[str, Any] = {"pageSize": 100}
      while True:
          page = photon.organizations.projects.list(
              ListProjectsInput.model_validate(
                  {"path": {"organizationId": organization_id}, "query": query}
              )
          )
          for project in page.projects:
              print(project.projectId, project.name)
          # nextPageToken is absent (MISSING, not a string) on the last page.
          if not isinstance(page.nextPageToken, str):
              break
          query["pageToken"] = page.nextPageToken
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

      let mut page_token: Option<String> = None;
      loop {
          let mut params = ListProjectsParams::default().page_size(100);
          if let Some(token) = page_token.take() {
              params = params.page_token(token);
          }
          let page = client
              .list_projects(organization_id.clone(), Some(params))
              .await
              .map_err(|error| format!("{error:?}"))?
              .into_inner();
          for project in &page.projects {
              println!("{} {}", project.project_id, project.name);
          }
          match page.next_page_token {
              Some(token) => page_token = Some(token),
              None => break,
          }
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

  	params := &photonapi.ListProjectsParams{
  		OrganizationID: organizationID,
  		PageSize:       photonapi.Ptr(int64(100)),
  	}
  	for {
  		page, err := client.Organizations.Projects.List(context.Background(), params)
  		if err != nil {
  			log.Fatal(err)
  		}
  		for _, project := range page.Projects {
  			fmt.Println(project.ProjectID, project.Name)
  		}
  		// NextPageToken is nil on the last page.
  		if page.NextPageToken == nil {
  			break
  		}
  		params.PageToken = page.NextPageToken
  	}
  }
  ```
</CodeGroup>

Each page is a separate request, so each one is retried, and can fail, on its
own. See [Retries and timeouts](/docs/beta/api-client/retries-and-timeouts) and
[Errors](/docs/beta/api-client/errors).


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.