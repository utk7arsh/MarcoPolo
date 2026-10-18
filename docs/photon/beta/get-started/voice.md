> ## Documentation Index
> Fetch the complete documentation index at: https://docs.photon.codes/docs/llms.txt
> Use this file to discover all available pages before exploring further.

> ## Agent Instructions
> Use Stable documentation by default. Honor an explicit Beta request or a URL under /docs/beta/. If the requested version conflicts with the installed CLI package or API origin, clarify the target before writing integration code.
> Pages under /docs/beta/ document Beta; other product pages document Stable. Keep the CLI package, commands, API origin, and credentials within the selected version. State the documentation version in your answer.
> For MCP search, always pass version: Stable or version: Beta. Unfiltered search mixes both versions. For filesystem reads, keep Beta queries under /beta/ and exclude /beta/ from Stable queries; discover paths before reading them.
> The public docs base is https://photon.codes/docs. Convert MCP page paths to public URLs under that base, preserving /beta/ when present. Read https://photon.codes/docs/skill.md for version selection and https://photon.codes/docs/llms.txt for the version indexes.

# Build a voice agent

> Connect a Photon number to an ElevenLabs voice agent over SIP and verify your first incoming call.

Call your Photon number and have your agent answer. Photon connects the phone
network to your agent over **SIP**; ElevenLabs runs the voice conversation.
You do not stream phone audio through the messaging HTTP endpoint.

This walkthrough starts with **incoming calls only**. You do not need to
enable outbound calling or generate an outbound SIP password to receive your
first call.

## Before you start

* A Photon project you can configure, with an eligible **SMS number** or
  **dedicated iMessage or WhatsApp number**. Shared lines cannot take calls.
* An ElevenLabs account and a voice agent you can publish.
* A separate phone to call your Photon number.

<Note>
  Number availability, subscription requirements, and call usage can incur costs.
  Review [plans and billing](/docs/beta/plans-and-billing) and the purchase confirmation
  before acquiring a number. If you already have an eligible number, reuse it.
</Note>

<Steps>
  <Step title="Prepare an agent that can hold a conversation">
    In ElevenLabs, create an agent using its
    [agent quickstart](https://elevenlabs.io/docs/eleven-agents/quickstart).
    Choose its voice, set a first message such as **Hello, I'm your test agent.
    What would you like to try?**, and give it a small job, such as answering
    questions about a fictional coffee shop.

    Use **Preview** in the agent editor. Ask a question, hear its response,
    and publish the version you want callers to reach. Fix the agent here
    before troubleshooting the phone connection.
  </Step>

  <Step title="Find your Photon number and its Voice profile">
    Select your Photon project and open **Voice**. Find your number under
    **Lines**. If it is missing, confirm it is voice-capable; a shared iMessage
    assignment is not an eligible number.

    If there is no default profile, select **Set up default**, choose **SIP**,
    and select **Create profile**. If your number already uses a profile, open
    that profile instead.

    <Frame caption="Create the default SIP profile before adding other profiles. Dashboard preview with sample data.">
      <img src="https://mintcdn.com/photon-6d78d87b/ihPr8z21mxGiVObP/beta/images/get-started/voice-create-profile.png?fit=max&auto=format&n=ihPr8z21mxGiVObP&q=85&s=dcb4a82a93f232297a5cc2f788635a98" alt="Photon Create the default profile form with SIP selected and Create profile available." width="720" height="292" data-path="beta/images/get-started/voice-create-profile.png" />
    </Frame>

    The default applies to numbers without an additional profile. An
    additional profile affects only numbers assigned to it. Check the number's
    assignment and the profile's **Lines** count before editing: the change
    affects new calls on every line using that profile.
  </Step>

  <Step title="Import the number into ElevenLabs">
    In ElevenLabs, open **Deploy → Phone Numbers**, select **Import number**,
    then **From SIP Trunk**. Enter a label you recognize and your Photon
    number in international format, including `+` and the country code.

    Configure **Inbound Configuration** for the calls arriving from Photon.
    Use **Allowed** for media encryption to match Photon's **Auto** setting.
    If you enable inbound SIP authentication in ElevenLabs, save that
    username and password: you must enter the same pair in Photon next.

    These are **ElevenLabs inbound credentials**, not a Photon API key or a
    Photon outbound SIP password. Leave outbound configuration disabled for
    this incoming-only test.

    Save the imported number, then select your published agent in its
    **Agent** dropdown. If **Branch** appears, choose the version or traffic
    split you intend callers to reach. A number with **No agent** will not
    run your conversation.

    For the provider's current import fields and security options, see
    [ElevenLabs SIP trunking](https://elevenlabs.io/docs/eleven-agents/phone-numbers/sip-trunking).
  </Step>

  <Step title="Point Photon at the agent's SIP destination">
    Return to the Photon Voice profile used by the number. Under **Inbound
    calls**, select **Enable inbound** if needed. Configure:

    | Setting | Value for this ElevenLabs connection |
    | - | - |
    | **SIP address** when enabling, or **Destination** when editing | `sips:sip.rtc.elevenlabs.io:5061` |
    | **Transport** | **TLS** |
    | SIP credentials | The inbound username and password configured in ElevenLabs, if required there. Otherwise leave them unset. |
    | **Media encryption** | **Auto**, paired with **Allowed** in ElevenLabs for this initial test. |

    <Frame caption="The ElevenLabs receiving destination with TLS selected. Dashboard preview; a saved address alone does not verify call delivery.">
      <img src="https://mintcdn.com/photon-6d78d87b/ihPr8z21mxGiVObP/beta/images/get-started/voice-inbound-destination.png?fit=max&auto=format&n=ihPr8z21mxGiVObP&q=85&s=efd9023809c3a7d9f0351c0e09ef7c41" alt="Photon Inbound calls destination set to sips:sip.rtc.elevenlabs.io:5061 with TLS selected." width="720" height="222" data-path="beta/images/get-started/voice-inbound-destination.png" />
    </Frame>

    Complete **Enable inbound** for a new configuration. For an existing
    destination, edit the field and move focus out of it to save. Confirm the
    saved address and **TLS** remain visible. If required by the provider,
    add its inbound credentials using **Add** or **Replace** beside the
    credential row.

    TLS protects SIP signaling. Requiring encrypted audio is a separate
    policy; if you require it, enable **Require encrypted calls** in Photon
    and **Required** media encryption in ElevenLabs, with matching support in
    both directions.
  </Step>

  <Step title="Call the agent from another phone">
    Dial your Photon number. Listen for the greeting, ask your test question,
    and confirm the agent hears you and responds audibly. End the call.

    In Photon, check **Voice → Recent calls** for the attempt and its final
    status. In ElevenLabs, check the conversation for the selected agent.
    A saved SIP destination is not proof of a working call: verify audio in
    **both directions** and that the call ends normally.
  </Step>
</Steps>

## Read the configuration from your application

The voice conversation runs in the provider, but you can inspect its Photon
routing with any published API client. Complete
[project setup](/docs/beta/get-started/project) with `platforms:read`, copy the
**Profile id** from this Voice profile, and set:

```sh theme={null}
export PHOTON_VOICE_PROFILE_ID="pho_vpf_REPLACE_WITH_YOUR_PROFILE_ID"
```

Save the example as `voice.ts`, `voice.py`, `src/main.rs`, or `main.go` in the
directory you prepared in project setup. These are **API-client calls**, not
audio streaming or a replacement for your provider's agent code.

<CodeGroup>
  ```typescript TypeScript theme={null}
  import { Photon } from "@photon-ai/api";

  const { PHOTON_API_KEY, PHOTON_PROJECT_ID, PHOTON_VOICE_PROFILE_ID } = process.env;
  if (!PHOTON_API_KEY || !PHOTON_PROJECT_ID || !PHOTON_VOICE_PROFILE_ID) {
    throw new Error("Set PHOTON_API_KEY, PHOTON_PROJECT_ID, and PHOTON_VOICE_PROFILE_ID");
  }

  const photon = new Photon({
    headers: { Authorization: `Bearer ${PHOTON_API_KEY}` },
  });

  try {
    const profile = await photon.projects.platforms.getVoiceProfile({
      path: { id: PHOTON_PROJECT_ID, profileId: PHOTON_VOICE_PROFILE_ID },
    });
    console.log(profile.configuration.inbound?.destinationUri ?? "Inbound is not enabled");
  } catch {
    console.error("Could not read the Voice profile");
    process.exitCode = 1;
  }
  ```

  ```python Python theme={null}
  import os

  from photon_api import Photon, PhotonError
  from photon_api.rpc_generated import GetVoiceProfileInput

  try:
      with Photon(headers={"Authorization": f"Bearer {os.environ['PHOTON_API_KEY']}"}) as photon:
          profile = photon.projects.platforms.get_voice_profile(
              GetVoiceProfileInput.model_validate({
                  "path": {
                      "id": os.environ["PHOTON_PROJECT_ID"],
                      "profileId": os.environ["PHOTON_VOICE_PROFILE_ID"],
                  }
              })
          )
          inbound = profile.configuration.inbound
          print(inbound.destinationUri if inbound is not None else "Inbound is not enabled")
  except PhotonError:
      raise SystemExit("Could not read the Voice profile") from None
  ```

  ```rust Rust theme={null}
  use photon_ai_api::{Credential, PhotonClientBuilder, SecretString};

  #[tokio::main]
  async fn main() -> Result<(), Box<dyn std::error::Error>> {
      let client = PhotonClientBuilder::new()
          .credential(
              "projectApiKey",
              Credential::Bearer(SecretString::from(std::env::var("PHOTON_API_KEY")?)),
          )
          .build()?;
      let response = client
          .get_voice_profile(
              std::env::var("PHOTON_PROJECT_ID")?,
              std::env::var("PHOTON_VOICE_PROFILE_ID")?,
          )
          .await
          .map_err(|_| "Could not read the Voice profile")?;
      match &response.inner().configuration.inbound {
          Some(inbound) => println!("{}", inbound.destination_uri),
          None => println!("Inbound is not enabled"),
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

  func required(name string) string {
      value := os.Getenv(name)
      if value == "" {
          log.Fatalf("Set %s", name)
      }
      return value
  }

  func main() {
      client := photonapi.NewClient(photonapi.WithAPIKey(required("PHOTON_API_KEY")))
      profile, err := client.Projects.Platforms.GetVoiceProfile(
          context.Background(), &photonapi.GetVoiceProfileParams{
              ID: required("PHOTON_PROJECT_ID"),
              ProfileID: required("PHOTON_VOICE_PROFILE_ID"),
          },
      )
      if err != nil {
          log.Fatal("Could not read the Voice profile")
      }
      if profile.Configuration.Inbound == nil {
          fmt.Println("Inbound is not enabled")
          return
      }
      fmt.Println(profile.Configuration.Inbound.DestinationURI)
  }
  ```
</CodeGroup>

<CodeGroup>
  ```sh TypeScript theme={null}
  node voice.ts
  ```

  ```sh Python theme={null}
  python voice.py
  ```

  ```sh Rust theme={null}
  cargo run --bin photon-first-agent
  ```

  ```sh Go theme={null}
  go run main.go
  ```
</CodeGroup>

The returned destination confirms what is saved in Photon, not whether the
remote agent answered. Keep the phone-call check above as your success test.

## If the call does not work

| What you see | What to check |
| - | - |
| Your number is missing from **Lines** | Confirm it is an SMS or dedicated messaging number with voice support, in the selected project. Shared lines do not support Voice. |
| The agent works in Preview but does not answer calls | Check the imported number, assigned agent and branch, line-to-profile assignment, and Photon's saved inbound destination. |
| SIP authentication fails | Use the provider's **inbound** credential pair in Photon. A Photon API key or outbound SIP credential cannot replace it. |
| The call connects with no audio or one-way audio | Compare the platforms' media-encryption settings and supported codecs. TLS signaling and encrypted audio are separate settings. |
| Calls reach the wrong agent | Check whether this line follows the default or an additional profile, and which agent is assigned to the imported number in ElevenLabs. |

Keep the attempt time, Photon call ID, provider conversation ID, and any SIP
error when asking for help. Do not include passwords or API keys.

## Keep building

<CardGroup cols={2}>
  <Card title="Add outgoing ElevenLabs calls" icon="phone-arrow-up-right" href="/docs/beta/cookbooks/voice/elevenlabs">
    Configure the separate Photon outbound credential and test outgoing calls.
  </Card>

  <Card title="Use another voice provider" icon="headset" href="/docs/beta/cookbooks">
    Follow the LiveKit, Retell, or Twilio walkthrough for your agent stack.
  </Card>

  <Card title="Add iMessage" icon="comment" href="/docs/beta/get-started/imessage">
    Give your agent a text conversation alongside phone calls.
  </Card>

  <Card title="Add email" icon="envelope" href="/docs/beta/get-started/email">
    Receive and reply to email on your own domain.
  </Card>
</CardGroup>


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.