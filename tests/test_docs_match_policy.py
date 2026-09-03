"""Guard against documentation drift.

The customer acceptance review found docs/seed-data.md still describing tiers
as standard/premium/platinum with spreads 1.5/1.0/0.5 and allowances
1000/5000/20000 — none of which had been true since the engines were renamed.
A lecturer reading that table would have taught wrong numbers.

Prose can drift silently; a parsed table cannot.
"""
import re
from pathlib import Path

from app import db, seed
from app.engines import policy

DOC = Path(__file__).resolve().parent.parent / "docs" / "seed-data.md"


def _tariff_rows() -> dict[str, list[str]]:
    """Parse the tier table: tier -> [spread, allowance, daily, monthly]."""
    rows = {}
    for line in DOC.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\|\s*(tier\d)\s*\|(.+)\|\s*$", line)
        if m:
            rows[m.group(1)] = [c.strip() for c in m.group(2).split("|")]
    return rows


def _num(cell: str) -> float:
    """'1 000 EUR' -> 1000.0, '0.9%' -> 0.9 (thin and normal spaces alike)."""
    return float(re.sub(r"[^\d.]", "", cell.replace(" ", "")))


def test_tariff_table_matches_engine():
    rows = _tariff_rows()
    assert set(rows) == set(policy.TIERS), "tier rows missing from seed-data.md"
    for tier, cells in rows.items():
        spread, allowance, daily, monthly = cells[:4]
        assert _num(spread) == policy.FX_SPREAD_PCT[tier], f"{tier} spread"
        assert _num(allowance) == policy.FX_FREE_MONTHLY_ALLOWANCE_EUR[tier], f"{tier} allowance"
        assert _num(daily) == policy.DAILY_LIMIT_EUR[tier], f"{tier} daily limit"
        assert _num(monthly) == policy.MONTHLY_LIMIT_EUR[tier], f"{tier} monthly limit"


def test_dispute_windows_documented():
    text = DOC.read_text(encoding="utf-8")
    for code, days in policy.DISPUTE_WINDOWS_DAYS.items():
        assert re.search(rf"`{re.escape(code)}`\s*\D{{0,12}}{days}\b", text), \
            f"{code}={days} not documented in seed-data.md"


def test_customer_tiers_match_seed():
    db.reset()
    actual = {r["id"]: r["tier"] for r in db.table_dump("customers")}
    text = DOC.read_text(encoding="utf-8")
    for cid, tier in actual.items():
        m = re.search(rf"^\|\s*{cid}[^|]*\|\s*(\S+)\s*\|", text, re.M)
        assert m, f"{cid} missing from the seed table"
        assert m.group(1) == tier, f"{cid}: doc says {m.group(1)}, seed says {tier}"


def test_seed_version_documented():
    assert seed.SEED_VERSION in DOC.read_text(encoding="utf-8")


def test_documented_test_counts_are_current():
    """The trust table in ONBOARDING.md quotes how many tests exist. It went
    stale twice — once in the very commit that added the tests it undercounted
    — so the number is now derived and compared instead of remembered."""
    import ast as _ast

    def count(root: Path) -> int:
        total = 0
        for f in root.rglob("*.py"):
            try:
                tree = _ast.parse(f.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError):
                continue
            total += sum(1 for n in _ast.walk(tree)
                         if isinstance(n, _ast.FunctionDef)
                         and n.name.startswith("test_"))
        return total

    root = DOC.parent.parent
    stand = count(root / "tests")
    everything = stand + count(root / "solutions")

    onboarding = (root / "docs" / "ONBOARDING.md").read_text(encoding="utf-8")
    row = next(line for line in onboarding.splitlines()
               if "стенд не ламається" in line)
    numbers = [int(n) for n in re.findall(r"\*\*(\d+)\*\*", row)]
    assert stand in numbers, f"ONBOARDING claims {numbers}, tests/ has {stand}"
    assert everything in numbers, \
        f"ONBOARDING claims {numbers}, the whole repo has {everything}"
