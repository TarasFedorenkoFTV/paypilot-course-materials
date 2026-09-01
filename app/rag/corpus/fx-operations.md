# Currency conversion operations

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
