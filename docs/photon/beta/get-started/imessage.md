> ## Documentation Index
> Fetch the complete documentation index at: https://docs.photon.codes/docs/llms.txt
> Use this file to discover all available pages before exploring further.

> ## Agent Instructions
> Use Stable documentation by default. Honor an explicit Beta request or a URL under /docs/beta/. If the requested version conflicts with the installed CLI package or API origin, clarify the target before writing integration code.
> Pages under /docs/beta/ document Beta; other product pages document Stable. Keep the CLI package, commands, API origin, and credentials within the selected version. State the documentation version in your answer.
> For MCP search, always pass version: Stable or version: Beta. Unfiltered search mixes both versions. For filesystem reads, keep Beta queries under /beta/ and exclude /beta/ from Stable queries; discover paths before reading them.
> The public docs base is https://photon.codes/docs. Convert MCP page paths to public URLs under that base, preserving /beta/ when present. Read https://photon.codes/docs/skill.md for version selection and https://photon.codes/docs/llms.txt for the version indexes.

# Build an iMessage agent

> Assign a shared iMessage line, run a small agent in your language, and receive its first reply.

Send **ping** from your iPhone or Mac and receive **Hello from your Photon
agent!**. This walkthrough uses a shared iMessage line and a small program on
your computer. You do not need a public webhook server or an AI model yet.

## Before you start

* Complete [Set up your project](/docs/beta/get-started/project), including a key
  with `project:read` and `project:write`.
* Have an iMessage-enabled phone number or Apple-account email you can send
  from, and a plan with shared iMessage capacity. Check
  [plans and billing](/docs/beta/plans-and-billing) before assigning a seat.
* Keep Messages available on your device. You must start the conversation;
  a shared line cannot send an unsolicited first message.

<Steps>
  <Step title="Add the identity you will send from">
    In the dashboard, select your project and open **iMessage**. Under **Add the
    number you or your user will send from**, enter your own iMessage phone
    number. To test with an Apple-account email instead, select **Use an iMessage
    email instead**.

    <Frame caption="Enter the human sender's identity, not a number for the agent. Dashboard preview with sample data.">
      <img src="https://mintcdn.com/photon-6d78d87b/ihPr8z21mxGiVObP/beta/images/get-started/imessage-add-sender.png?fit=max&auto=format&n=ihPr8z21mxGiVObP&q=85&s=34131052e2a8e0c60937fcc2bd98fad4" alt="Shared iMessage setup asks for the number the user will send from, with Add and an email alternative." width="720" height="464" data-path="beta/images/get-started/imessage-add-sender.png" />
    </Frame>

    On iPhone, check **Settings → Apps → Messages → Send & Receive** to confirm
    the identity you will use. A phone number and an Apple-account email are
    different senders, even when both belong to you.

    Select **Add**, then complete **Assign a number from the shared pool**.
    Copy the assigned number. That is your **agent's** number; your own identity
    is the **test sender**. Only messages from the assigned sender reach this
    shared-line connection.

    <Accordion title="Assign the line with an API client instead">
      This replaces the dashboard assignment; do not run both for the same
      test. The key also needs `platforms:write`. Assignment uses plan capacity.
      Set `PHOTON_TEST_SENDER` to your phone in E.164 format, such as
      `+14155550123`, or your exact iMessage email. Set `PHOTON_SETUP_KEY` to a
      unique value and keep it unchanged when retrying this same assignment.

      ```sh theme={null}
      export PHOTON_TEST_SENDER="+14155550123"
      export PHOTON_SETUP_KEY="first-agent-imessage-$(date +%s)"
      ```

      Run these exports once and save the value of `PHOTON_SETUP_KEY`.
      Retry only the program below with that same key. In a new terminal,
      restore the saved value instead of generating another key.

      Save the example as `setup.ts`, `setup.py`, `src/main.rs`, or `main.go` in the
      directory you prepared in [project setup](/docs/beta/get-started/project).

      <CodeGroup>
        ```typescript TypeScript theme={null}
        import { Photon } from "@photon-ai/api";

        const required = (name: string): string => {
          const value = process.env[name];
          if (!value) throw new Error(`Set ${name}`);
          return value;
        };

        const photon = new Photon({
          headers: { Authorization: `Bearer ${required("PHOTON_API_KEY")}` },
        });
        try {
          const assignment = await photon.projects.platforms.imessage.assignments.create({
            path: { id: required("PHOTON_PROJECT_ID") },
            headers: { idempotencyKey: required("PHOTON_SETUP_KEY") },
            body: { handle: required("PHOTON_TEST_SENDER") },
          });
          console.log(assignment.assignedPhoneNumber);
        } catch {
          console.error("Could not assign the shared line. Check the key, permissions, and plan capacity.");
          process.exitCode = 1;
        }
        ```

        ```python Python theme={null}
        import os

        from photon_api import Photon, PhotonError
        from photon_api.generated.models import CreateSharedLineAssignmentRequest
        from photon_api.rpc_generated import (
            CreateSharedLineAssignmentHeader,
            CreateSharedLineAssignmentInput,
            CreateSharedLineAssignmentPath,
        )

        try:
            with Photon(headers={"Authorization": f"Bearer {os.environ['PHOTON_API_KEY']}"}) as photon:
                assignment = photon.projects.platforms.imessage.assignments.create(
                    CreateSharedLineAssignmentInput(
                        path=CreateSharedLineAssignmentPath(id=os.environ["PHOTON_PROJECT_ID"]),
                        headers=CreateSharedLineAssignmentHeader.model_validate(
                            {"Idempotency-Key": os.environ["PHOTON_SETUP_KEY"]}
                        ),
                        body=CreateSharedLineAssignmentRequest(
                            handle=os.environ["PHOTON_TEST_SENDER"]
                        ),
                    )
                )
                print(assignment.assignedPhoneNumber)
        except PhotonError:
            raise SystemExit("Could not assign the shared line. Check the key, permissions, and plan capacity.") from None
        ```

        ```rust Rust theme={null}
        use photon_ai_api::{types, Credential, PhotonClientBuilder, SecretString};

        #[tokio::main]
        async fn main() -> Result<(), Box<dyn std::error::Error>> {
            let client = PhotonClientBuilder::new()
                .credential(
                    "projectApiKey",
                    Credential::Bearer(SecretString::from(std::env::var("PHOTON_API_KEY")?)),
                )
                .build()?;
            let assignment = client
                .create_shared_line_assignment(
                    std::env::var("PHOTON_SETUP_KEY")?,
                    std::env::var("PHOTON_PROJECT_ID")?,
                    &types::CreateSharedLineAssignmentRequest {
                        handle: std::env::var("PHOTON_TEST_SENDER")?,
                        email: None,
                        first_name: None,
                        last_name: None,
                    },
                )
                .await
                .map_err(|_| "Could not assign the shared line. Check the key, permissions, and plan capacity.")?;
            println!("{}", assignment.inner().assigned_phone_number);
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

        func required(name string) string {
            value := os.Getenv(name)
            if value == "" {
                log.Fatalf("Set %s", name)
            }
            return value
        }

        func main() {
            client := photonapi.NewClient(photonapi.WithAPIKey(required("PHOTON_API_KEY")))
            assignment, err := client.Projects.Platforms.Imessage.Assignments.Create(
                context.Background(), &photonapi.CreateSharedLineAssignmentParams{
                    ID: required("PHOTON_PROJECT_ID"),
                    IdempotencyKey: required("PHOTON_SETUP_KEY"),
                    Body: photonapi.CreateSharedLineAssignmentRequest{
                        Handle: photonapi.ImessageHandle(required("PHOTON_TEST_SENDER")),
                    },
                },
            )
            if err != nil {
                log.Fatal("Could not assign the shared line. Check the key, permissions, and plan capacity.")
            }
            fmt.Println(assignment.AssignedPhoneNumber)
        }
        ```
      </CodeGroup>

      <CodeGroup>
        ```sh TypeScript theme={null}
        node setup.ts
        ```

        ```sh Python theme={null}
        python setup.py
        ```

        ```sh Rust theme={null}
        cargo run --bin photon-first-agent
        ```

        ```sh Go theme={null}
        go run main.go
        ```
      </CodeGroup>

      The program prints the assigned number. Save it as `PHOTON_AGENT_HANDLE`
      below. Do not create an agent User ID from this number; the incoming
      message supplies the IDs used for its reply.
    </Accordion>
  </Step>

  <Step title="Configure your test identities">
    Use your actual values, not the sample phone numbers shown here. Include
    `+` and the country code for phone numbers. Keep email spelling consistent
    with the identity used in Messages.

    ```sh theme={null}
    export PHOTON_PLATFORM="imessage"
    export PHOTON_TEST_SENDER="+14155550123"
    export PHOTON_AGENT_HANDLE="+14155550188"
    ```

    | Variable | What it identifies |
    | - | - |
    | `PHOTON_TEST_SENDER` | Your human send-from phone number or iMessage email. |
    | `PHOTON_AGENT_HANDLE` | The number Photon assigned for this sender. |
  </Step>

  <Step title="Run your agent">
    This program uses the **SDK messaging methods**: `listMessages` polls for a
    new message every two seconds for up to two minutes, `sendMessage` replies
    once, and the program exits. The client validates responses against the
    contract and retries transient failures, so the code checks only the
    walkthrough's own rules.

    It only answers a plain-text **ping** from your configured test sender to
    your configured agent. Surrounding whitespace is ignored, but signatures or
    other text are not. For email, a plain-text part may accompany an HTML
    alternative. HTML-only email is not a match.

    The reply reuses the incoming message's `space.id`, `receivedBy.id`, and `id`
    as `spaceId`, `senderId`, and `parentMessageId`. Its stable
    `Idempotency-Key` is `first-agent-reply:<incoming Message ID>`.

    Save the code for **one language** in the directory from project setup:

    | Language | File |
    | - | - |
    | TypeScript | `agent.ts` |
    | Python | `agent.py` |
    | Rust | `src/bin/agent.rs` — create `src/bin` first, and run `cargo add time` once. |
    | Go | `agent.go` — or `main.go`; run one file. |

    <CodeGroup>
      ```typescript TypeScript expandable theme={null}
      import { pathToFileURL } from "node:url";
      import { setTimeout as sleep } from "node:timers/promises";
      import { ApiError, Photon } from "@photon-ai/api";

      type Config = { key: string; project: string; platform: "imessage" | "email"; agent: string; sender: string };

      export function configuration(): Config {
        const required = (name: string) => {
          const value = process.env[name];
          if (!value) throw new Error(`Missing ${name}.`);
          return value;
        };
        const platform = required("PHOTON_PLATFORM");
        if (platform !== "imessage" && platform !== "email") throw new Error("PHOTON_PLATFORM must be imessage or email.");
        return {
          key: required("PHOTON_API_KEY"), project: required("PHOTON_PROJECT_ID"),
          platform, agent: required("PHOTON_AGENT_HANDLE"), sender: required("PHOTON_TEST_SENDER"),
        };
      }

      type Page = Awaited<ReturnType<Photon["projects"]["listMessages"]>>;
      type Item = Page["items"][number];

      // The client validates every response against the contract, so these checks
      // are the walkthrough's own rules: the right conversation, sender, and text.
      // A match returns the reply's inputs.
      function matching(m: Item, c: Config, startedAt: number): { id: string; spaceId: string; senderId: string } | undefined {
        if (m.platform !== c.platform || m.status !== "received") return undefined;
        if (Date.parse(m.createdAt) < startedAt) return undefined;
        if (m.sentBy.platform !== c.platform || m.receivedBy?.platform !== c.platform || m.space.platform !== c.platform) return undefined;
        if (m.sentBy.kind !== "human" || m.sentBy.handle !== c.sender) return undefined;
        if (m.receivedBy.kind !== "agent" || m.receivedBy.handle !== c.agent) return undefined;
        if (m.sentBy.id === m.receivedBy.id) return undefined;
        if (c.platform === "imessage" && m.space.kind !== "direct") return undefined;
        const found = { id: m.id, spaceId: m.space.id, senderId: m.receivedBy.id };
        const content = m.content;
        if (content.type === "text") {
          return content.format === "plain" && content.text.trim() === "ping" ? found : undefined;
        }
        if (c.platform !== "email" || content.type !== "group") return undefined;
        const plain = content.parts.flatMap((part) => (part.type === "text" && part.format === "plain" ? [part] : []));
        return plain.length === 1 && plain[0].text.trim() === "ping" ? found : undefined;
      }

      export async function run(c: Config, windowMs = 120_000, pollMs = 2_000) {
        const photon = new Photon({ headers: { Authorization: `Bearer ${c.key}` } });
        const startedAt = Date.now();
        const deadline = startedAt + windowMs;
        const createdSince = new Date(startedAt - 5_000).toISOString();
        console.log("Ready. Waiting for the configured test sender.");
        while (true) {
          let pageToken: string | undefined;
          do {
            const page = await photon.projects.listMessages({
              path: { id: c.project },
              query: { createdSince, direction: "received", order: "asc", pageSize: 100, platform: c.platform, ...(pageToken ? { pageToken } : {}) },
            });
            for (const m of page.items) {
              const found = matching(m, c, startedAt);
              if (!found) continue;
              await photon.projects.sendMessage({
                path: { id: c.project },
                headers: { "idempotency-key": `first-agent-reply:${found.id}` },
                body: {
                  spaceId: found.spaceId, senderId: found.senderId, parentMessageId: found.id,
                  content: { type: "text", format: "plain", text: "Hello from your Photon agent!" },
                },
              });
              console.log("Reply accepted for asynchronous dispatch; delivery is not confirmed.");
              return;
            }
            pageToken = page.nextPageToken;
          } while (pageToken);
          if (Date.now() + pollMs > deadline) throw new Error("No matching ping found before the deadline.");
          await sleep(pollMs);
        }
      }

      if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
        try {
          await run(configuration());
        } catch (error) {
          if (error instanceof ApiError) console.error(`Photon API error ${error.status} (request ${error.requestId ?? "unknown"}).`);
          else console.error(error instanceof Error ? error.message : "Agent failed.");
          process.exitCode = 1;
        }
      }
      ```

      ```python Python expandable theme={null}
      import os
      import sys
      import time
      from datetime import datetime, timedelta, timezone

      from photon_api import ApiError, Photon
      from photon_api.generated.models import (
          EmailGroupContent,
          SendMessageRequest,
          SendTextContent,
          TextContent,
          UserSnapshot,
      )
      from photon_api.rpc_generated import ListMessagesInput, SendMessageHeader, SendMessageInput, SendMessagePath


      def configuration():
          names = ("PHOTON_API_KEY", "PHOTON_PROJECT_ID", "PHOTON_PLATFORM", "PHOTON_AGENT_HANDLE", "PHOTON_TEST_SENDER")
          for name in names:
              if not os.environ.get(name):
                  raise RuntimeError(f"Missing {name}.")
          key, project, platform, agent, sender = (os.environ[name] for name in names)
          if platform not in ("imessage", "email"):
              raise RuntimeError("PHOTON_PLATFORM must be imessage or email.")
          return dict(key=key, project=project, platform=platform, agent=agent, sender=sender)


      def matches(item, c, started_at):
          # The client validates every response against the contract, so these checks
          # are the walkthrough's own rules: the right conversation, sender, and text.
          m = item.root.root
          if m.platform != c["platform"] or m.status != "received":
              return False
          if datetime.fromisoformat(m.createdAt) < started_at:
              return False
          if not isinstance(m.receivedBy, UserSnapshot):
              return False
          sender, agent, space = m.sentBy.root, m.receivedBy.root, m.space.root
          if sender.kind != "human" or sender.handle != c["sender"]:
              return False
          if agent.kind != "agent" or agent.handle != c["agent"] or sender.id == agent.id:
              return False
          if c["platform"] == "imessage" and space.kind != "direct":
              return False
          content = m.content
          if isinstance(content, TextContent):
              return content.format == "plain" and content.text.strip() == "ping"
          if c["platform"] != "email" or not isinstance(content, EmailGroupContent):
              return False
          plain = [p for p in (part.root for part in content.parts) if isinstance(p, TextContent) and p.format == "plain"]
          return len(plain) == 1 and plain[0].text.strip() == "ping"


      def run(c, window_s=120.0, poll_s=2.0):
          started_at = datetime.now(timezone.utc)
          deadline = time.monotonic() + window_s
          created_since = (started_at - timedelta(seconds=5)).isoformat(timespec="milliseconds").replace("+00:00", "Z")
          with Photon(headers={"Authorization": f"Bearer {c['key']}"}) as photon:
              print("Ready. Waiting for the configured test sender.")
              while True:
                  query = {"createdSince": created_since, "direction": "received", "order": "asc", "pageSize": 100, "platform": c["platform"]}
                  while True:
                      page = photon.projects.list_messages(
                          ListMessagesInput.model_validate({"path": {"id": c["project"]}, "query": query})
                      )
                      for item in page.items:
                          if not matches(item, c, started_at):
                              continue
                          m = item.root.root
                          photon.projects.send_message(
                              SendMessageInput(
                                  path=SendMessagePath(id=c["project"]),
                                  headers=SendMessageHeader.model_validate({"idempotency-key": f"first-agent-reply:{m.id}"}),
                                  body=SendMessageRequest(
                                      spaceId=m.space.root.id,
                                      senderId=m.receivedBy.root.id,
                                      parentMessageId=m.id,
                                      content=SendTextContent(type="text", format="plain", text="Hello from your Photon agent!"),
                                  ),
                              )
                          )
                          print("Reply accepted for asynchronous dispatch; delivery is not confirmed.")
                          return
                      token = page.nextPageToken
                      if not isinstance(token, str):
                          break
                      query["pageToken"] = token
                  if time.monotonic() + poll_s > deadline:
                      raise RuntimeError("No matching ping found before the deadline.")
                  time.sleep(poll_s)


      if __name__ == "__main__":
          try:
              run(configuration())
          except ApiError as error:
              print(f"Photon API error {error.status} (request {error.request_id or 'unknown'}).", file=sys.stderr)
              sys.exit(1)
          except RuntimeError as error:
              print(error, file=sys.stderr)
              sys.exit(1)
      ```

      ```rust Rust expandable theme={null}
      use std::time::{Duration, Instant};

      use photon_ai_api::types::{
          EmailGroupContentPart, EmailMessage, EmailMessageContent, ImessageMessage, ImessageMessageContent,
          MessageDirection, Platform, PlatformMessage, SendContent, SendMessageRequest, SendTextContent,
          SortOrder, SpaceSnapshot, UserSnapshot,
      };
      use photon_ai_api::{Credential, DateTime, ListMessagesParams, PhotonClientBuilder, SecretString};

      struct Config {
          key: String,
          project: String,
          platform: String,
          agent: String,
          sender: String,
      }

      fn configuration() -> Result<Config, Box<dyn std::error::Error>> {
          let required = |name: &str| match std::env::var(name) {
              Ok(value) if !value.is_empty() => Ok(value),
              _ => Err(format!("Missing {name}.")),
          };
          let platform = required("PHOTON_PLATFORM")?;
          if platform != "imessage" && platform != "email" {
              return Err("PHOTON_PLATFORM must be imessage or email.".into());
          }
          Ok(Config {
              key: required("PHOTON_API_KEY")?,
              project: required("PHOTON_PROJECT_ID")?,
              platform,
              agent: required("PHOTON_AGENT_HANDLE")?,
              sender: required("PHOTON_TEST_SENDER")?,
          })
      }

      /// The reply's inputs, taken from a matching incoming message.
      struct Incoming {
          id: String,
          space_id: String,
          agent_id: String,
      }

      /// The client validates every response against the contract, so these checks
      /// are the walkthrough's own rules: the right conversation, sender, and text.
      fn incoming(message: &PlatformMessage, c: &Config, started: DateTime) -> Option<Incoming> {
          match message {
              PlatformMessage::ImessageMessage(platform_message) if c.platform == "imessage" => {
                  let ImessageMessage::ReceivedImessageMessage(m) = platform_message.as_ref() else {
                      return None;
                  };
                  let UserSnapshot::ImessageUserSnapshot(sender) = &m.sent_by else { return None };
                  let UserSnapshot::ImessageUserSnapshot(agent) = m.received_by.as_ref()? else {
                      return None;
                  };
                  let SpaceSnapshot::ImessageSpaceSnapshot(space) = &m.space else { return None };
                  let text = match &m.content {
                      ImessageMessageContent::TextContent(t) if t.format == "plain" => t.text.clone(),
                      _ => return None,
                  };
                  let valid = m.created_at >= started
                      && sender.kind == "human"
                      && sender.handle == c.sender
                      && agent.kind == "agent"
                      && agent.handle == c.agent
                      && sender.id != agent.id
                      && space.kind == "direct"
                      && text.trim() == "ping";
                  valid.then(|| Incoming {
                      id: m.id.to_string(),
                      space_id: space.id.to_string(),
                      agent_id: agent.id.to_string(),
                  })
              }
              PlatformMessage::EmailMessage(platform_message) if c.platform == "email" => {
                  let EmailMessage::ReceivedEmailMessage(m) = platform_message.as_ref() else {
                      return None;
                  };
                  let UserSnapshot::EmailUserSnapshot(sender) = &m.sent_by else { return None };
                  let UserSnapshot::EmailUserSnapshot(agent) = m.received_by.as_ref()? else {
                      return None;
                  };
                  let SpaceSnapshot::EmailSpaceSnapshot(space) = &m.space else { return None };
                  let text = match &m.content {
                      EmailMessageContent::TextContent(t) if t.format == "plain" => Some(t.text.clone()),
                      EmailMessageContent::EmailGroupContent(group) => {
                          let mut plain = group.parts.iter().filter_map(|part| match part {
                              EmailGroupContentPart::TextContent(t) if t.format == "plain" => Some(t.text.clone()),
                              _ => None,
                          });
                          let first = plain.next();
                          if plain.next().is_some() { None } else { first }
                      }
                      _ => None,
                  }?;
                  let valid = m.created_at >= started
                      && sender.kind == "human"
                      && sender.handle == c.sender
                      && agent.kind == "agent"
                      && agent.handle == c.agent
                      && sender.id != agent.id
                      && text.trim() == "ping";
                  valid.then(|| Incoming {
                      id: m.id.to_string(),
                      space_id: space.id.to_string(),
                      agent_id: agent.id.to_string(),
                  })
              }
              _ => None,
          }
      }

      #[tokio::main]
      async fn main() -> Result<(), Box<dyn std::error::Error>> {
          let c = configuration()?;
          let client = PhotonClientBuilder::new()
              .credential("projectApiKey", Credential::Bearer(SecretString::from(c.key.clone())))
              .build()?;
          let platform = if c.platform == "imessage" { Platform::Imessage } else { Platform::Email };
          let started = DateTime(time::OffsetDateTime::now_utc());
          let created_since = DateTime(started.0 - time::Duration::seconds(5));
          let deadline = Instant::now() + Duration::from_secs(120);
          println!("Ready. Waiting for the configured test sender.");
          loop {
              let mut page_token: Option<String> = None;
              loop {
                  let mut params = ListMessagesParams::default()
                      .created_since(created_since)
                      .direction(MessageDirection::Received)
                      .order(SortOrder::Asc)
                      .page_size(100)
                      .platform(platform.clone());
                  if let Some(token) = page_token.take() {
                      params = params.page_token(token);
                  }
                  let page = client
                      .list_messages(c.project.clone(), Some(params))
                      .await
                      .map_err(|error| format!("{error:?}"))?
                      .into_inner();
                  for message in &page.items {
                      let Some(found) = incoming(message, &c, started) else { continue };
                      let body = SendMessageRequest {
                          space_id: found.space_id,
                          sender_id: found.agent_id,
                          parent_message_id: Some(found.id.clone()),
                          content: SendContent::SendTextContent(Box::new(SendTextContent {
                              r#type: "text".into(),
                              format: "plain".into(),
                              text: "Hello from your Photon agent!".into(),
                          })),
                          email: None,
                          telegram: None,
                      };
                      client
                          .send_message(c.project.clone(), format!("first-agent-reply:{}", found.id), &body)
                          .await
                          .map_err(|error| format!("{error:?}"))?;
                      println!("Reply accepted for asynchronous dispatch; delivery is not confirmed.");
                      return Ok(());
                  }
                  if page.next_page_token.is_none() {
                      break;
                  }
                  page_token = page.next_page_token;
              }
              if Instant::now() + Duration::from_secs(2) > deadline {
                  return Err("No matching ping found before the deadline.".into());
              }
              tokio::time::sleep(Duration::from_secs(2)).await;
          }
      }
      ```

      ```go Go expandable theme={null}
      package main

      import (
      	"context"
      	"fmt"
      	"log"
      	"os"
      	"strings"
      	"time"

      	photonapi "github.com/photon-hq/api/packages/go"
      )

      type config struct {
      	key, project, platform, agent, sender string
      }

      func configuration() config {
      	required := func(name string) string {
      		value := os.Getenv(name)
      		if value == "" {
      			log.Fatalf("Missing %s.", name)
      		}
      		return value
      	}
      	platform := required("PHOTON_PLATFORM")
      	if platform != "imessage" && platform != "email" {
      		log.Fatal("PHOTON_PLATFORM must be imessage or email.")
      	}
      	return config{
      		key: required("PHOTON_API_KEY"), project: required("PHOTON_PROJECT_ID"),
      		platform: platform, agent: required("PHOTON_AGENT_HANDLE"), sender: required("PHOTON_TEST_SENDER"),
      	}
      }

      // The reply's inputs, taken from a matching incoming message.
      type incoming struct {
      	id, spaceID, senderID string
      }

      func user(snapshot photonapi.UserSnapshot, platform string) (kind, handle, id string) {
      	switch platform {
      	case "imessage":
      		if u, err := snapshot.AsImessageUserSnapshot(); err == nil {
      			return u.Kind, u.Handle, string(u.ID)
      		}
      	case "email":
      		if u, err := snapshot.AsEmailUserSnapshot(); err == nil {
      			return u.Kind, u.Handle, string(u.ID)
      		}
      	}
      	return "", "", ""
      }

      // The client validates response shapes; these checks are the walkthrough's own
      // rules: the right conversation, sender, and text. A match returns the reply's inputs.
      func matching(item photonapi.PlatformMessage, c config, startedAt time.Time) *incoming {
      	if item.Kind() != c.platform {
      		return nil
      	}
      	var (
      		created               time.Time
      		status, text, spaceID string
      		spaceKind             string
      		sentBy, receivedBy    photonapi.UserSnapshot
      		received              bool
      		id                    string
      	)
      	switch c.platform {
      	case "imessage":
      		im, err := item.AsImessageMessage()
      		if err != nil {
      			return nil
      		}
      		m, err := im.AsReceivedImessageMessage()
      		if err != nil {
      			return nil
      		}
      		space, err := m.Space.AsImessageSpaceSnapshot()
      		if err != nil {
      			return nil
      		}
      		content, err := m.Content.AsTextContent()
      		if err != nil || content.Format != "plain" {
      			return nil
      		}
      		if m.ReceivedBy == nil {
      			return nil
      		}
      		id, created, status = string(m.ID), m.CreatedAt.Time, m.Status
      		sentBy, receivedBy = m.SentBy, *m.ReceivedBy
      		spaceID, spaceKind, text, received = string(space.ID), space.Kind, content.Text, true
      	case "email":
      		em, err := item.AsEmailMessage()
      		if err != nil {
      			return nil
      		}
      		m, err := em.AsReceivedEmailMessage()
      		if err != nil {
      			return nil
      		}
      		space, err := m.Space.AsEmailSpaceSnapshot()
      		if err != nil {
      			return nil
      		}
      		if m.ReceivedBy == nil {
      			return nil
      		}
      		if content, err := m.Content.AsTextContent(); err == nil && content.Format == "plain" {
      			text = content.Text
      		} else if group, err := m.Content.AsEmailGroupContent(); err == nil && group.Type == "group" {
      			var plain []string
      			for _, part := range group.Parts {
      				if p, err := part.AsTextContent(); err == nil && p.Type == "text" && p.Format == "plain" {
      					plain = append(plain, p.Text)
      				}
      			}
      			if len(plain) != 1 {
      				return nil
      			}
      			text = plain[0]
      		} else {
      			return nil
      		}
      		id, created, status = string(m.ID), m.CreatedAt.Time, m.Status
      		sentBy, receivedBy = m.SentBy, *m.ReceivedBy
      		spaceID, spaceKind, received = string(space.ID), space.Kind, true
      	}
      	if !received || status != "received" || created.Before(startedAt) {
      		return nil
      	}
      	senderKind, senderHandle, senderID := user(sentBy, c.platform)
      	agentKind, agentHandle, agentID := user(receivedBy, c.platform)
      	if senderKind != "human" || senderHandle != c.sender {
      		return nil
      	}
      	if agentKind != "agent" || agentHandle != c.agent || senderID == agentID {
      		return nil
      	}
      	if c.platform == "imessage" && spaceKind != "direct" {
      		return nil
      	}
      	if strings.TrimSpace(text) != "ping" {
      		return nil
      	}
      	return &incoming{id: id, spaceID: spaceID, senderID: agentID}
      }

      func main() {
      	c := configuration()
      	client := photonapi.NewClient(photonapi.WithAPIKey(c.key))
      	ctx := context.Background()
      	startedAt := time.Now().UTC()
      	deadline := time.Now().Add(120 * time.Second)
      	createdSince := startedAt.Add(-5 * time.Second).Format("2006-01-02T15:04:05.000Z")
      	platform := photonapi.Platform(c.platform)
      	fmt.Println("Ready. Waiting for the configured test sender.")
      	for {
      		params := &photonapi.ListMessagesParams{
      			ID:           c.project,
      			CreatedSince: photonapi.Ptr(createdSince),
      			Direction:    photonapi.Ptr(photonapi.MessageDirectionReceived),
      			Order:        photonapi.Ptr(photonapi.SortOrderAsc),
      			PageSize:     photonapi.Ptr(int64(100)),
      			Platform:     photonapi.Ptr(platform),
      		}
      		for {
      			page, err := client.Projects.ListMessages(ctx, params)
      			if err != nil {
      				log.Fatal(err)
      			}
      			for _, item := range page.Items {
      				found := matching(item, c, startedAt)
      				if found == nil {
      					continue
      				}
      				_, err := client.Projects.SendMessage(ctx, &photonapi.SendMessageParams{
      					ID:             c.project,
      					IdempotencyKey: "first-agent-reply:" + found.id,
      					Body: photonapi.SendMessageRequest{
      						SpaceID:         found.spaceID,
      						SenderID:        found.senderID,
      						ParentMessageID: photonapi.Ptr(found.id),
      						Content:         photonapi.SendContent{Union: photonapi.Union{Raw: []byte(`{"type":"text","format":"plain","text":"Hello from your Photon agent!"}`)}},
      					},
      				})
      				if err != nil {
      					log.Fatal(err)
      				}
      				fmt.Println("Reply accepted for asynchronous dispatch; delivery is not confirmed.")
      				return
      			}
      			if page.NextPageToken == nil {
      				break
      			}
      			params.PageToken = page.NextPageToken
      		}
      		if time.Now().Add(2 * time.Second).After(deadline) {
      			log.Fatal("No matching ping found before the deadline.")
      		}
      		time.Sleep(2 * time.Second)
      	}
      }
      ```
    </CodeGroup>

    When it prints **Ready**, continue to the next step and send your test
    message. If it exits with an API error, fix that error before sending another
    test. `429` means stop and honor the response's retry guidance; do not increase
    the polling frequency.

    <Note>
      This is a bounded connection test, not a production inbox consumer. It queries
      from five seconds before launch but ignores messages created before this run
      started. It rechecks that fixed window to account for eventual consistency.
      Keep your computer's clock synchronized. After restarting, send a fresh ping
      after `Ready`; the program does not recover older messages. A timed-out send
      may still be dispatched. If you retry that original message separately, reuse
      its original message ID and idempotency key rather than issuing a new logical
      reply.
    </Note>
  </Step>

  <Step title="Send ping and check the reply">
    Wait for **Ready** in your terminal. In Messages, start a **new direct
    conversation** with the assigned number, choose the send-from identity
    you added, and send exactly **ping**. Make sure it is an iMessage, not SMS.

    You should receive **Hello from your Photon agent!** in the same
    conversation. The program prints **Reply accepted** and exits after one
    reply. That terminal message means Photon accepted the send; seeing the
    text on your device confirms the complete round trip.

    Send a new `ping` after starting the program again to repeat the test.
    An old conversation from before the current shared assignment does not
    establish permission to reply; send a fresh message after assignment.
  </Step>
</Steps>

## If the reply does not arrive

| What you see | What to check |
| - | - |
| You cannot assign a line | Check your plan's shared mode and available seats. Use the assigned number shown for this sender, not a number copied from a screenshot. |
| The program times out | Confirm the sender's **Send & Receive** identity matches `PHOTON_TEST_SENDER`, the recipient is the assigned line, and you sent plain `ping` after **Ready**. A shared assignment supports direct conversations, not group chats. |
| HTTP `401` or `403` | Check the key's expiry, project ID, and `project:read` / `project:write` permissions. Platform setup needs its separate permissions. |
| Reply accepted, but no message on your device | Acceptance is asynchronous, not delivery. Check the conversation in the iMessage dashboard and **API Activities** for the send outcome; retain the request ID for support. |

## Turn the test into your agent

Replace the fixed reply with your application or model's response only after
this round trip works. Keep the sender checks, use the incoming conversation's
Space ID and receiving agent's User ID, and retain a stable idempotency key
for each incoming message. Do not answer your own outbound messages.

For a long-running agent, use [live events](/docs/beta/websocket) with durable
[replay cursors](/docs/beta/websocket/cursors), rather than expanding this short
polling test. The Socket.IO `reply` command is an HTTP webhook response;
it is **not** how an agent sends an iMessage.

<CardGroup cols={2}>
  <Card title="Add email" icon="envelope" href="/docs/beta/get-started/email">
    Reuse the reply pattern with an address on your domain.
  </Card>

  <Card title="Add voice" icon="phone" href="/docs/beta/get-started/voice">
    Connect a voice-capable number. Shared iMessage lines do not support calls.
  </Card>
</CardGroup>


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.