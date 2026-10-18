> ## Documentation Index
> Fetch the complete documentation index at: https://docs.photon.codes/docs/llms.txt
> Use this file to discover all available pages before exploring further.

> ## Agent Instructions
> Use Stable documentation by default. Honor an explicit Beta request or a URL under /docs/beta/. If the requested version conflicts with the installed CLI package or API origin, clarify the target before writing integration code.
> Pages under /docs/beta/ document Beta; other product pages document Stable. Keep the CLI package, commands, API origin, and credentials within the selected version. State the documentation version in your answer.
> For MCP search, always pass version: Stable or version: Beta. Unfiltered search mixes both versions. For filesystem reads, keep Beta queries under /beta/ and exclude /beta/ from Stable queries; discover paths before reading them.
> The public docs base is https://photon.codes/docs. Convert MCP page paths to public URLs under that base, preserving /beta/ when present. Read https://photon.codes/docs/skill.md for version selection and https://photon.codes/docs/llms.txt for the version indexes.

# Billing

> Understand billing periods, usage charges, resource pricing, and plan changes.

Choose a [plan](/docs/beta/plans-and-billing) for each project. Your bill combines your
plan, paid usage, and any optional resources. Organization services, such as SSO
and 10DLC registration, are billed separately from project plans. For payments,
credit, and overdue invoices, see [Invoices and payments](/docs/beta/invoices-and-payments).

## When you're billed

Subscriptions renew monthly on the day they started, with days starting at
midnight Pacific Time. If a month has no such day, the subscription renews on the
month's last day. Changing plans keeps the original renewal day. Subscriptions
with the same payer and renewal day share one invoice.

* **Free** has no base fee. Paid usage and resources still incur charges.
* **Pro** costs \$25 per month, paid in advance. An upgrade from Free is prorated
  for the days remaining until your next renewal; a new Pro subscription starts
  with a full billing period.
* **Business** has a \$250 monthly minimum. Project usage and resource charges
  count toward it, and any shortfall is billed at the end of the period. The
  first partial period's minimum is prorated by days.

Paid usage is also invoiced during the billing period each time it reaches **\$20
on Free or Pro**, or **\$100 on Business**. Any remaining usage is billed at the end
of the period. These thresholds determine invoice timing; they are not extra fees.

<Note>
  Free means no monthly base fee. Add a payment method before you buy resources or
  turn on paid features. See [Payment method](/docs/beta/invoices-and-payments#payment-method).
</Note>

## How usage is counted

<AccordionGroup>
  <Accordion title="SMS and MMS" icon="comment-sms">
    SMS is billed per message part, so a message split into multiple parts counts
    more than once. MMS is counted per recipient for outbound messages and per
    message for inbound messages, regardless of the number of attachments.

    SMS and MMS carrier fees are passed through at cost, in addition to message
    rates. Included SMS parts do not cover carrier fees.
  </Accordion>

  <Accordion title="Voice" icon="phone">
    Each answered call is rounded up to the next minute. Unanswered calls are
    free. US/Canada calls use your plan's included minutes first, then its
    [usage rate](/docs/beta/plans-and-billing#usage-rates).

    International voice costs **\$0.065 per minute** for Australia, Brazil, France,
    Germany, India, Indonesia, Japan, Mexico, South Korea, and the United Kingdom.
    Calls to Argentina, Italy, Russia, Saudi Arabia, South Africa, and Turkey cost
    **\$0.34 per minute**. These international rates are the same on all three plans
    and are separate from the US/Canada allowance.
  </Accordion>

  <Accordion title="Email" icon="envelope">
    Sent and received emails share one usage allowance per project. Each outbound
    recipient in To, Cc, or Bcc counts as one email; each inbound message counts
    as one email.

    Outbound email is billable once accepted for delivery. Bounced messages are
    not refunded.
  </Accordion>
</AccordionGroup>

## Optional resources and services

All prices are in USD.

| Resource or service | Price | Availability |
| - | - | - |
| Dedicated iMessage line | \$250 / line / month | Business |
| Dedicated WhatsApp line | \$250 / line / month | Business |
| Local US phone number | \$2 / number / month | All plans |
| SSO | \$220 / organization / month | Organization service |
| 10DLC campaign | \$15 / campaign / month | From campaign activation |
| 10DLC campaign registration | \$20 / submission | Includes resubmissions |

Dedicated lines and SSO are paid in advance and prorated for the rest of the
billing period. Local US numbers and 10DLC campaigns are paid in advance without
proration. A number purchased shortly before renewal is charged at purchase and
again on the renewal day.

Releasing a dedicated line or canceling SSO returns the unused days as
[credit](/docs/beta/invoices-and-payments#credit). Releasing a number or ending a
campaign does not. Campaign registration fees are non-refundable.

Organization charges do not count toward a project's Business minimum. Credit
from a released line is subtracted from the charges that count toward it.

## Change plans

Upgrades take effect once their payment succeeds. Downgrades take effect at the
end of the current billing period. Dedicated lines keep working until a downgrade
from Business takes effect, and are then released automatically. While a downgrade
is scheduled, you cannot request new dedicated lines, and you can keep your
current plan from the Billing page.

Canceling a paid plan moves the project to Free at the end of the period. Local US
numbers stay with the project and continue at \$2 per month.

When upgrading from Pro to Business, your invoice includes Business charges and
Pro usage so far, with a credit for unused prepaid Pro time. Any remaining credit
applies to later invoices.

## Delete a project or organization

Deleting a project releases its resources and issues a final invoice for usage
not yet billed. The unused days of dedicated lines and unused prepaid Pro time
return as credit. On Business, the minimum commitment is prorated to the deletion
date.

To delete an organization, first delete its projects and pay any unpaid invoices.
Remaining credit is not paid out.

## Billing support

For help with invoices, payment methods, plan changes, or larger deployments,
email [support@photon.codes](mailto:support@photon.codes). Our team operates 24/7.
For an urgent escalation, contact Ryan, Photon's cofounder, at
[ryan@photon.codes](mailto:ryan@photon.codes).


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.