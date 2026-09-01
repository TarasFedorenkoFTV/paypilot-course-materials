"""Limits engine. Key property (ТЗ §5.3): the daily and the monthly
remainder are different numbers computed from the same source; confusing
them is defect D22 — which lives in the tool, never here."""
from dataclasses import dataclass, asdict
from datetime import date


@dataclass
class LimitStatus:
    tier: str
    as_of: str
    daily_limit_eur: float
    daily_spent_eur: float
    daily_remaining_eur: float
    monthly_limit_eur: float
    monthly_spent_eur: float
    monthly_remaining_eur: float

    def as_dict(self) -> dict:
        return {k: (round(v, 2) if isinstance(v, float) else v)
                for k, v in asdict(self).items()}


def status(tier: str, as_of: date, outgoing_transfers: list[dict]) -> LimitStatus:
    """`outgoing_transfers`: [{"date": date, "amount_eur": float}, ...] —
    already-settled outgoing operations for the account(s) of one customer."""
    from app.engines import policy
    if tier not in policy.TIERS:
        raise ValueError(f"Unknown tier: {tier}")
    daily_spent = sum(t["amount_eur"] for t in outgoing_transfers
                      if t["date"] == as_of)
    monthly_spent = sum(t["amount_eur"] for t in outgoing_transfers
                        if t["date"].year == as_of.year and t["date"].month == as_of.month)
    daily_limit = policy.DAILY_LIMIT_EUR[tier]
    monthly_limit = policy.MONTHLY_LIMIT_EUR[tier]
    return LimitStatus(
        tier=tier, as_of=as_of.isoformat(),
        daily_limit_eur=daily_limit, daily_spent_eur=daily_spent,
        daily_remaining_eur=max(0.0, daily_limit - daily_spent),
        monthly_limit_eur=monthly_limit, monthly_spent_eur=monthly_spent,
        monthly_remaining_eur=max(0.0, monthly_limit - monthly_spent))
