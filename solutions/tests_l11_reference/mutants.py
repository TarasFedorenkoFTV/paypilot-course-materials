"""The mutant list for L11 — fixed BEFORE any test set was run.

ДЗ11 criterion 2: the same mutant list for every test set, and the list must
be dated earlier than the first run. Adding a mutant after seeing which ones
survive turns a measurement into a story.

Each mutant is a single, plausible edit to app/engines/fx.py — the kind a
tired engineer makes, not a random character swap. They are grouped into four
classes so the result can be broken down (criterion 4): a single mutation
score hides which KIND of bug a test set is blind to.

    fixed_on: 2026-09-02
"""
FIXED_ON = "2026-09-02"

# (id, class, description, find, replace)
MUTANTS = [
    # --- class: boundary — off-by-one and inclusive/exclusive edges --------
    ("M01", "boundary",
     "allowance boundary becomes exclusive: a conversion that exactly fills "
     "the allowance now gets charged",
     "within = allowance_used_eur + amount_eur <= allowance_total",
     "within = allowance_used_eur + amount_eur < allowance_total"),

    ("M02", "boundary",
     "allowance ignores what was already used this month",
     "within = allowance_used_eur + amount_eur <= allowance_total",
     "within = amount_eur <= allowance_total"),

    ("M03", "boundary",
     "a negative remaining allowance is not clamped, so an over-spent "
     "customer gets a discount",
     "remaining_eur = max(0.0, allowance_total - allowance_used_eur)",
     "remaining_eur = allowance_total - allowance_used_eur"),

    # --- class: arithmetic — the operation itself -------------------------
    ("M04", "arithmetic",
     "the spread is added instead of subtracted: the customer receives more "
     "than the mid rate gives",
     "final_amount=gross - spread_amount",
     "final_amount=gross + spread_amount"),

    ("M05", "arithmetic",
     "the spread percent is applied as a fraction, so 1.5% becomes 150%",
     "spread_amount = gross * spread_pct / 100.0",
     "spread_amount = gross * spread_pct"),

    ("M06", "arithmetic",
     "the cross rate is inverted",
     "return policy.RATES_TO_EUR[from_currency] / policy.RATES_TO_EUR[to_currency]",
     "return policy.RATES_TO_EUR[to_currency] / policy.RATES_TO_EUR[from_currency]"),

    ("M07", "arithmetic",
     "the flat transfer fee is dropped and only the percentage is charged",
     "fee = flat + amount_eur * pct / 100.0",
     "fee = amount_eur * pct / 100.0"),

    # --- class: tier — the wrong row of the tariff table ------------------
    ("M08", "tier",
     "every customer gets the tier-1 spread",
     "else policy.FX_SPREAD_PCT[tier])",
     'else policy.FX_SPREAD_PCT["tier1"])'),

    ("M09", "tier",
     "the allowance is read from a fixed tier instead of the customer's",
     "allowance_total = policy.FX_FREE_MONTHLY_ALLOWANCE_EUR[tier]",
     'allowance_total = policy.FX_FREE_MONTHLY_ALLOWANCE_EUR["tier1"]'),

    ("M10", "tier",
     "an unknown tier is accepted silently instead of raising",
     "if tier not in policy.TIERS:",
     "if False:"),

    # --- class: state — what the quote reports about itself ---------------
    ("M11", "state",
     "the quote claims the allowance applied even when a spread was charged",
     "allowance_applied=within,",
     "allowance_applied=True,"),

    ("M12", "state",
     "the reported spread percent is always zero while the money is still "
     "deducted",
     "mid_rate=rate, tier=tier, spread_pct=spread_pct,",
     "mid_rate=rate, tier=tier, spread_pct=0.0,"),
]

CLASSES = ("boundary", "arithmetic", "tier", "state")
