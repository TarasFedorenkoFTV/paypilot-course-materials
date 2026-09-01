"""Engine unit tests: the oracle must be right before anything else is."""
from datetime import date

from app.engines import disputes, fx, limits, policy


def test_fx_quote_within_allowance_is_spread_free():
    q = fx.quote(100, "EUR", "USD", "tier1", allowance_used_eur=0)
    assert q.allowance_applied is True
    assert q.spread_pct == 0.0
    assert q.final_amount == q.gross_amount


def test_fx_quote_beyond_allowance_applies_tier_spread():
    q = fx.quote(1000, "EUR", "USD", "tier1", allowance_used_eur=900)
    assert q.allowance_applied is False
    assert q.spread_pct == policy.FX_SPREAD_PCT["tier1"]
    assert q.final_amount == q.gross_amount - q.spread_amount
    assert round(q.spread_amount, 6) == round(q.gross_amount * 0.015, 6)


def test_fx_mid_rate_cross():
    assert round(fx.mid_rate("USD", "EUR"), 6) == round(0.92, 6)
    assert round(fx.mid_rate("EUR", "USD"), 6) == round(1 / 0.92, 6)


def test_transfer_fee_swift():
    fee = fx.transfer_fee(1000, "swift")
    assert fee["total_fee_eur"] == 15 + 3.0


def test_limits_daily_vs_monthly_are_different_numbers():
    as_of = date(2026, 9, 15)
    transfers = [
        {"date": date(2026, 9, 15), "amount_eur": 1000.0},
        {"date": date(2026, 9, 2), "amount_eur": 4000.0},
    ]
    st = limits.status("tier1", as_of, transfers)
    assert st.daily_spent_eur == 1000
    assert st.monthly_spent_eur == 5000
    assert st.daily_remaining_eur == 4000
    assert st.monthly_remaining_eur == 45000
    assert st.daily_remaining_eur != st.monthly_remaining_eur


def test_dispute_inside_window_eligible():
    r = disputes.check("duplicate_charge", date(2026, 7, 20), "settled",
                       date(2026, 9, 15), compliance_hold=False)
    assert r.eligible is True
    assert r.checks["window"] == "pass"


def test_dispute_past_window_not_eligible():
    r = disputes.check("duplicate_charge", date(2026, 7, 14), "settled",
                       date(2026, 9, 15), compliance_hold=False)
    assert r.eligible is False
    assert r.checks["window"].startswith("fail")


def test_dispute_blocked_by_compliance_hold_even_when_window_ok():
    r = disputes.check("goods_not_received", date(2026, 8, 16), "settled",
                       date(2026, 9, 15), compliance_hold=True)
    assert r.checks["window"] == "pass"
    assert r.checks["compliance_hold"].startswith("fail")
    assert r.eligible is False
