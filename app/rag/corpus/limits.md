# Transfer limits

## Daily and monthly limits by tier
Outgoing transfer limits are tracked in EUR equivalent, separately per day and
per calendar month. The daily and the monthly remainder are different numbers:
both are computed from the same settled-transactions source, but over
different windows.

| Tier | Daily limit | Monthly limit |
|---|---|---|
| Tier 1 | EUR 5,000 | EUR 50,000 |
| Tier 2 | EUR 20,000 | EUR 200,000 |
| Tier 3 | EUR 100,000 | EUR 1,000,000 |

## How the remainder is computed
The daily remainder equals the daily limit minus settled outgoing transfers
dated today. The monthly remainder equals the monthly limit minus settled
outgoing transfers in the current calendar month. A transfer is refused when
it exceeds either remainder.
