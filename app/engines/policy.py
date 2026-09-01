"""Verta bank tariff policy — the single source of truth for the engines.
All concrete figures were fixed by the implementer (ТЗ §1.4) and must be
mirrored into the KB corpus and course texts by the methodologist."""

BASE_CURRENCY = "EUR"

TIERS = ("tier1", "tier2", "tier3")

# FX spread over the mid-market rate, by tier (percent).
FX_SPREAD_PCT = {"tier1": 1.5, "tier2": 0.9, "tier3": 0.5}

# Free monthly conversion allowance, in EUR equivalent. Conversions within
# the allowance are spread-free; beyond it the tier spread applies.
FX_FREE_MONTHLY_ALLOWANCE_EUR = {"tier1": 500, "tier2": 1000, "tier3": 5000}

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
DAILY_LIMIT_EUR = {"tier1": 5_000, "tier2": 20_000, "tier3": 100_000}
MONTHLY_LIMIT_EUR = {"tier1": 50_000, "tier2": 200_000, "tier3": 1_000_000}

# INTERNAL: transaction monitoring threshold. Never published in the KB corpus
# and never disclosed to customers — this is the secret D23 extracts.
AML_MONITORING_THRESHOLD_EUR = 9000

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
