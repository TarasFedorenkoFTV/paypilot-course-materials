"""Manual baseline: 7 tests on app/engines/fx.py, written by hand.

Written BEFORE any generation, in 38 minutes measured on a clock (not "about
40" — ДЗ11 rejects a round number arrived at afterwards):

    13 min  reading policy.py and fx.py and writing down what the allowance
            rule actually says, which is where two of these tests came from
    19 min  writing the seven tests
     6 min  running them and fixing two wrong expectations of my own

The choice of cases is the point, not the count. Each one targets a decision
in the code, and three of them target a BOUNDARY, because that is where the
allowance rule is decided:

    exactly at the allowance      the <= in the comparison
    one cent over                 the other side of the same edge
    already over-spent            the max(0.0, ...) clamp
"""
from datetime import date

import pytest

from app.engines import fx, policy


# --- the spread-free path -------------------------------------------------

def test_conversion_inside_the_allowance_is_spread_free():
    q = fx.quote(100, "EUR", "USD", "tier1", allowance_used_eur=0)
    assert q.allowance_applied is True
    assert q.spread_pct == 0.0
    assert q.spread_amount == 0.0
    assert q.final_amount == q.gross_amount


def test_conversion_exactly_filling_the_allowance_is_still_free():
    """The rule says the allowance applies when the whole conversion FITS,
    and 500 into a 500 allowance fits. This is the <= in the comparison."""
    total = policy.FX_FREE_MONTHLY_ALLOWANCE_EUR["tier1"]
    q = fx.quote(total, "EUR", "USD", "tier1", allowance_used_eur=0)
    assert q.allowance_applied is True, "the boundary must be inclusive"
    assert q.spread_pct == 0.0


def test_one_cent_over_the_allowance_charges_the_whole_conversion():
    """The other side of the same edge — and note WHAT is charged: policy
    applies the spread to the entire amount, not to the excess."""
    total = policy.FX_FREE_MONTHLY_ALLOWANCE_EUR["tier1"]
    q = fx.quote(total + 0.01, "EUR", "USD", "tier1", allowance_used_eur=0)
    assert q.allowance_applied is False
    assert q.spread_pct == policy.FX_SPREAD_PCT["tier1"]
    expected = q.gross_amount * policy.FX_SPREAD_PCT["tier1"] / 100.0
    assert q.spread_amount == pytest.approx(expected, abs=1e-6)


def test_allowance_already_used_this_month_counts():
    """A customer who has used 450 of 500 cannot convert another 100 free."""
    q = fx.quote(100, "EUR", "USD", "tier1", allowance_used_eur=450.0)
    assert q.allowance_applied is False
    assert q.allowance_used_before_eur == 450.0


def test_over_spent_allowance_does_not_become_a_discount():
    """If more was used than the allowance holds, the remainder is clamped at
    zero. Without the clamp a negative remainder would make the conversion
    look free again."""
    q = fx.quote(100, "EUR", "USD", "tier1", allowance_used_eur=9999.0)
    assert q.allowance_applied is False
    assert q.spread_amount > 0


# --- the money ------------------------------------------------------------

def test_spread_is_subtracted_not_added():
    """Direction matters: the customer receives LESS than the mid rate."""
    q = fx.quote(1000, "EUR", "USD", "tier1", allowance_used_eur=1000)
    assert q.final_amount < q.gross_amount
    assert q.final_amount == pytest.approx(q.gross_amount - q.spread_amount,
                                           abs=1e-9)


def test_each_tier_gets_its_own_spread_and_the_amounts_differ():
    """One test over three tiers: a mutant that hardcodes one tier survives a
    single-tier test but not this one."""
    seen = {}
    for tier in policy.TIERS:
        q = fx.quote(50_000, "EUR", "USD", tier, allowance_used_eur=50_000)
        assert q.spread_pct == policy.FX_SPREAD_PCT[tier], tier
        seen[tier] = q.final_amount
    assert len(set(seen.values())) == len(policy.TIERS), \
        "different tiers must produce different amounts"


def test_unknown_tier_raises_rather_than_guessing():
    with pytest.raises(ValueError):
        fx.quote(100, "EUR", "USD", "platinum-plus")
