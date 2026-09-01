# Dispute handling process

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
