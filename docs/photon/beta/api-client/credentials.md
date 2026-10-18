> ## Documentation Index
> Fetch the complete documentation index at: https://docs.photon.codes/docs/llms.txt
> Use this file to discover all available pages before exploring further.

> ## Agent Instructions
> Use Stable documentation by default. Honor an explicit Beta request or a URL under /docs/beta/. If the requested version conflicts with the installed CLI package or API origin, clarify the target before writing integration code.
> Pages under /docs/beta/ document Beta; other product pages document Stable. Keep the CLI package, commands, API origin, and credentials within the selected version. State the documentation version in your answer.
> For MCP search, always pass version: Stable or version: Beta. Unfiltered search mixes both versions. For filesystem reads, keep Beta queries under /beta/ and exclude /beta/ from Stable queries; discover paths before reading them.
> The public docs base is https://photon.codes/docs. Convert MCP page paths to public URLs under that base, preserving /beta/ when present. Read https://photon.codes/docs/skill.md for version selection and https://photon.codes/docs/llms.txt for the version indexes.

# Credentials

> Choose a Photon credential and pass it to the TypeScript, Python, Rust, or Go client.

Every Photon credential is sent as `Authorization: Bearer <credential>`. The
API tells them apart; the clients only attach the one you give them.

## Credential types

| Credential | Looks like | Security scheme | What it can do |
| - | - | - | - |
| Account service key | `pho_ask_...` | `accountServiceKey` | Acts on behalf of the account that owns it, subject to each endpoint's permissions and credential restrictions. |
| Project API key | `pho_sk_...` | `projectApiKey` | Bound to one project. Accepted only under `/v1/projects/{projectId}` and refused everywhere else. |
| Service identity credential | An organization Service Identity API key or M2M access token | `serviceIdentityBearer` | Restricted to its organization and to the business permissions granted to it. It cannot govern the organization or manage Photon credentials. |
| OAuth access token | A JWT | `oauth2` | Issued by the Photon authorization server to your application. Its consented scopes are intersected with the permissions the endpoint grants; if nothing is left, the API answers `403` with `INSUFFICIENT_SCOPE`. |

Each endpoint in the [API reference](/docs/beta/api-reference) lists the credentials it
accepts, and a few endpoints need none. Use the narrowest credential that
reaches the endpoints you call: a project API key for work inside one project,
a service identity credential for automation in one organization, and an
account service key only when you need account-wide access.

Never send an M2M client secret to an API endpoint. Keep account service keys,
project API keys, and service identity credentials on your servers: do not embed
them in browser or mobile apps.

## Pass a credential

In TypeScript and Python, pass the header in the client's `headers` option. In
Rust, register the credential under the security scheme it belongs to with
`PhotonClientBuilder::credential`. In Go, pass an account service key, project
API key, or service identity credential with `WithAPIKey`.

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

  const result = await photon.organizations.projects.count({
    path: { organizationId },
  });
  console.log(`${result.count} projects`);
  ```

  ```python Python theme={null}
  import os

  from photon_api import Photon
  from photon_api.rpc_generated import CountProjectsInput

  api_key = os.environ["PHOTON_API_KEY"]
  organization_id = os.environ["PHOTON_ORGANIZATION_ID"]

  with Photon(headers={"Authorization": f"Bearer {api_key}"}) as photon:
      result = photon.organizations.projects.count(
          CountProjectsInput.model_validate({"path": {"organizationId": organization_id}})
      )
      print(f"{result.count} projects")
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

      let result = client
          .count_projects(organization_id, None)
          .await
          .map_err(|error| format!("{error:?}"))?;
      println!("{} projects", result.inner().count);
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

  	result, err := client.Organizations.Projects.Count(context.Background(), &photonapi.CountProjectsParams{
  		OrganizationID: organizationID,
  	})
  	if err != nil {
  		log.Fatal(err)
  	}
  	fmt.Printf("%d projects\n", result.Count)
  }
  ```
</CodeGroup>

### Security schemes in Rust

The Rust client checks each operation's accepted credentials before it sends
anything. Register your credential under its scheme name from the table above:
`"accountServiceKey"`, `"projectApiKey"`, `"serviceIdentityBearer"`, or
`"oauth2"`. If no registered credential matches an endpoint, the call fails with
`Error::RequestConstruction` and no request is sent. An `Authorization` header
set through `static_headers` or `headers` does not count as a registered
credential.

## Project API keys

A project API key works only on endpoints under `/v1/projects/{projectId}`, for
the project it belongs to. In Rust, register it as `"projectApiKey"`:

<CodeGroup>
  ```typescript TypeScript theme={null}
  import { Photon } from "@photon-ai/api";

  const apiKey = process.env.PHOTON_PROJECT_API_KEY;
  const projectId = process.env.PHOTON_PROJECT_ID;
  if (!apiKey || !projectId) {
    throw new Error("Set PHOTON_PROJECT_API_KEY and PHOTON_PROJECT_ID");
  }

  const photon = new Photon({
    headers: { Authorization: `Bearer ${apiKey}` },
  });

  const project = await photon.projects.get({ path: { projectId } });
  console.log(project.name);
  ```

  ```python Python theme={null}
  import os

  from photon_api import Photon
  from photon_api.rpc_generated import GetProjectInput

  api_key = os.environ["PHOTON_PROJECT_API_KEY"]
  project_id = os.environ["PHOTON_PROJECT_ID"]

  with Photon(headers={"Authorization": f"Bearer {api_key}"}) as photon:
      project = photon.projects.get(
          GetProjectInput.model_validate({"path": {"projectId": project_id}})
      )
      print(project.name)
  ```

  ```rust Rust theme={null}
  use photon_ai_api::{Credential, PhotonClientBuilder, SecretString};

  #[tokio::main]
  async fn main() -> Result<(), Box<dyn std::error::Error>> {
      let api_key = std::env::var("PHOTON_PROJECT_API_KEY")?;
      let project_id = std::env::var("PHOTON_PROJECT_ID")?;

      let credential = Credential::Bearer(SecretString::from(api_key));
      let client = PhotonClientBuilder::new()
          .credential("projectApiKey", credential)
          .build()?;

      let project = client
          .get_project(project_id)
          .await
          .map_err(|error| format!("{error:?}"))?
          .into_inner();
      println!("{}", project.name);
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
  	apiKey := os.Getenv("PHOTON_PROJECT_API_KEY")
  	projectID := os.Getenv("PHOTON_PROJECT_ID")
  	if apiKey == "" || projectID == "" {
  		log.Fatal("Set PHOTON_PROJECT_API_KEY and PHOTON_PROJECT_ID")
  	}

  	client := photonapi.NewClient(photonapi.WithAPIKey(apiKey))

  	project, err := client.Projects.Get(context.Background(), &photonapi.GetProjectParams{
  		ProjectID: projectID,
  	})
  	if err != nil {
  		log.Fatal(err)
  	}
  	fmt.Println(project.Name)
  }
  ```
</CodeGroup>

## OAuth access tokens

The clients do not run OAuth flows: they do not open authorization pages,
exchange codes, or refresh tokens. Your application's own login flow obtains
the access token and refreshes it. Give the client a function that returns the
current token:

* **TypeScript**: `headers` can be a function, sync or async. It is called
  before every attempt, including retries.
* **Python**: `headers` can be a callable. It is called before every attempt,
  including retries. For `AsyncPhoton` it can be async; for `Photon` it must be
  synchronous.
* **Rust**: register a `Credential::Provider` under `"oauth2"`. It is called
  once each time you call an operation that uses it; the client's retries of
  that call reuse the token.
* **Go**: pass a `TokenSource` function with `WithTokenSource`. It is called
  for every request the client sends, including retries.

<CodeGroup>
  ```typescript TypeScript theme={null}
  import { Photon } from "@photon-ai/api";

  // Your application's own OAuth flow obtains and refreshes this token.
  async function getAccessToken(): Promise<string> {
    const token = process.env.PHOTON_ACCESS_TOKEN;
    if (!token) throw new Error("Sign in first");
    return token;
  }

  const photon = new Photon({
    headers: async () => ({ Authorization: `Bearer ${await getAccessToken()}` }),
  });

  const account = await photon.account.get();
  console.log(account.email);
  ```

  ```python Python theme={null}
  import asyncio
  import os

  from photon_api import AsyncPhoton


  # Your application's own OAuth flow obtains and refreshes this token.
  async def get_access_token() -> str:
      return os.environ["PHOTON_ACCESS_TOKEN"]


  async def authorization() -> dict[str, str]:
      return {"Authorization": f"Bearer {await get_access_token()}"}


  async def main() -> None:
      async with AsyncPhoton(headers=authorization) as photon:
          account = await photon.account.get()
          print(account.email)


  asyncio.run(main())
  ```

  ```rust Rust theme={null}
  use std::sync::Arc;

  use photon_ai_api::{
      AuthError, Credential, PhotonClientBuilder, SecretString, TokenFuture, TokenProvider,
  };

  // Your application's own OAuth flow obtains and refreshes this token.
  async fn access_token() -> Result<String, AuthError> {
      std::env::var("PHOTON_ACCESS_TOKEN").map_err(|_| AuthError::new("Sign in first"))
  }

  #[tokio::main]
  async fn main() -> Result<(), Box<dyn std::error::Error>> {
      let provider: TokenProvider = Arc::new(|| -> TokenFuture {
          Box::pin(async { Ok(SecretString::from(access_token().await?)) })
      });

      let client = PhotonClientBuilder::new()
          .credential("oauth2", Credential::Provider(provider))
          .build()?;

      let account = client
          .get_account()
          .await
          .map_err(|error| format!("{error:?}"))?
          .into_inner();
      println!("{}", account.email);
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

  // Your application's own OAuth flow obtains and refreshes this token.
  func accessToken(ctx context.Context) (string, error) {
  	token := os.Getenv("PHOTON_ACCESS_TOKEN")
  	if token == "" {
  		return "", errors.New("sign in first")
  	}
  	return token, nil
  }

  func main() {
  	client := photonapi.NewClient(photonapi.WithTokenSource(accessToken))

  	account, err := client.Account.Get(context.Background())
  	if err != nil {
  		log.Fatal(err)
  	}
  	fmt.Println(account.Email)
  }
  ```
</CodeGroup>

An OAuth token works only on endpoints that accept `oauth2` and only within the
scopes the user granted. Each endpoint in the [API reference](/docs/beta/api-reference)
lists the scope it needs.


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.