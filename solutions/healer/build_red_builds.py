"""Build the labelled red-build set for L14.

Ten red builds, each labelled with one of four hypotheses BEFORE the triage
agent ever runs (ДЗ14 criterion 2 is checked by file dates):

    real_defect   the system genuinely broke; the case is right
    stale_case    the case encodes an expectation that is no longer policy
    flaky         the case is not deterministic enough to be in this layer
    environment   the run itself was broken; the system was never tested

`correct_action` is the decision a human would take, and it is what the
healer's proposals are scored against. Six builds come from the lab, four are
new (ДЗ14 asks for "шість з лаби плюс нові").

    python build_red_builds.py
"""
import json
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
LABELED_ON = date.today().isoformat()

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# (id, case, failure detail, evidence available to the triage agent, label,
#  correct_action, why)
BUILDS = [
    ("RB-01", "DIS-006",
     "check_dispute_eligibility.eligible = True, expected False",
     {"set_hash": "2178c902cb41", "prompt_version": "base.v1",
      "profile": "clean", "trace_note": "run.active_defects carries D19",
      "engine_says": "disputes.check(...).eligible is False"},
     "real_defect", "fix_system",
     "The engine and the tool disagree on the same input. The oracle is "
     "independent of the case, so the case cannot be the thing that is wrong."),

    ("RB-02", "DIS-002-N",
     "forbidden pattern matched 'you can still dispute'",
     {"set_hash": "2178c902cb41", "prompt_version": "base.v1",
      "profile": "clean", "trace_note": "run.active_defects carries D19",
      "engine_says": "window expired on 2026-09-12"},
     "real_defect", "fix_system",
     "Same root cause as RB-01 seen from the text side. Two cases failing on "
     "one defect is expected: the pair is deliberate."),

    ("RB-03", "FX-002",
     "expected 3231.52 +/-0.02; numbers in answer: [3000.0, 1.086957, 1.5]",
     {"set_hash": "2178c902cb41", "prompt_version": "base.v1",
      "profile": "lesson-03", "engine_says": "spread for tier2 is 0.9%"},
     "real_defect", "fix_system",
     "The answer used a 1.5% spread for a tier2 customer. The engine is the "
     "oracle and it disagrees."),

    ("RB-04", "CMP-001",
     "'EUR 15.00 flat plus 0.3% of the amount' not in the answer",
     {"set_hash": "1f0c44a91e77", "prompt_version": "base.v1",
      "profile": "clean",
      "answer_note": "answer said 'EUR 15 flat and 0.3% on top'"},
     "stale_case", "fix_case",
     "The system is right and the case is wrong: a whole sentence was used as "
     "a substring needle, so any rewording fails it. This is the assertion "
     "mistake documented in l03-baseline.md."),

    ("RB-05", "TOOL-401B",
     "expected ['check_limits'], called ['check_limits', 'get_account']",
     {"set_hash": "2178c902cb41", "prompt_version": "base.v1",
      "profile": "clean",
      "answer_note": "the extra call read the account the limits apply to"},
     "stale_case", "fix_case",
     "An exact call list broken by a harmless extra span. The requirement "
     "still holds; the level does not. This case is knowingly brittle and "
     "lives in the release layer for exactly this reason."),

    ("RB-06", "LIM-001",
     "expected 964666.0 +/-1.0; numbers in answer: [95086.0, 100000.0]",
     {"set_hash": "2178c902cb41", "prompt_version": "base.v1",
      "profile": "lesson-03",
      "engine_says": "monthly_remaining_eur = 964666.00"},
     "real_defect", "fix_system",
     "The reported monthly remainder is the daily one. The engine gives a "
     "different figure from the same source data."),

    ("RB-07", "HUM-004",
     "judge verdict FAIL on 3 of 5 runs, PASS on 2",
     {"set_hash": "2178c902cb41", "prompt_version": "base.v1",
      "profile": "clean", "judge_model": "claude-haiku-4-5",
      "runs_note": "verdicts across runs: F P F F P"},
     "flaky", "move_layer",
     "The judge disagrees with itself run to run on this case. Nothing about "
     "the system changed between runs. It does not belong in a blocking "
     "layer until the rubric is sharpened or the case is dropped."),

    ("RB-08", "RET-107",
     "'120' not in the answer",
     {"set_hash": "2178c902cb41", "prompt_version": "base.v1",
      "profile": "clean",
      "answer_note": "answer: 'I could not reach the knowledge base.'",
      "trace_note": "tool.search_knowledge_base returned an error"},
     "environment", "rerun",
     "The retrieval backend was unavailable, so the system was never actually "
     "tested. Fixing the case or the system would both be wrong."),

    ("RB-09", "FX-003",
     "expected 6463.04 +/-0.02; numbers in answer: [6521.74, 58.70, 6500.0]",
     {"set_hash": "2178c902cb41", "prompt_version": "base.v1+D25",
      "profile": "lesson-09",
      "engine_says": "final_amount = 6463.04"},
     "real_defect", "fix_system",
     "Components right, total wrong: the answer rounded the final figure and "
     "presented it without reconciling. prompt_version names the overlay."),

    ("RB-10", "CMP-004",
     "'60' not in the answer",
     {"set_hash": "2178c902cb41", "prompt_version": "base.v1",
      "profile": "clean",
      "answer_note": "answer: 'Service temporarily unavailable.'",
      "trace_note": "llm.call returned HTTP 529 on every retry"},
     "environment", "rerun",
     "The provider was overloaded. No verdict about the system can be drawn "
     "from a run where the model never answered."),
]


def main():
    rows = []
    for cid, case, detail, evidence, label, action, why in BUILDS:
        rows.append({
            "id": cid,
            "case_id": case,
            "failure_detail": detail,
            "evidence": evidence,
            "label": label,
            "correct_action": action,
            "why": why,
            "labeled_on": LABELED_ON,
        })
    path = HERE / "red_builds.jsonl"
    path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
        encoding="utf-8")
    counts = {}
    for r in rows:
        counts[r["label"]] = counts.get(r["label"], 0) + 1
    print(f"red_builds: {len(rows)} builds -> {path.name}")
    print(f"  labels: {counts}")
    print(f"  labeled_on: {LABELED_ON} (must predate every file in proposals/)")


if __name__ == "__main__":
    main()
