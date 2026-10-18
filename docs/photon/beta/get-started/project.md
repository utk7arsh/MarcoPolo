> ## Documentation Index
> Fetch the complete documentation index at: https://docs.photon.codes/docs/llms.txt
> Use this file to discover all available pages before exploring further.

> ## Agent Instructions
> Use Stable documentation by default. Honor an explicit Beta request or a URL under /docs/beta/. If the requested version conflicts with the installed CLI package or API origin, clarify the target before writing integration code.
> Pages under /docs/beta/ document Beta; other product pages document Stable. Keep the CLI package, commands, API origin, and credentials within the selected version. State the documentation version in your answer.
> For MCP search, always pass version: Stable or version: Beta. Unfiltered search mixes both versions. For filesystem reads, keep Beta queries under /beta/ and exclude /beta/ from Stable queries; discover paths before reading them.
> The public docs base is https://photon.codes/docs. Convert MCP page paths to public URLs under that base, preserving /beta/ when present. Read https://photon.codes/docs/skill.md for version selection and https://photon.codes/docs/llms.txt for the version indexes.

# Set up your project

> Choose a Photon project, create a server-side API key, and prepare your development environment.

Use one project for your first agent. Its channel connections, messages, Voice
profiles, and API key belong together; a key from another project cannot access
them.

<Steps>
  <Step title="Choose your project">
    Open the [Photon Beta dashboard](https://app.beta.photon.codes). Create an organization
    and project if you do not have one, or select your project in the switcher
    at the top of the sidebar.

    Open **Settings** and copy the **Project ID**, beginning with `pho_prj_`.
    Keep this project selected for the rest of the walkthrough. Ask an
    organization admin for access if you cannot manage its keys or channels.
  </Step>

  <Step title="Create an API key">
    Open **API keys** in the project sidebar, then **New API key**. Name it
    **First agent**, choose an expiry, and select the permissions it needs:

    | Permission | When you need it |
    | - | - |
    | `project:read` | Read messages for the iMessage and email tests. |
    | `project:write` | Send the agent's replies. |
    | `platforms:read` | Read channel configuration or a Voice profile with a client. |
    | `platforms:write` | Run the optional client examples that assign a shared line or connect a domain. Not needed when you configure them in the dashboard. |

    <Frame caption="The messaging program needs project:read and project:write. Add platform permissions only for the setup examples you run. Sample dashboard preview; no key is shown.">
      <img src="https://mintcdn.com/photon-6d78d87b/ihPr8z21mxGiVObP/beta/images/get-started/project-api-key.png?fit=max&auto=format&n=ihPr8z21mxGiVObP&q=85&s=213d54ea042f38f75bfc063d7d71cf83" alt="New API key form named First agent with project:read and project:write selected." width="720" height="802" data-path="beta/images/get-started/project-api-key.png" />
    </Frame>

    Select **Create key**. Copy and save the key when it appears on the page:
    **it is shown only once**. If you lose it, create a replacement and revoke
    the old key rather than trying to retrieve its plaintext.
  </Step>

  <Step title="Set your environment variables">
    In the terminal where you will run the examples, set your project ID and
    key. Replace the placeholders locally; do not paste real credentials into
    shared code or screenshots. Choose the block for your shell; macOS uses
    zsh by default. Both prompts keep the key out of shell history.

    <CodeGroup>
      ```sh macOS (zsh) theme={null}
      export PHOTON_PROJECT_ID="pho_prj_REPLACE_WITH_YOUR_PROJECT_ID"
      read -rs "PHOTON_API_KEY?Photon API key: "; echo
      export PHOTON_API_KEY
      ```

      ```sh Bash theme={null}
      export PHOTON_PROJECT_ID="pho_prj_REPLACE_WITH_YOUR_PROJECT_ID"
      read -rsp "Photon API key: " PHOTON_API_KEY; echo
      export PHOTON_API_KEY
      ```
    </CodeGroup>

    Your application's secret manager is a better place for a deployed key.

    <Warning>
      Run these examples on your computer or server, never in a browser or mobile
      app. Do not commit the key or a local environment file. All HTTP examples
      use `https://api.photon.codes` with `Authorization: Bearer <key>`.
    </Warning>
  </Step>

  <Step title="Install the client for your language">
    Create a working directory for the examples. Choose one language; you do
    not need all four. These setup examples use published client **0.5.0**.

    <CodeGroup>
      ```sh TypeScript theme={null}
      mkdir photon-first-agent && cd photon-first-agent
      npm init -y
      npm pkg set type=module
      npm install @photon-ai/api@0.5.0
      ```

      ```sh Python theme={null}
      mkdir photon-first-agent && cd photon-first-agent
      python3 -m venv .venv
      source .venv/bin/activate
      pip install photonhq-api==0.5.0
      ```

      ```sh Rust theme={null}
      cargo new photon-first-agent
      cd photon-first-agent
      cargo add photonhq-api@=0.5.0
      cargo add tokio --features macros,rt-multi-thread
      ```

      ```sh Go theme={null}
      mkdir photon-first-agent && cd photon-first-agent
      go mod init example.com/photon-first-agent
      go get github.com/photon-hq/api/packages/go@v0.5.0
      ```
    </CodeGroup>

    Use Node.js 24 or later for the TypeScript walkthrough, Python 3.11 or
    later, Rust 1.88 or later, or Go 1.25 or later. The messaging programs
    explain their additional HTTP dependencies where needed.
  </Step>
</Steps>

## Choose your first conversation

<CardGroup cols={3}>
  <Card title="iMessage" icon="comment" href="/docs/beta/get-started/imessage">
    Text a shared line from your own phone or iMessage email.
  </Card>

  <Card title="Email" icon="envelope" href="/docs/beta/get-started/email">
    Connect a domain and reply to your first incoming email.
  </Card>

  <Card title="Voice" icon="phone" href="/docs/beta/get-started/voice">
    Route a phone call to your voice agent over SIP.
  </Card>
</CardGroup>


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.