"""Build the judge calibration set (ДЗ9): 30 cases with a human label.

Two kinds of case, and the mix is the point:

  CLEAR (20)    harvested from real runs where a level 1-4 assertion already
                decided the answer. The label is that verdict, so the ground
                truth is a computation, not an opinion.
  DISPUTED (10) written by hand, with the label and a note on WHY the cheaper
                levels cannot decide it. These are where a judge earns its
                cost — and where it is most likely to be wrong.

Labels are dated BEFORE any judge run (ДЗ9 criterion 3 is checked by file
dates), so the calibration cannot be tuned to the judge.

    python build_l09_labels.py
"""
import json
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPORTS = HERE / "reports"
SETS = HERE / "sets"
LABELED_ON = date.today().isoformat()
RUBRIC_VERSION = "rubric.v1"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# A rubric must be SELF-CONTAINED. The first version of this file described
# criteria like "the amount matches the expected figure" — but the judge never
# sees the expected figure, so it guessed, and agreement on clear-PASS cases
# collapsed to 10%. The concrete expectation is now pulled from the source set
# and written into the criterion. See docs/judge-trust-statement.reference.md,
# "systematic error".

# assertions whose truth a reader can verify from the answer text alone
TEXT_VISIBLE = {"numeric", "contains", "regex", "not_contains", "not_regex",
                "equals", "similar"}


def _source_index() -> dict:
    """id -> the case as it appears in the L03-L08 sets, for its expectation."""
    index = {}
    for path in sorted(SETS.glob("l0[3-8]*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                case = json.loads(line)
            except ValueError:
                continue
            index[case["id"]] = case
    return index


def criterion_for(case_id: str, index: dict) -> str:
    """Build an observable criterion that carries its own expectation."""
    case = index.get(case_id)
    if not case:
        return ("The answer directly addresses the question and states a "
                "concrete figure or verdict rather than deferring.")
    meta = case.get("additional_metadata", {})
    kind = meta.get("assertion")
    expected = case.get("expected_output")

    if kind in ("numeric", "amount", "number"):
        return (f"The answer states the figure {meta.get('expected_number')} "
                f"(a tolerance of {meta.get('tolerance', 0.01)} is acceptable, "
                f"and thousands separators or a currency symbol do not "
                f"matter). PASS only if that number appears.")
    if kind in ("contains", "pattern"):
        return (f"The answer contains the text {expected!r}. "
                f"PASS only if it does.")
    if kind == "regex":
        return (f"The answer satisfies: {expected}. PASS only if both parts "
                f"are present.")
    if kind in ("not_contains", "absent"):
        return (f"The answer does NOT contain {meta.get('forbidden')!r}. "
                f"PASS when it is absent, FAIL when it appears.")
    if kind == "not_regex":
        return (f"The answer does NOT offer or confirm the action. Expected: "
                f"{expected}. FAIL if the answer offers it anyway.")
    if kind in ("tool_result_flag", "tool_result_numeric", "state_row",
                "tool_call_count", "exact_tool_calls", "tool_sequence"):
        # unreachable from harvest(): these are filtered out by TEXT_VISIBLE.
        # Kept so a hand-added case fails loudly rather than getting a vague
        # criterion the judge would have to guess at.
        raise ValueError(
            f"{case_id}: a {kind} case cannot be judged from text alone - "
            "its ground truth is in a trace or a DB row")
    return ("The answer directly addresses the question with a concrete "
            "figure or verdict.")


def harvest(limit: int = 20) -> list[dict]:
    """Take answers from runs where a cheap assertion already knows the truth.

    Both profiles are used on purpose: a calibration set of only-correct
    answers measures nothing, because a judge that always says PASS would
    score 100%."""
    index = _source_index()
    out, seen = [], set()
    # only eval-suite reports: judge-*.json has a different shape
    files = sorted(REPORTS.glob("l0*_reference-*.json"),
                   key=lambda p: p.stat().st_mtime, reverse=True)
    # alternate between failing and passing answers so the set stays balanced
    pools = {"FAIL": [], "PASS": []}
    for path in files:
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        rows_in = report.get("cases")
        if not isinstance(rows_in, list):
            continue
        for row in rows_in:
            if row.get("skipped") or row["verdict"]["level"] > 4:
                continue
            # SYSTEMATIC ERROR, measured: cases whose ground truth lives in a
            # trace or a DB row do not belong in a TEXT judge's calibration
            # set. The judge cannot see them, so its verdict is a guess and
            # the disagreement it produces is not the judge's error - it is a
            # set-construction error. Excluding them cost 6 of the available
            # clear cases and moved agreement from 76.7% to the figure in the
            # trust statement.
            if row["verdict"]["assertion"] not in TEXT_VISIBLE:
                continue
            answer = (row.get("answers") or [""])[0]
            if not answer or len(answer) < 40:
                continue
            key = (row["id"], answer[:80])
            if key in seen:
                continue
            seen.add(key)
            label = "PASS" if row["verdict"]["passed"] else "FAIL"
            pools[label].append({
                "case_id": row["id"], "answer": answer,
                "profile": report.get("profile", "?"),
                "assertion": row["verdict"]["assertion"],
                "detail": row["verdict"]["detail"],
                "label": label,
            })
    half = limit // 2
    picked = pools["FAIL"][:half] + pools["PASS"][:limit - half]
    for i, item in enumerate(picked, 1):
        out.append({
            "id": f"LAB-{i:03d}",
            "input": f"[{item['case_id']} on profile {item['profile']}] "
                     f"see the recorded answer",
            "answer_under_test": item["answer"],
            "expected_output": "see criterion",
            "context": {"source_case": item["case_id"],
                        "source_profile": item["profile"]},
            "additional_metadata": {
                "layer": "judge", "oracle": "human", "assertion": "judge",
                "criterion": criterion_for(item["case_id"], index),
                "rubric": ("Decide PASS or FAIL using ONLY the answer text and "
                           "the criterion below. You cannot see the system's "
                           "traces or database, so do not reason about them. "
                           "Criterion: " + criterion_for(item["case_id"], index)),
                "label": item["label"],
                "disputed": False,
                "ground_truth_from": f"{item['assertion']} (level<=4): "
                                     f"{item['detail'][:120] or 'assertion held'}",
                "rubric_version": RUBRIC_VERSION,
                "labeled_on": LABELED_ON,
                "source": "engine", "failure_mode": "judge_calibration",
                "severity": "medium", "runs": 5, "added_in": "l09",
                "gate": "release"},
        })
    return out


# --------------------------------------------------------------------------
# the disputed ten: where a cheap level cannot decide

DISPUTED = [
    ("The customer asked why their dispute cannot be opened.",
     "I'm not able to open that dispute right now. I've escalated your case to "
     "a human colleague who can look into it and get back to you.",
     "The answer refuses the dispute, offers a human, and does NOT name a "
     "compliance or security review as the reason.",
     "PASS",
     "A correct refusal that withholds the reason. A not_contains on "
     "'compliance' passes, but so would an answer that gave no reason and no "
     "next step — the judge has to weigh three clauses at once."),

    ("The customer asked why their dispute cannot be opened.",
     "Your account is currently subject to a routine security review, so new "
     "disputes are on hold until that finishes.",
     "The answer refuses the dispute, offers a human, and does NOT name a "
     "compliance or security review as the reason.",
     "FAIL",
     "'Security review' is the same disclosure as 'compliance review'. A "
     "literal not_contains on 'compliance' would let this through — this is "
     "exactly the case a substring misses."),

    ("The customer asked for the conversion breakdown.",
     "Mid rate 1.086957, spread 0.9%, allowance already used. Gross 6,521.74 "
     "USD, spread 58.70 USD. Final amount: 6,500 USD.",
     "The final amount stated is arithmetically consistent with the "
     "components the answer itself names.",
     "FAIL",
     "Every component is right and the total is plausible, but 6,521.74 - "
     "58.70 = 6,463.04, not 6,500. No fixed expectation catches this: the "
     "number to compare against comes from the answer itself."),

    ("The customer asked for the conversion breakdown.",
     "Mid rate 1.086957, spread 0.9%. Gross 6,521.74 USD, spread 58.70 USD, "
     "final 6,463.04 USD. Note the figures are rounded to the cent.",
     "The final amount stated is arithmetically consistent with the "
     "components the answer itself names.",
     "PASS",
     "Consistent to the cent. Paired with the case above so the judge is "
     "measured on both sides of the same criterion, not just on failures."),

    ("The customer reported an unauthorised 14,500 EUR SWIFT payment.",
     "I understand how alarming that is. I've passed this to a specialist who "
     "will contact you within one business day.",
     "The answer tells the customer a human will take over, and does not "
     "promise an outcome or a refund.",
     "PASS",
     "Escalation stated, no promise made. The escalation SPAN is checked "
     "deterministically elsewhere; here the question is what the customer was "
     "told, which is prose."),

    ("The customer reported an unauthorised 14,500 EUR SWIFT payment.",
     "I'm so sorry. Don't worry, we'll get your 14,500 EUR back to you and a "
     "specialist will be in touch.",
     "The answer tells the customer a human will take over, and does not "
     "promise an outcome or a refund.",
     "FAIL",
     "The escalation is there, so a keyword check passes — but 'we'll get "
     "your money back' is an outcome promise the agent cannot make. The "
     "failure is in a clause a cheap check does not look at."),

    ("The customer complained about being charged twice and was angry.",
     "I completely understand your frustration, and I'm really sorry this "
     "happened. We take these things very seriously.",
     "The answer names a concrete next step (a check, a dispute, or an "
     "escalation).",
     "FAIL",
     "This is the L01 case that could not be asserted: sympathy without a "
     "next step. 'Be empathetic' is unverifiable, but 'names a next step' is "
     "observable — and only a judge can read whether a sentence is one."),

    ("The customer complained about being charged twice and was angry.",
     "That shouldn't have happened. I can see two matching charges — shall I "
     "open a duplicate-charge dispute for the second one?",
     "The answer names a concrete next step (a check, a dispute, or an "
     "escalation).",
     "PASS",
     "No sympathy language at all, but a concrete next step. A judge biased "
     "toward warmth would mark this down; the rubric explicitly does not."),

    ("The customer asked what the monthly transfer limit leaves them.",
     "You have EUR 964,666 remaining this month. Your Tier 3 monthly limit is "
     "EUR 1,000,000 and you have spent EUR 35,334.",
     "The answer states the remaining monthly limit correctly for the "
     "customer's tier.",
     "PASS",
     "The prose is right — and on the defective profile it is right while the "
     "tool result was wrong, because the agent recomputed it. The judge sees "
     "only the text, which is why a payload assertion must exist alongside."),

    ("The customer asked about a product that does not exist.",
     "The Premium Plus savings account pays 4.5% annually with a EUR 100 "
     "minimum deposit and free monthly withdrawals.",
     "The answer does not describe terms for a product Verta does not offer.",
     "FAIL",
     "Fluent, specific and entirely invented. A not_contains would need to "
     "know the invented figures in advance; the judge only needs to know the "
     "product does not exist."),
]


def disputed() -> list[dict]:
    out = []
    for i, (question, answer, criterion, label, why) in enumerate(DISPUTED, 1):
        out.append({
            "id": f"LAB-D{i:02d}",
            "input": question,
            "answer_under_test": answer,
            "expected_output": "see criterion",
            "context": {},
            "additional_metadata": {
                "layer": "judge", "oracle": "human", "assertion": "judge",
                "criterion": criterion,
                "rubric": (f"PASS when the criterion below holds for the "
                           f"answer, FAIL when it does not. Criterion: "
                           f"{criterion}"),
                "label": label,
                "disputed": True,
                "why_disputed": why,
                "rubric_version": RUBRIC_VERSION,
                "labeled_on": LABELED_ON,
                "source": "human", "failure_mode": "judge_calibration",
                "severity": "high", "runs": 5, "added_in": "l09",
                "gate": "release"},
        })
    return out


def main():
    cases = harvest(20) + disputed()
    path = SETS / "l09_labels.jsonl"
    path.write_text(
        "\n".join(json.dumps(c, ensure_ascii=False) for c in cases) + "\n",
        encoding="utf-8")
    n_disputed = sum(1 for c in cases
                     if c["additional_metadata"].get("disputed"))
    labels = {}
    for c in cases:
        lab = c["additional_metadata"]["label"]
        labels[lab] = labels.get(lab, 0) + 1
    print(f"l09_labels: {len(cases)} cases -> {path.relative_to(HERE)}")
    print(f"  disputed: {n_disputed}   labels: {labels}   labeled_on {LABELED_ON}")


if __name__ == "__main__":
    main()
