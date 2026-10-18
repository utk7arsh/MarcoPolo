> ## Documentation Index
> Fetch the complete documentation index at: https://docs.photon.codes/docs/llms.txt
> Use this file to discover all available pages before exploring further.

> ## Agent Instructions
> Use Stable documentation by default. Honor an explicit Beta request or a URL under /docs/beta/. If the requested version conflicts with the installed CLI package or API origin, clarify the target before writing integration code.
> Pages under /docs/beta/ document Beta; other product pages document Stable. Keep the CLI package, commands, API origin, and credentials within the selected version. State the documentation version in your answer.
> For MCP search, always pass version: Stable or version: Beta. Unfiltered search mixes both versions. For filesystem reads, keep Beta queries under /beta/ and exclude /beta/ from Stable queries; discover paths before reading them.
> The public docs base is https://photon.codes/docs. Convert MCP page paths to public URLs under that base, preserving /beta/ when present. Read https://photon.codes/docs/skill.md for version selection and https://photon.codes/docs/llms.txt for the version indexes.

# Plans

> Start free, grow with Pro, or scale on Business with dedicated infrastructure support.

Photon offers Free, Pro, and Business plans for your projects. Each plan uses the
same API, so you can grow your usage without rebuilding your integration.

All prices below are in USD. Usage and optional resources are billed separately
from the plan's base fee.

<CardGroup cols={3}>
  <Card title="Free" icon="seedling" href="#free">
    **\$0 base fee**

    Get your agent up and running.
  </Card>

  <Card title="Pro" icon="users" href="#pro">
    **\$25 / month**

    Build and grow with a small team.
  </Card>

  <Card title="Business" icon="building" href="#business">
    **\$250 monthly minimum**

    Scale with dedicated infrastructure support.
  </Card>
</CardGroup>

## Free

Free gives you what you need to start operating your agent, with no monthly base
fee. It includes up to **25 shared iMessage assignments**, **25 shared WhatsApp
assignments**, and **one email domain** per project. Paid usage and resources are
charged at the rates below.

## Pro

Pro is designed for small teams. For **\$25 per month**, each project gets up to
**100 shared iMessage assignments**, **100 shared WhatsApp assignments**, **five
email domains**, and included SMS, voice, and email usage each billing period.

## Business

Business is designed for teams operating at scale, with dedicated infrastructure
support, higher included usage, and unlimited email domains. Purchase dedicated
iMessage and WhatsApp lines for **\$250 per line per month**, with a standard limit
of **50 lines of each per project**. Contact us if you need more capacity.

Business has a **\$250 monthly minimum** and no separate base fee. Its project
usage and resource charges count toward that minimum. For example, one dedicated
iMessage line at \$250 per month meets the minimum; additional paid usage still
applies. Business uses dedicated lines rather than shared assignments.

## Compare what's included

Allowances reset each billing period. Limits and included usage apply per project.

| | Free | Pro | Business |
| - | - | - | - |
| Monthly base fee | \$0 | \$25 | \$0 |
| Monthly minimum | None | None | \$250 |
| Shared iMessage assignments | 25 | 100 | Dedicated lines |
| Shared WhatsApp assignments | 25 | 100 | Dedicated lines |
| Email domains | 1 | 5 | Unlimited |
| Included SMS parts, US/Canada | None | 500 | 2,000 |
| Included voice minutes, US/Canada | None | 300 | 1,200 |
| Included emails | None | 50,000 | 200,000 |
| Dedicated iMessage lines | Not available | Not available | \$250 / line / month |
| Dedicated WhatsApp lines | Not available | Not available | \$250 / line / month |

An assignment connects one user to your agent through a shared line.
Dedicated lines give your project its own capacity on Business.

## Usage rates

These rates apply after any included allowance. SMS, MMS, and US/Canada voice
rates are the same for inbound and outbound traffic.

| Usage | Free | Pro | Business |
| - | - | - | - |
| SMS, per part, US/Canada | \$0.01 | \$0.008 | \$0.007 |
| MMS, per message, US/Canada | \$0.02 | \$0.02 | \$0.018 |
| Voice, per minute, US/Canada | \$0.013 | \$0.012 | \$0.01 |
| Email | \$0.001 | \$0.0009 | \$0.0008 |
| SMS and MMS carrier fees | At cost | At cost | At cost |

Photon does not charge per-message usage fees for iMessage, WhatsApp, or Telegram
sends. Resource charges, such as dedicated lines, still apply.
See [Billing](/docs/beta/billing) for usage counting, international voice rates, and
optional resource charges.

## Find the right fit

<CardGroup cols={2}>
  <Card title="Start building" icon="bolt" href="/docs/beta/index">
    Connect your application and make your first request.
  </Card>

  <Card title="Talk to our team" icon="comments" href="mailto:support@photon.codes">
    Get help choosing a plan or planning a larger deployment.
  </Card>
</CardGroup>


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.