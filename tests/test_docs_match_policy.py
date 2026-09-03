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


def test_documented_demo_amount_is_not_a_cancellation_point():
    """D20 and D21 both live on lesson-03 and cancel exactly when the
    conversion equals 2.5x the remaining free allowance: D20 multiplies the
    spread by 1.667, D21 applies it to 0.4 of the amount, and the product is
    1.0. final_amount is then identical on clean and on the defect profile,
    so a case asserting the total goes green on two critical defects at once.

    A student found this on 500 EUR. The lesson guide must never suggest such
    an amount, and this test is what stops one drifting in.
    """
    from app.engines import fx, policy

    def diverges(amount: float, used: float) -> bool:
        clean = fx.quote(amount, "EUR", "USD", "tier2", allowance_used_eur=used)
        broken = fx.quote(amount, "EUR", "USD", "tier2", allowance_used_eur=used,
                          spread_pct_override=policy.FX_SPREAD_PCT["tier1"],
                          partial_allowance=True)
        return abs(broken.final_amount - clean.final_amount) > 0.01

    ratio = 1 - policy.FX_SPREAD_PCT["tier2"] / policy.FX_SPREAD_PCT["tier1"]
    remaining = policy.FX_FREE_MONTHLY_ALLOWANCE_EUR["tier2"]
    # the caveat's arithmetic still holds
    assert not diverges(remaining / ratio, 0.0), \
        "the cancellation point moved; the D20 caveat needs remeasuring"

    guide = (DOC.parent / "lesson-guide.md").read_text(encoding="utf-8")
    l03 = guide.split("## L03")[1].split("\n## ")[0]
    for amount in re.findall(r"Convert (\d+) EUR", l03):
        assert diverges(float(amount), 0.0), (
            f"L03 suggests converting {amount} EUR, which is a D20/D21 "
            f"cancellation point: final_amount is identical on both profiles")


def test_catalog_documents_the_cancellation():
    catalog = (DOC.parent / "defect-catalog.md").read_text(encoding="utf-8")
    section = catalog.split("## D20")[1].split("## D21")[0]
    assert "гасить d21" in section.lower(), \
        "the D20/D21 interaction is not in the catalog"


def test_d27_exception_is_declared_not_silently_fixed():
    """The customer decided on 2026-09-03 to keep D27 failing and teach with
    it rather than change the acceptance rule or tune the prompt until the
    number looked right. This test is what makes that decision durable: if
    someone later declares a clean-side corridor for it, or drops the
    exception without a decision, the suite says so.
    """
    import yaml
    doc = yaml.safe_load(
        (DOC.parent.parent / "profiles" / "corridors.yaml").read_text(encoding="utf-8"))
    exceptions = doc.get("known_exceptions") or {}
    assert "D27" in exceptions, \
        "D27 is no longer a declared exception — was that a decision or a slip?"
    entry = exceptions["D27"]
    for field in ("decided_on", "clean_baseline", "reason", "how_to_demonstrate"):
        assert entry.get(field), f"D27 exception is missing {field}"
    # D27 keeps its profile-side corridor — declared before the run, and it
    # passed it at 100%. What must never appear is an allowance for firing
    # on clean: that would be a threshold invented to fit the observed 1/30.
    assert doc["corridors"]["D27"]["low_pct"] >= 30, "profile corridor lost"
    for field in ("clean_pct", "clean_low_pct", "clean_allowed", "clean_max_pct"):
        assert field not in entry, f"D27 exception invents {field}"
        assert field not in doc["corridors"]["D27"], f"corridor invents {field}"

    guide = (DOC.parent / "lesson-guide.md").read_text(encoding="utf-8")
    l09 = guide.split("## L09")[1].split("\n## ")[0]
    assert "різницю частот" in l09, \
        "L09 must tell the lecturer to show D27 as a rate difference"
