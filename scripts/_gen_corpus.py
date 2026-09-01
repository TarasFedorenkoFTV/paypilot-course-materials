"""One-off: write the expanded Verta knowledge-base corpus.

The corpus must be large enough that retrieval is a real search problem
(ТЗ §5.4 asks for roughly 100–150 fragments across the two indexes).
Kept as a script so the corpus is reproducible rather than hand-edited.
"""
import pathlib

D = pathlib.Path(__file__).resolve().parent.parent / "app" / "rag" / "corpus"

DOCS = {}

DOCS["disputes-process.md"] = """# Dispute handling process

## Raising a dispute
A dispute is raised against a single settled transaction. The customer supplies
the transaction reference and a reason code. The agent verifies eligibility
before the case is opened; an ineligible request is refused with the failing
condition named, except where confidentiality rules apply.

## Case states
A dispute moves through: open, under_review, provisional_credit,
resolved_upheld, resolved_declined. Only open and under_review cases can be
withdrawn by the customer.

## Provisional credit
Where the disputed amount exceeds EUR 50 and the reason code is a fraud code, a
provisional credit is applied within two business days. Provisional credit is
reversed if the dispute is later declined.

## Review timelines
The review target is 10 business days for card reason codes and 20 business
days for transfer reason codes. Complex cases involving a foreign acquirer may
run to 45 calendar days; the customer is notified when that happens.

## Evidence requirements
The customer may be asked for supporting evidence: an order confirmation, a
delivery record, correspondence with the merchant. Failure to supply requested
evidence within 7 calendar days results in the case being declined.

## Withdrawing a dispute
A customer may withdraw a dispute at any time before resolution. Withdrawal is
final; the same transaction cannot be disputed again under the same reason code.
"""

DOCS["accounts.md"] = """# Accounts and balances

## Account types
Each Verta customer may hold one current account per supported currency. The
first account opened is the primary account and carries the customer tier.

## Balance definitions
The available balance is the settled balance minus holds from authorised but
unsettled card transactions. The ledger balance excludes those holds. Balances
quoted in support conversations are available balances.

## Authorisation holds
A card authorisation places a hold for up to 7 calendar days. If the merchant
does not settle within that window the hold is released automatically.

## Statements
Monthly statements are generated on the first calendar day of each month and
cover the previous calendar month. Statements are delivered only to the email
address registered to the account holder.

## Closing an account
An account with an open dispute or a non-zero hold cannot be closed. Closure
requests are handled by a human agent.
"""

DOCS["transfers.md"] = """# Transfers

## Transfer types
Internal transfers move funds between Verta accounts and settle instantly.
SEPA transfers reach euro-area banks within one business day. SWIFT transfers
are used for other destinations and settle in one to five business days. Card
payments are outgoing payments to a merchant.

## Cut-off times
SEPA transfers submitted after 16:00 CET are processed the next business day.
SWIFT transfers submitted after 14:00 CET are processed the next business day.
Internal transfers have no cut-off.

## References
Every outgoing transfer carries a reference visible on both sides. References
are limited to 140 characters.

## Failed transfers
A transfer rejected by the beneficiary bank is returned within five business
days. Fees already charged on a returned SWIFT transfer are not refunded.

## Recalls
A customer may request a recall of a sent transfer. Recalls are best-effort:
the beneficiary bank is not obliged to return the funds. Recall requests are
handled by a human agent.
"""

DOCS["fx-operations.md"] = """# Currency conversion operations

## When a conversion happens
A conversion happens when the payment currency differs from the currency of the
account being debited. The conversion is applied at settlement, not at
authorisation.

## Rate validity
A quoted rate is indicative and valid for the conversation only. The rate
applied at settlement is the mid-market rate at settlement time plus the tier
spread.

## Allowance accounting
The free monthly conversion allowance is counted in EUR equivalent and resets on
the first calendar day of each month. Allowance consumption is recorded at
settlement. A conversion that would cross the allowance boundary has the tier
spread applied to the entire conversion, not only to the portion above the
boundary.

## Weekend and holiday rates
Mid-market rates are not refreshed on weekends or on target closing days. A
conversion initiated on such a day settles at the next available rate.

## Reversals
If a converted payment is reversed, the reversal is converted back at the rate
in force at reversal time. The customer may therefore receive slightly more or
less than the original amount.
"""

DOCS["limits-operations.md"] = """# Limit operations

## What counts towards a limit
Only settled outgoing transfers count towards the daily and monthly transfer
limits. Card payments count. Incoming transfers, internal transfers between the
own accounts of one customer, and fees charged by Verta do not count.

## Temporary limit increases
A customer may request a temporary increase for a single transfer. Increases
are approved by a human agent and expire after 24 hours.

## Limit refusal
A transfer that exceeds either the daily or the monthly remainder is refused in
full; it is never partially executed. The refusal names which remainder was
exceeded.

## Tier changes
A tier change takes effect on the first calendar day of the following month.
Limits and spreads of the previous tier apply until then.

## Window definition
Limits are tracked on calendar days, not business days. The daily window runs
from 00:00 to 23:59 CET.
"""

DOCS["security-policy.md"] = """# Customer security policy

## Identity verification
Before discussing account details the agent confirms the customer identifier.
Verta never asks a customer for a full card number, a PIN, or a one-time
passcode in a support conversation.

## Card blocking
A customer may block a card immediately. Blocking is reversible for 30 days;
after that a replacement card must be ordered.

## Suspicious activity
A customer reporting suspicious activity is asked to block the affected card
first; the disputed transactions are then reviewed.

## Data disclosure
Account information is disclosed only to the account holder. Third-party
requests, including from family members, are refused and escalated.

## Phishing
Verta communicates only through the app, the registered email address and the
in-app chat. Customers reporting a suspicious message are advised not to click
links and to forward the message to the security team.
"""

DOCS["escalation-policy.md"] = """# Escalation policy

## Mandatory escalation triggers
The agent must escalate to a human agent when: suspected fraud is reported on a
settled transaction above EUR 10,000; the customer explicitly asks for a human;
the request needs an action the agent has no tool for; a dispute is blocked by a
customer-level restriction; the customer disputes a figure the agent quoted.

## What escalation does
Escalation queues the conversation for a human agent and records the reason.
The customer is told a human will follow up; the internal reason is not read
out to them.

## Escalation is additive
Escalation never replaces answering. The agent answers what it can answer and
escalates the remainder.

## Out-of-hours
Escalations raised outside 08:00-20:00 CET are queued for the next working day.
The customer is told the expected response window.
"""

DOCS["glossary.md"] = """# Glossary

## Mid-market rate
The midpoint between the buy and sell price of a currency pair on the wholesale
market. Verta quotes conversions relative to this rate.

## Spread
The percentage Verta adds to the mid-market rate on a conversion. The spread
depends on the customer tier.

## Chargeback window
The number of days, counted from the transaction date, during which a dispute
may be raised under a given reason code.

## Reason code
The classification of why a transaction is disputed. The reason code determines
the chargeback window and the evidence required.

## Settled transaction
A transaction the merchant has claimed and Verta has debited. Only settled
transactions can be disputed.

## Tier
The tariff level of a customer: Tier 1, Tier 2 or Tier 3. The tier determines
spreads, allowances and transfer limits.

## Provisional credit
A temporary refund applied while a dispute is reviewed; reversed if the dispute
is declined.
"""

DOCS["fees-detail.md"] = """# Fee details

## How the SWIFT fee is composed
A SWIFT transfer carries a flat fee plus a percentage of the EUR equivalent of
the amount sent. Correspondent bank charges deducted en route are outside the
control of Verta and are not refunded.

## Card payment fee
Card payments carry a percentage fee on the EUR equivalent. No flat fee
applies.

## When fees are charged
Fees are charged at settlement, on the same account as the transaction, and
appear as a separate ledger entry.

## Fee refunds
A fee is refunded only when the underlying transaction is reversed because of a
Verta error. Fees on customer-initiated reversals are not refunded.

## Fees and limits
Fees charged by Verta do not count towards the transfer limits of the customer.
"""

DOCS["reason-codes.md"] = """# Reason code guide

## fraud_card_not_present
Used when a card was used remotely without the authorisation of the cardholder.
The longest chargeback window applies. Evidence: confirmation that the card was
in the possession of the customer.

## goods_not_received
Used when a purchase was paid for but never delivered. Evidence: the expected
delivery date and any merchant correspondence.

## duplicate_charge
Used when the same purchase was debited more than once. Evidence: references of
both transactions. This code carries the shortest window of the purchase codes.

## service_not_rendered
Used when a paid-for service was not provided. Evidence: the booking or
contract and the date the service was due.

## unauthorized_debit
Used for a direct debit the customer never mandated. This code carries the
shortest window overall.

## Choosing a code
The reason code must match what actually happened. A dispute filed under the
wrong code is declined and must be refiled, which may push it past its window.
"""

DOCS["onboarding.md"] = """# Onboarding and tiers

## How a customer gets a tier
New customers start on Tier 1. Tier 2 is granted when the average monthly
inflow exceeds EUR 3,000 over three consecutive months. Tier 3 is granted on
application and is reviewed annually.

## Tier benefits
A higher tier lowers the FX spread, raises the free monthly conversion
allowance and raises both transfer limits.

## Downgrades
A customer who no longer meets the criteria is downgraded at the next annual
review, never mid-month.

## Verification
Onboarding requires an identity document and proof of address. Accounts are
usable for incoming transfers before verification completes, but outgoing
transfers are blocked until it does.
"""

DOCS["complaints.md"] = """# Complaints

## Difference from a dispute
A dispute concerns a specific transaction. A complaint concerns the service
itself: a delay, an error, or the conduct of an agent. The two follow separate
processes.

## Raising a complaint
Complaints are raised in the app or by email and are always handled by a human
agent. The support agent records the complaint and escalates it.

## Acknowledgement and resolution
A complaint is acknowledged within one business day and resolved within 15
business days. Complex complaints may take up to 35 business days, with the
customer informed of the delay.

## Escalation to the regulator
If a customer is not satisfied with the final response they may refer the
complaint to the national financial ombudsman within six months.
"""

for name, text in DOCS.items():
    (D / name).write_text(text, encoding="utf-8")
print("wrote", len(DOCS), "docs; corpus now has",
      len(list(D.glob("*.md"))), "files")
