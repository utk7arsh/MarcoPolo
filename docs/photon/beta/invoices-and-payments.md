> ## Documentation Index
> Fetch the complete documentation index at: https://docs.photon.codes/docs/llms.txt
> Use this file to discover all available pages before exploring further.

> ## Agent Instructions
> Use Stable documentation by default. Honor an explicit Beta request or a URL under /docs/beta/. If the requested version conflicts with the installed CLI package or API origin, clarify the target before writing integration code.
> Pages under /docs/beta/ document Beta; other product pages document Stable. Keep the CLI package, commands, API origin, and credentials within the selected version. State the documentation version in your answer.
> For MCP search, always pass version: Stable or version: Beta. Unfiltered search mixes both versions. For filesystem reads, keep Beta queries under /beta/ and exclude /beta/ from Stable queries; discover paths before reading them.
> The public docs base is https://photon.codes/docs. Convert MCP page paths to public URLs under that base, preserving /beta/ when present. Read https://photon.codes/docs/skill.md for version selection and https://photon.codes/docs/llms.txt for the version indexes.

# Invoices and payments

> Understand payment methods, failed payments, credit, and the charges on your invoice.

Your organization pays the invoices for all of its projects and organization
services. Invoices are charged to the organization's payment method when they
are issued, after any credit is applied.

## Payment method

Add a card on the organization's Billing page before you upgrade a project, buy
a phone number or dedicated line, subscribe to SSO, add an email domain, turn on
outbound calls, connect WhatsApp Business, or register for 10DLC. Without one,
these requests return `402` `ENTITLEMENT_REQUIRED` with reason `card_required`.

## Failed payments

Purchases and upgrades take effect once their payment succeeds. If the payment
fails, the purchase is canceled and the project stays on its current plan.
Update your payment method and try again.

Invoices below \$0.50 are not charged on their own. They are added to your next
charge.

A renewal or usage invoice that is not paid becomes overdue. Retry the payment
from the invoice on the Billing page.

* **7 days overdue:** you cannot buy resources, turn on outbound calls, or
  register for 10DLC. These requests return `402` `ENTITLEMENT_REQUIRED` with
  reason `billing_restricted`.
* **14 days overdue:** SMS, MMS, email, and outbound calls are suspended until
  the invoice is paid. Inbound traffic, iMessage, WhatsApp, and Telegram are not
  affected.

Sending can be suspended earlier if a large amount of usage is unpaid, or while
a payment is disputed with your bank.

## Credit

Credit pays your invoices before your card is charged. It is applied
automatically and does not expire.

Your organization receives credit from:

* A **\$100 welcome credit** for the first organization on a new account.
* The unused days of a released dedicated line or canceled SSO subscription.
* Unused prepaid Pro time when you upgrade to Business or delete a project.

Credit does not apply to 10DLC campaign registration fees. It is not refunded to
your card or paid out. To see your balance and its history, open the Billing page
and choose **View activity** next to **Credit**.

## What's on your invoice

| Line | Charge |
| - | - |
| Messaging Free, Pro, or Business | The plan's base fee |
| SMS Message Parts, MMS Messages, Voice Minutes, Emails | Usage beyond your plan's included amounts |
| SMS / MMS Carrier Fees | Carrier fees, passed through at cost |
| iMessage Dedicated Lines, WhatsApp Dedicated Lines, Local US Numbers | Project resources |
| SSO, 10DLC Campaigns | Organization services |
| 10DLC Campaign Registrations | Registration fees, billed on a separate invoice |
| Minimum Commitment | The Business minimum shortfall |

Fees paid in advance cover the period that is starting. Usage covers the period
that just ended.

## Billing support

For help with invoices or payments, email
[support@photon.codes](mailto:support@photon.codes). Our team operates 24/7.


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.