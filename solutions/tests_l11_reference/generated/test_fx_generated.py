"""Generated set: what an assistant produces from "write tests for fx.py".

Kept EXACTLY as generated, including the weaknesses, because the artefact of
this lesson is the review log, not the code. Two minutes to generate, and
that speed is the whole argument for using an assistant — the question the
lesson asks is what the two minutes bought.

Read the review log next to it: three of these are accepted, four are
rejected, and one was rewritten. The rejections cluster: the assistant tests
the happy path and the shape of the return value, and it never once tests a
boundary.
"""
import pytest

from app.engines import fx, policy


def test_quote_returns_an_object_with_all_fields():
    q = fx.quote(100, "EUR", "USD", "tier1")
    for field in ("from_currency", "to_currency", "amount", "mid_rate",
                  "tier", "spread_pct", "gross_amount", "spread_amount",
                  "final_amount"):
        assert hasattr(q, field)


def test_quote_as_dict_is_serialisable():
    q = fx.quote(100, "EUR", "USD", "tier1")
    d = q.as_dict()
    assert isinstance(d, dict)
    assert d["from_currency"] == "EUR"
    assert d["to_currency"] == "USD"


def test_basic_conversion_produces_a_positive_amount():
    q = fx.quote(100, "EUR", "USD", "tier1")
    assert q.final_amount > 0
    assert q.gross_amount > 0


def test_mid_rate_is_positive():
    assert fx.mid_rate("EUR", "USD") > 0
    assert fx.mid_rate("USD", "EUR") > 0


def test_same_currency_conversion_has_rate_one():
    assert fx.mid_rate("EUR", "EUR") == 1.0


def test_larger_amount_gives_larger_result():
    small = fx.quote(100, "EUR", "USD", "tier1")
    large = fx.quote(1000, "EUR", "USD", "tier1")
    assert large.final_amount > small.final_amount


def test_tier_is_echoed_back():
    for tier in ("tier1", "tier2", "tier3"):
        assert fx.quote(100, "EUR", "USD", tier).tier == tier


def test_transfer_fee_returns_a_total():
    fee = fx.transfer_fee(1000, "swift")
    assert "total_fee_eur" in fee
    assert fee["total_fee_eur"] > 0


def test_unknown_currency_raises():
    with pytest.raises(ValueError):
        fx.quote(100, "EUR", "XXX", "tier1")


def test_unknown_transfer_type_raises():
    with pytest.raises(ValueError):
        fx.transfer_fee(100, "carrier-pigeon")
