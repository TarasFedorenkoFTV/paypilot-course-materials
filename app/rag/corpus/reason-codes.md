# Reason code guide

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
