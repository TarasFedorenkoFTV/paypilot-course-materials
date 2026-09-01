"""Second corpus batch — brings kb_clean to roughly 100 fragments (ТЗ §5.4)."""
import pathlib

D = pathlib.Path(__file__).resolve().parent.parent / "app" / "rag" / "corpus"

DOCS = {}

DOCS["cards.md"] = """# Cards

## Card types
Every account may have one physical and up to three virtual debit cards.
Virtual cards can be created and destroyed at any time.

## Authorisation and settlement
A card payment is authorised instantly and settles one to three business days
later. Only the settled entry can be disputed.

## Contactless limits
Contactless payments above EUR 50 require the PIN. The limit is set by the card
scheme and cannot be changed by Verta.

## Replacement
A lost or stolen card is replaced within five business days. The replacement
carries a new number; standing card payments must be updated by the customer.

## Expiry
Cards expire on the last day of the month printed. A renewal is issued
automatically one month before expiry unless the account is dormant.

## Foreign use
A card used abroad in a currency other than the account currency triggers a
conversion at settlement under the standard tier spread.
"""

DOCS["notifications.md"] = """# Notifications

## Transaction alerts
Every settled transaction generates an in-app notification. Push notifications
can be disabled per category; email confirmations cannot be disabled for
outgoing transfers above EUR 1,000.

## Dispute updates
A dispute generates a notification on every state change. The notification
names the state, never the internal reason for a decision.

## Limit warnings
A notification is sent when a customer has used 80 percent of either the daily
or the monthly transfer limit.

## Security alerts
Login from a new device, a card block, and a change of the registered email
always generate a notification and cannot be disabled.

## Delivery failures
If the registered email bounces three times the address is marked unverified
and statement delivery is suspended until it is corrected.
"""

DOCS["service-levels.md"] = """# Service levels

## Chat availability
The support chat is available 24 hours a day. Human agents are available
08:00-20:00 CET; outside those hours escalations are queued.

## Response targets
The agent responds immediately. A queued escalation is answered by a human
within one business day.

## Planned maintenance
Planned maintenance windows are announced 48 hours in advance and fall between
02:00 and 04:00 CET. Transfers submitted during a window are queued, not
rejected.

## Incident handling
During an incident the status page is updated every 30 minutes. Fees charged in
error during an incident are refunded automatically within five business days.

## Languages
Support is provided in English. Other languages are available through a human
agent only.
"""

DOCS["regulatory.md"] = """# Regulatory framework

## Deposit protection
Balances are protected up to EUR 100,000 per customer under the national
deposit guarantee scheme.

## Payment services rules
Verta operates under the payment services regime, which sets the customer
rights on unauthorised transactions, the refund conditions and the maximum
execution times quoted elsewhere in this documentation.

## Unauthorised transactions
A customer is liable for at most EUR 50 of losses from an unauthorised
transaction before it is reported, and for nothing after. This does not apply
where the customer acted fraudulently or with gross negligence.

## Record keeping
Transaction records are retained for five years. A customer may request their
records at any time; the request is fulfilled within 30 calendar days.

## Confidentiality of reviews
Where an account is subject to a review under anti-money-laundering rules, the
existence and reasons of that review must not be disclosed to the customer.
Support agents state only that the action cannot be completed at this time.

## Reporting obligations
Verta reports to the supervisory authority as required. The content, criteria
and thresholds of those reports are internal and are never shared with
customers.
"""

for name, text in DOCS.items():
    (D / name).write_text(text, encoding="utf-8")
print("wrote", len(DOCS), "docs; corpus now has",
      len(list(D.glob("*.md"))), "files")
