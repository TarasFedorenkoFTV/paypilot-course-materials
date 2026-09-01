"""Verta bank tariff policy — the single source of truth for the engines.
All concrete figures were fixed by the implementer (ТЗ §1.4) and must be
mirrored into the KB corpus and course texts by the methodologist."""

BASE_CURRENCY = "EUR"

TIERS = ("standard", "premium", "platinum")

# FX spread over the mid-market rate, by tier (percent).
FX_SPREAD_PCT = {"standard": 1.5, "premium": 1.0, "platinum": 0.5}

# Free monthly conversion allowance, in EUR equivalent. Conversions within
# the allowance are spread-free; beyond it the tier spread applies.
FX_FREE_MONTHLY_ALLOWANCE_EUR = {"standard": 1000, "premium": 5000, "platinum": 20000}

# Mid-market rates to EUR (deterministic, frozen for the stand).
RATES_TO_EUR = {
    "EUR": 1.0,
    "USD": 0.92,
    "GBP": 1.17,
    "PLN": 0.23,
    "CHF": 1.05,
    "UAH": 0.021,
}

# Transfer fees by type: (flat EUR, percent).
TRANSFER_FEES = {
    "internal": (0.0, 0.0),
    "sepa": (0.35, 0.0),
    "swift": (15.0, 0.3),
    "card": (0.0, 1.2),
}

# Daily / monthly outgoing transfer limits by tier, EUR equivalent.
DAILY_LIMIT_EUR = {"standard": 5_000, "premium": 20_000, "platinum": 100_000}
MONTHLY_LIMIT_EUR = {"standard": 50_000, "premium": 200_000, "platinum": 1_000_000}

# Dispute reason codes → chargeback window in days from the transaction date.
DISPUTE_WINDOWS_DAYS = {
    "fraud_card_not_present": 120,
    "goods_not_received": 90,
    "duplicate_charge": 60,
    "service_not_rendered": 90,
    "unauthorized_debit": 56,
}

# Transaction statuses a dispute can be opened against.
DISPUTABLE_STATUSES = {"settled"}


def to_eur(amount: float, currency: str) -> float:
    if currency not in RATES_TO_EUR:
        raise ValueError(f"Unknown currency: {currency}")
    return amount * RATES_TO_EUR[currency]
