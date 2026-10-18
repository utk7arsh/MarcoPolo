> ## Documentation Index
> Fetch the complete documentation index at: https://docs.photon.codes/docs/llms.txt
> Use this file to discover all available pages before exploring further.

> ## Agent Instructions
> Use Stable documentation by default. Honor an explicit Beta request or a URL under /docs/beta/. If the requested version conflicts with the installed CLI package or API origin, clarify the target before writing integration code.
> Pages under /docs/beta/ document Beta; other product pages document Stable. Keep the CLI package, commands, API origin, and credentials within the selected version. State the documentation version in your answer.
> For MCP search, always pass version: Stable or version: Beta. Unfiltered search mixes both versions. For filesystem reads, keep Beta queries under /beta/ and exclude /beta/ from Stable queries; discover paths before reading them.
> The public docs base is https://photon.codes/docs. Convert MCP page paths to public URLs under that base, preserving /beta/ when present. Read https://photon.codes/docs/skill.md for version selection and https://photon.codes/docs/llms.txt for the version indexes.

# Set up Photon with ElevenLabs

> Connect your ElevenLabs agent to a Photon number with SIP trunking for incoming and outgoing calls.

Connect your existing ElevenLabs agent to a Photon number through SIP trunking.
Your number stays with Photon. You configure the receiving destination in
Photon and import the number into ElevenLabs.

This walkthrough configures both incoming and outgoing calls.

Incoming call: caller → Photon number → Voice profile → ElevenLabs agent.

Outgoing call: ElevenLabs agent → Photon SIP connection → recipient's phone.

This walkthrough uses **TLS** for SIP signaling. Audio encryption is a separate
setting on each platform. ElevenLabs provides a **From SIP Trunk** import option
for this connection.
[ElevenLabs SIP trunking](https://elevenlabs.io/docs/eleven-agents/phone-numbers/sip-trunking).

## Before you start

* A Photon project with an eligible **SMS number**, **WhatsApp number**, or
  **dedicated iMessage line**. Shared iMessage assignments do not support Voice.
* Permission to manage the project's Voice profiles.
* An ElevenLabs account with a published voice agent ready to use.
* A separate phone you can use to check incoming and outgoing calls.

Use your own agent, prompt, and voice. If you need an agent, follow the
[ElevenLabs quickstart](https://elevenlabs.io/docs/eleven-agents/quickstart).
You can check its behavior with **Preview** in the agent editor before
connecting your number.

User-entered names in the screenshots are examples. Choose your own labels
and use your own numbers. Copy generated credentials and assigned connection addresses
from your account; the field instructions identify values that must match.

## 1. Prepare your Photon Voice profile

### Choose a profile

A Voice profile stores the call settings for one or more numbers in your project.

| Profile | Which numbers use it | When to use it |
| - | - | - |
| **Default profile** | Numbers without an additional profile, including newly added numbers. They follow it automatically. | Use it for the settings your numbers share. A project can have one default. |
| **Additional profile** | Only the numbers you explicitly assign to it. | Use it when selected numbers need a different provider, agent, or call configuration. |

Create the default before creating an additional profile. Creating an additional
profile does not move any numbers; assign the intended numbers to it afterward.

The screenshots below show default-profile setup. If your number uses an
additional profile, apply the connection settings to that profile instead.
Changes affect new calls on every number using the edited profile. Check its
**Lines** count to see how many numbers share the settings.

### Open or create your profile

Select your Photon project and open **Voice**. Under **Lines**, find the number
you want to connect.

If your number already uses a SIP Voice profile, open it and continue to
**Understand your profile** below. If your project has no default profile,
select **Set up default**.

<img src="https://mintcdn.com/photon-6d78d87b/hMh2hcolREhyGomA/beta/images/cookbooks/voice/elevenlabs/photon-voice.webp?fit=max&auto=format&n=hMh2hcolREhyGomA&q=85&s=da336abcd583cc2f1fc35be89194ede0" alt="Photon Voice page with an eligible number under Lines and Set up default highlighted." width="3964" height="2472" data-path="beta/images/cookbooks/voice/elevenlabs/photon-voice.webp" />

Select **SIP**, then select **Create profile**.

<img src="https://mintcdn.com/photon-6d78d87b/hMh2hcolREhyGomA/beta/images/cookbooks/voice/get-started/create-default-profile.webp?fit=max&auto=format&n=hMh2hcolREhyGomA&q=85&s=8ff5fa674ac33d6903cd1711b831356b" alt="Create the default profile with SIP selected." width="3962" height="2467" data-path="beta/images/cookbooks/voice/get-started/create-default-profile.webp" />

### Understand your profile

The profile has two independent sections:

| Photon section | Purpose |
| - | - |
| **Inbound calls** | Deliver calls arriving at your Photon number to ElevenLabs. |
| **Outbound calls** | Provide the SIP credentials ElevenLabs uses to place calls through Photon. |

### Check media encryption

For this walkthrough, use **Auto** in Photon and **Allowed** in ElevenLabs.
These settings allow audio encryption to be negotiated. They do not require
every call to use encrypted audio.

If you require encrypted audio, use **Change** beside Photon's **Media
encryption**, enable **Require encrypted calls**, and select **Save**. Use
**Required** in the corresponding ElevenLabs media settings. Both directions
must support encrypted audio, and this walkthrough uses TLS for both.

## 2. Prepare Photon outbound credentials

For outgoing calls, ElevenLabs needs the outbound credential from the Photon
profile used by your number. If outbound is already enabled, use its current
connection details and the password you saved.

To enable it, open **Outbound calls**. For a new credential, select
**SHA-256 (recommended)** under **Digest algorithm**, then select
**Enable outbound**.

<img src="https://mintcdn.com/photon-6d78d87b/hMh2hcolREhyGomA/beta/images/cookbooks/voice/elevenlabs/enable-outbound.webp?fit=max&auto=format&n=hMh2hcolREhyGomA&q=85&s=f25ffa3df9a36169d63cd3513d579f54" alt="Photon Outbound calls with SHA-256 selected and Enable outbound highlighted." width="1712" height="986" data-path="beta/images/cookbooks/voice/elevenlabs/enable-outbound.webp" />

Photon opens **Save the outbound password**. Copy the password to a secure
location, then select **I saved it**. Photon displays this password once.

<img src="https://mintcdn.com/photon-6d78d87b/hMh2hcolREhyGomA/beta/images/cookbooks/voice/elevenlabs/save-outbound-password.webp?fit=max&auto=format&n=hMh2hcolREhyGomA&q=85&s=5659c47cddc5e234d4011a6820bd56eb" alt="Photon one-time password dialog with the password concealed." width="1220" height="802" data-path="beta/images/cookbooks/voice/elevenlabs/save-outbound-password.webp" />

Keep these values available for the ElevenLabs form:

| Photon value | Where you use it in ElevenLabs |
| - | - |
| Server and port under **SIP connection** | **Outbound Configuration → Address**, such as `sip.photon.codes:5061` |
| **TLS** connection | **Transport Type: TLS**; check the corresponding port in Photon |
| **Username** | **Outbound Configuration → SIP Trunk Username** |
| Saved outbound password | **Outbound Configuration → SIP Trunk Password** |

<img src="https://mintcdn.com/photon-6d78d87b/hMh2hcolREhyGomA/beta/images/cookbooks/voice/elevenlabs/photon-outbound-configured.webp?fit=max&auto=format&n=hMh2hcolREhyGomA&q=85&s=1d794b249fef317683a23c4223843cb6" alt="Photon outbound settings with SHA-256 selected and sip.photon.codes shown as the SIP connection, with TLS on port 5061." width="1740" height="1538" data-path="beta/images/cookbooks/voice/elevenlabs/photon-outbound-configured.webp" />

Copy the connection details from the same environment and profile as the
credential. **Authentication realm** can differ from the SIP server; use the
server under **SIP connection** for **Address**. The ElevenLabs form shown here
has no separate realm or port field.

These are SIP credentials, separate from your Photon API key. If you lose the
password, use **Rotate** in Photon and update every service using that
credential.

## 3. Import your Photon number into ElevenLabs

In ElevenLabs, open **Phone Numbers** under **Deploy**. Select **Import number**.

<img src="https://mintcdn.com/photon-6d78d87b/hMh2hcolREhyGomA/beta/images/cookbooks/voice/elevenlabs/import-number.webp?fit=max&auto=format&n=hMh2hcolREhyGomA&q=85&s=09a7430e79e2daf65fea05ef1622d931" alt="ElevenLabs Phone Numbers page with Import number highlighted." width="2756" height="1092" data-path="beta/images/cookbooks/voice/elevenlabs/import-number.webp" />

Choose **From SIP Trunk**.

<img src="https://mintcdn.com/photon-6d78d87b/hMh2hcolREhyGomA/beta/images/cookbooks/voice/elevenlabs/choose-sip-trunk.webp?fit=max&auto=format&n=hMh2hcolREhyGomA&q=85&s=38d4cbd5d6e6e7385a0605ad6c08e162" alt="Import number menu with From SIP Trunk highlighted." width="2836" height="1242" data-path="beta/images/cookbooks/voice/elevenlabs/choose-sip-trunk.webp" />

In **Import SIP Trunk**, enter:

| Field | What to enter |
| - | - |
| **Label** | A label of your choice that you will recognize, such as `Photon demo`. |
| **Phone number** | Your Photon number in international format, including `+` and the country code. |

### Configure incoming calls

**Inbound Configuration** controls calls that Photon sends to ElevenLabs.
Use these settings for this walkthrough:

| ElevenLabs field | Setting used in this walkthrough |
| - | - |
| **Media Encryption** | **Allowed** |
| **Allowed Numbers (Optional)** | Leave empty; the saved configuration shows **All numbers**. |
| **Allowed Source IP Addresses (Optional)** | `0.0.0.0/0`; the saved configuration shows **All addresses**. |
| **Remote Domains (Optional)** | Leave empty for the initial configuration. |
| **SIP Trunk Username** | Leave empty for this walkthrough. |
| **SIP Trunk Password** | Leave empty for this walkthrough. |

<img src="https://mintcdn.com/photon-6d78d87b/hMh2hcolREhyGomA/beta/images/cookbooks/voice/elevenlabs/inbound-configuration.webp?fit=max&auto=format&n=hMh2hcolREhyGomA&q=85&s=796804f55c1e896bc9d055ac414e53eb" alt="ElevenLabs import form showing the Photon label and number, Allowed media encryption, and optional inbound controls." width="1648" height="3080" data-path="beta/images/cookbooks/voice/elevenlabs/inbound-configuration.webp" />

This configuration has no source-IP restriction or inbound SIP password.
If your deployment requires authenticated incoming calls, define credentials
in ElevenLabs' **Inbound Configuration** and enter the same pair in Photon's
**Inbound calls** settings. That is a separate pair from Photon's generated
outbound credential.

### Configure outgoing calls

Scroll to **Outbound Configuration**. This is where ElevenLabs sends calls
through Photon.

| ElevenLabs field | What to enter |
| - | - |
| **Address** | The SIP server and TLS port from your Photon profile, such as `sip.photon.codes:5061`. Omit the `sip:` or `sips:` URI prefix. |
| **Transport Type** | **TLS** |
| **Media Encryption** | **Allowed** for this walkthrough |
| **Enabled Codecs** | Keep **G.722**, **PCMU**, and **PCMA** selected, as shown. |
| **Custom Headers (Optional)** | Leave empty for this walkthrough. |
| **SIP Trunk Username** | Your Photon profile's outbound **Username**. |
| **SIP Trunk Password** | The outbound password you saved from Photon. |

<img src="https://mintcdn.com/photon-6d78d87b/hMh2hcolREhyGomA/beta/images/cookbooks/voice/elevenlabs/outbound-configuration.webp?fit=max&auto=format&n=hMh2hcolREhyGomA&q=85&s=960b7b9aff5acd665c300d86fc1fc3d8" alt="ElevenLabs outbound settings with sip.photon.codes:5061, TLS, Allowed media encryption, the three codecs selected, and the existing SIP credential." width="1524" height="2184" data-path="beta/images/cookbooks/voice/elevenlabs/outbound-configuration.webp" />

Although ElevenLabs labels authentication optional, supply both Photon SIP
credential fields when importing the number. The screenshot shows an existing
number being edited, where leaving **SIP Trunk Password** empty keeps the saved
password. On first import, enter the password you saved from Photon.

Select **Import**. The number appears in **Phone Numbers** with
**Provider: SIP Trunk**. Open it to configure the agent.

<img src="https://mintcdn.com/photon-6d78d87b/hMh2hcolREhyGomA/beta/images/cookbooks/voice/elevenlabs/number-imported.webp?fit=max&auto=format&n=hMh2hcolREhyGomA&q=85&s=2298a762fb043a4596b339e7cb23287b" alt="Imported Photon demo number with SIP Trunk as the provider and no agent assigned yet." width="2724" height="736" data-path="beta/images/cookbooks/voice/elevenlabs/number-imported.webp" />

## 4. Assign your incoming-call agent

On the imported number's page, open the **Agent** dropdown, initially set to
**No agent**, and select the agent that should answer incoming calls.

<img src="https://mintcdn.com/photon-6d78d87b/hMh2hcolREhyGomA/beta/images/cookbooks/voice/elevenlabs/phone-setup.webp?fit=max&auto=format&n=hMh2hcolREhyGomA&q=85&s=031f5b12a8984671777af2486ebbc5f0" alt="Saved Photon number with Photon test agent assigned and Follow traffic split selected." width="1958" height="3158" data-path="beta/images/cookbooks/voice/elevenlabs/phone-setup.webp" />

The example uses **Photon test agent**. Your agent can have any name or prompt.
If **Branch** appears, **Follow traffic split** uses your agent's configured
traffic distribution. Select a specific branch if your setup calls for one.
[ElevenLabs agent versioning](https://elevenlabs.io/docs/eleven-agents/operate/versioning).

Check that the intended agent appears in the saved number settings. The agent
you choose for an outgoing call is selected separately in its call dialog.

## 5. Set the receiving destination in Photon

Return to the Photon Voice profile used by your number. Under **Inbound
calls**, select **Enable inbound** if it is not already enabled.

| Photon field | Value |
| - | - |
| **SIP address** when enabling, or **Destination** when editing | `sips:sip.rtc.elevenlabs.io:5061` |
| **Transport** | **TLS** |
| Inbound SIP credentials | Leave empty to match the ElevenLabs inbound configuration above. |

If you configured inbound authentication in ElevenLabs, enter that same
username and password here instead. On an enabled Photon profile, use **Add**
beside **No SIP credentials** to enter them.

Complete **Enable inbound** when creating the destination. For an existing
destination, edit the field and move focus out of it to save. Check that the
saved value and **TLS** remain visible.

<img src="https://mintcdn.com/photon-6d78d87b/hMh2hcolREhyGomA/beta/images/cookbooks/voice/elevenlabs/photon-inbound-configured.webp?fit=max&auto=format&n=hMh2hcolREhyGomA&q=85&s=c0e54856826fa00166d154028ccb3824" alt="Photon inbound destination set to sips:sip.rtc.elevenlabs.io:5061, with TLS selected and no SIP credentials." width="1710" height="1054" data-path="beta/images/cookbooks/voice/elevenlabs/photon-inbound-configured.webp" />

Call your Photon number from another phone. Check that your selected
ElevenLabs agent answers, hears you, and responds audibly. End the call and
check that it finishes in ElevenLabs.

## 6. Place an outgoing call

In ElevenLabs, open the imported Photon number and select **Outbound call**.

In **Outbound Call**:

1. Select the agent you want to use for this call.
2. Leave **Branch** at **Follow traffic split**, or choose the intended branch.
3. Enter the recipient's number in **Phone number**, including `+` and the
   country code. This is the phone that will receive the call.
4. Select **Send Test Call**.

<img src="https://mintcdn.com/photon-6d78d87b/hMh2hcolREhyGomA/beta/images/cookbooks/voice/elevenlabs/outbound-call-dialog.webp?fit=max&auto=format&n=hMh2hcolREhyGomA&q=85&s=9f7f05d4e3561e04d65c7358bf01cca4" alt="Outbound Call dialog with Photon test agent selected, the default branch option, and the recipient number field." width="1383" height="1105" data-path="beta/images/cookbooks/voice/elevenlabs/outbound-call-dialog.webp" />

Answer the recipient phone and check its caller ID, the agent's greeting,
audio in both directions, and call termination. A saved trunk or a request
acceptance message alone does not establish that the recipient received a call.

## Review your configuration

| Connection | Check these settings |
| - | - |
| Incoming calls | Your Photon number is imported in ElevenLabs, **Agent** and **Branch** select the intended agent, and Photon inbound points to `sips:sip.rtc.elevenlabs.io:5061` with **TLS**. |
| Outgoing calls | Photon outbound uses **SHA-256**. ElevenLabs has the profile's **SIP connection** and TLS port, such as `sip.photon.codes:5061`, with **TLS** and the matching outbound username and password. |
| Audio | Photon uses **Auto**, and both ElevenLabs media settings use **Allowed** for this walkthrough. |

Confirm that both directions use the same Photon number and Voice profile.

## Troubleshooting

| What you see | What to check |
| - | - |
| The agent works in **Preview**, but an incoming phone call fails | Confirm the imported Photon number, assigned agent and branch, the profile used by the line, and the Photon receiving destination. |
| The outgoing request is rejected | Record the exact message. Check the selected agent and branch, recipient number, and required call fields. |
| The UI shows “initiated”, but the phone does not ring | Look for the attempt in **Conversations** and inspect its outcome. Check the saved outbound hostname against the Photon profile's connection details. |
| SIP authentication fails | Check the outbound username and password, their environment, and that **SHA-256** is selected in Photon. These are separate from API keys and ElevenLabs inbound credentials. |
| The call connects with missing or one-way audio | Check the negotiated codec and both platforms' media-encryption settings. |
| TLS hangup or transfer requests fail | Check certificate validation and **Remote Domains**, following ElevenLabs' TLS guidance. |
| You lost the Photon outbound password | Rotate it in Photon and update the connected services with the replacement. |

**Remote Domains** is used for TLS certificate validation. If later requests
such as hangup fail certificate validation, add the domain covered by your
Photon SIP server's certificate. See
[ElevenLabs' TLS guidance](https://elevenlabs.io/docs/eleven-agents/phone-numbers/sip-trunking#follow-up-connections).

The imported number page includes **SIP Messages**. When enabled, it records
SIP signaling for troubleshooting; the page also points to messages in the
conversation history. Capture the attempt time, conversation ID when one
exists, and the reported SIP response before changing connection settings.

See [ElevenLabs SIP troubleshooting](https://elevenlabs.io/docs/eleven-agents/phone-numbers/sip-trunking#troubleshooting).


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.