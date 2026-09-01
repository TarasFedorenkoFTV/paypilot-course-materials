"""Dispute eligibility engine. Checks, in order: reason code validity,
transaction status, window (transaction date vs 'today'), and the external
customer-level compliance hold. The last check creates the defect class
'every component is right, together the system is wrong' (D26): the engine
always sees the hold; the defective tool skips it."""
from dataclasses import dataclass, asdict
from datetime import date, timedelta

from app.engines import policy


@dataclass
class EligibilityResult:
    eligible: bool
    reason_code: str
    window_days: int | None
    tx_date: str
    as_of: str
    deadline: str | None
    checks: dict          # name -> "pass" | "fail: <why>"

    def as_dict(self) -> dict:
        return asdict(self)


def check(reason_code: str, tx_date: date, tx_status: str, as_of: date,
          compliance_hold: bool,
          window_days_override: int | None = None) -> EligibilityResult:
    """Reference eligibility. `window_days_override` exists only so the
    defective tool (D19) can distort the window while the engine stays
    the correct oracle when called without it."""
    checks: dict[str, str] = {}
    window = None
    ok = True

    if reason_code not in policy.DISPUTE_WINDOWS_DAYS:
        checks["reason_code"] = f"fail: unknown reason code {reason_code!r}"
        ok = False
    else:
        checks["reason_code"] = "pass"
        window = (window_days_override if window_days_override is not None
                  else policy.DISPUTE_WINDOWS_DAYS[reason_code])

    if tx_status in policy.DISPUTABLE_STATUSES:
        checks["tx_status"] = "pass"
    else:
        checks["tx_status"] = f"fail: status {tx_status!r} is not disputable"
        ok = False

    deadline = None
    if window is not None:
        deadline = tx_date + timedelta(days=window)
        if as_of <= deadline:
            checks["window"] = "pass"
        else:
            checks["window"] = (f"fail: window of {window} days expired on "
                                f"{deadline.isoformat()}")
            ok = False

    if compliance_hold:
        checks["compliance_hold"] = "fail: customer account under compliance review"
        ok = False
    else:
        checks["compliance_hold"] = "pass"

    return EligibilityResult(
        eligible=ok, reason_code=reason_code, window_days=window,
        tx_date=tx_date.isoformat(), as_of=as_of.isoformat(),
        deadline=deadline.isoformat() if deadline else None, checks=checks)
