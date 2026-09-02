"""CI agent with three modes (ДЗ14).

    review   read a run record and comment on a PR: hypothesis + evidence
    triage   classify a red build into one of four hypotheses
    heal     propose a fix — never apply one outside the allowed boundary

The agent is a measuring instrument like the judge, and it gets the same
treatment: its two numbers (triage agreement, false heal rate) are measured
against labels written before it ran, and the policy states what it may do
autonomously, what needs a human, and what it may never touch.

    python triage.py triage --builds ../../healer/red_builds.jsonl
    python triage.py heal   --builds ../../healer/red_builds.jsonl
    python triage.py review --report ../../gate_reference/report-red.json
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOLUTIONS = HERE.parent.parent

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MODEL = os.environ.get("TRIAGE_MODEL", "claude-haiku-4-5")

HYPOTHESES = ("real_defect", "stale_case", "flaky", "environment")
ACTIONS = ("fix_system", "fix_case", "move_layer", "rerun")

# --- the boundary -------------------------------------------------------
# Paths the healer may NEVER write to, whatever it proposes. These encode
# decisions a human made: the dataset is the definition of correct, specs are
# the requirement, ADRs are the record of why. An agent that edits its own
# marking scheme is not fixing anything.
FORBIDDEN_PATHS = ("evals/sets/", "specs/", "docs/adr", "ADR-",
                   "healer/red_builds.jsonl")

SYSTEM_TRIAGE = """You triage a failing CI check for an LLM quality gate.

You are given the failing case, the failure detail, and the evidence the run
recorded. Classify the failure into exactly one hypothesis:

  real_defect  the system's behaviour is wrong; the case is right
  stale_case   the system is right; the case encodes a stale or brittle
               expectation
  flaky        neither: the case is not deterministic enough for this layer
  environment  the run itself was broken, so the system was never tested

Rules you must follow:
- an independent oracle (engines_says) disagreeing with the system means
  real_defect, never stale_case;
- an answer that is correct but worded differently than the assertion expects
  means stale_case;
- verdicts that differ between runs with nothing else changing mean flaky;
- an error from the provider or a tool, or an answer saying a service was
  unavailable, means environment.

Action rules, which are NOT negotiable:
- environment -> rerun. The system was never tested, so test it.
- flaky       -> move_layer, NEVER rerun. Re-running a flaky case rolls the
                 same dice again; it teaches the team to re-run instead of to
                 investigate, and the gate loses its authority.
- stale_case  -> fix_case (a human applies it: the dataset is out of bounds).
- real_defect -> fix_system.

Reply with ONE line of JSON and nothing else:
{"hypothesis": "...", "action": "fix_system|fix_case|move_layer|rerun",
 "evidence": "<the field you used, quoted>", "confidence": "high|low"}"""

SYSTEM_HEAL = """You propose a fix for a failing CI check. You NEVER apply it.

You are given the failing case, the failure detail and a triage hypothesis.
Propose the smallest change that would make the check correct.

Hard boundary — you may not propose changes to:
  evals/sets/**   the dataset defines what correct means
  specs/**        the requirements
  any ADR         the record of why a decision was made
If the only fix you can see lies there, say so and set "needs_human": true.

Reply with ONE line of JSON and nothing else:
{"target": "<path or component>", "change": "<one sentence>",
 "needs_human": true|false, "risk": "<what this could break>"}"""

_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _ask(system: str, prompt: str) -> str:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
    payload = json.dumps({
        "model": MODEL, "max_tokens": 400, "temperature": 0,
        "system": system,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages", data=payload,
        headers={"Content-Type": "application/json", "x-api-key": key,
                 "anthropic-version": "2023-06-01"})
    delay = 2.0
    for attempt in range(4):
        try:
            with _opener.open(req, timeout=60) as r:
                data = json.loads(r.read().decode("utf-8"))
                return "".join(b.get("text", "") for b in data.get("content", []))
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 529) and attempt < 3:
                time.sleep(delay)
                delay *= 2
                continue
            raise RuntimeError(f"triage {e.code}: "
                               f"{e.read().decode('utf-8')[:200]}") from e
    raise RuntimeError("triage agent unreachable")


def _json_line(raw: str) -> dict:
    match = re.search(r"\{.*\}", raw or "", re.S)
    if not match:
        raise ValueError(f"agent returned no JSON: {raw[:160]!r}")
    return json.loads(match.group(0))


def _describe(build: dict) -> str:
    return (f"CASE: {build['case_id']}\n"
            f"FAILURE: {build['failure_detail']}\n"
            f"EVIDENCE: {json.dumps(build['evidence'], ensure_ascii=False)}")


# --------------------------------------------------------------------------

def triage_one(build: dict) -> dict:
    out = _json_line(_ask(SYSTEM_TRIAGE, _describe(build)))
    hypothesis = out.get("hypothesis")
    if hypothesis not in HYPOTHESES:
        raise ValueError(f"unknown hypothesis {hypothesis!r}")
    if out.get("action") not in ACTIONS:
        raise ValueError(f"unknown action {out.get('action')!r}")
    # Measured miss RB-07: the agent classified a flaky case correctly and then
    # proposed `rerun`, which does not fix flakiness — it re-rolls the dice.
    # The rule lives here, not only in the prompt, so a model change cannot
    # quietly lose it.
    required = {"flaky": "move_layer", "environment": "rerun",
                "stale_case": "fix_case", "real_defect": "fix_system"}
    expected = required[hypothesis]
    if out["action"] != expected:
        out["action_overridden_from"] = out["action"]
        out["action"] = expected
    return out


def heal_one(build: dict, hypothesis: str) -> dict:
    prompt = _describe(build) + f"\nTRIAGE HYPOTHESIS: {hypothesis}"
    out = _json_line(_ask(SYSTEM_HEAL, prompt))
    target = str(out.get("target", ""))
    # The boundary is enforced in CODE, not by asking politely in the prompt.
    # A model that is merely told not to touch something eventually does.
    if any(bad in target for bad in FORBIDDEN_PATHS):
        out["blocked_by_boundary"] = True
        out["needs_human"] = True
    return out


def cmd_triage(args) -> int:
    builds = [json.loads(l) for l in
              Path(args.builds).read_text(encoding="utf-8").splitlines() if l.strip()]
    rows = []
    print(f"{'build':<8}{'label':<14}{'agent':<14}{'action':<12}{'ok'}")
    print("-" * 56)
    for b in builds:
        try:
            out = triage_one(b)
        except Exception as e:
            print(f"{b['id']:<8}ERROR {str(e)[:60]}")
            rows.append({**b, "agent": None, "agrees": False})
            continue
        agrees = out["hypothesis"] == b["label"]
        rows.append({"id": b["id"], "case_id": b["case_id"],
                     "label": b["label"], "correct_action": b["correct_action"],
                     "agent_hypothesis": out["hypothesis"],
                     "agent_action": out["action"],
                     "evidence": out.get("evidence", ""),
                     "confidence": out.get("confidence", ""),
                     "agrees": agrees,
                     "action_agrees": out["action"] == b["correct_action"]})
        print(f"{b['id']:<8}{b['label']:<14}{out['hypothesis']:<14}"
              f"{out['action']:<12}{'ok' if agrees else 'MISS'}")
    _write(args.out or SOLUTIONS / "healer" / "triage_result.json", rows)
    hits = sum(r["agrees"] for r in rows)
    print("-" * 56)
    print(f"triage agreement: {hits}/{len(rows)}")
    return 0


def cmd_heal(args) -> int:
    builds = [json.loads(l) for l in
              Path(args.builds).read_text(encoding="utf-8").splitlines() if l.strip()]
    proposals_dir = SOLUTIONS / "healer" / "proposals"
    proposals_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for b in builds:
        try:
            tri = triage_one(b)
            proposal = heal_one(b, tri["hypothesis"])
        except Exception as e:
            print(f"{b['id']}: ERROR {str(e)[:80]}")
            continue
        record = {"build": b["id"], "case_id": b["case_id"],
                  "hypothesis": tri["hypothesis"], "action": tri["action"],
                  "proposal": proposal,
                  "label": b["label"], "correct_action": b["correct_action"],
                  "generated_at": datetime.now(timezone.utc).isoformat()}
        (proposals_dir / f"{b['id']}.json").write_text(
            json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
        rows.append(record)
        flag = ("BLOCKED" if proposal.get("blocked_by_boundary")
                else ("human" if proposal.get("needs_human") else "auto"))
        print(f"{b['id']:<8}{tri['hypothesis']:<14}{flag:<9}"
              f"{str(proposal.get('target'))[:36]}")
    _write(SOLUTIONS / "healer" / "heal_result.json", rows)
    return 0


def cmd_review(args) -> int:
    """PR comment: a hypothesis, the evidence field it rests on, and a link.
    Never a bare 'this looks wrong'."""
    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    failing = [c for c in report["cases"] if not c["verdict"]["passed"]]
    six = {k: report.get(k) for k in
           ("prompt_version", "set_hash", "profile", "judge_model",
            "rubric_version", "elapsed")}
    lines = [f"**eval-gate: {report['passed']}/{report['total']}**", ""]
    lines.append("| field | value |")
    lines.append("|---|---|")
    for k, v in six.items():
        lines.append(f"| `{k}` | `{v}` |")
    lines.append("")
    if not failing:
        lines.append("No failing cases.")
    for case in failing:
        try:
            build = {"case_id": case["id"],
                     "failure_detail": case["verdict"]["detail"],
                     "evidence": six}
            out = triage_one(build)
            lines.append(
                f"- **{case['id']}** — hypothesis `{out['hypothesis']}`, "
                f"suggested `{out['action']}`.\n"
                f"  Evidence: {out.get('evidence', '')}\n"
                f"  Detail: `{case['verdict']['detail'][:160]}`")
        except Exception as e:
            lines.append(f"- **{case['id']}** — triage failed: {str(e)[:120]}")
    body = "\n".join(lines)
    out_path = SOLUTIONS / "healer" / "pr_comment.md"
    out_path.write_text(body + "\n", encoding="utf-8")
    print(body)
    print(f"\n-> {out_path.relative_to(SOLUTIONS)}")
    return 0


def _write(path, rows):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(rows, indent=2, ensure_ascii=False),
                          encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="mode", required=True)
    default_builds = SOLUTIONS / "healer" / "red_builds.jsonl"

    t = sub.add_parser("triage")
    t.add_argument("--builds", default=str(default_builds))
    t.add_argument("--out", default=None)
    t.set_defaults(func=cmd_triage)

    h = sub.add_parser("heal")
    h.add_argument("--builds", default=str(default_builds))
    h.set_defaults(func=cmd_heal)

    r = sub.add_parser("review")
    r.add_argument("--report", required=True)
    r.set_defaults(func=cmd_review)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
