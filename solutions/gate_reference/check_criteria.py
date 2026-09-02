"""Check the ДЗ13 gate criteria mechanically.

Written because the first version of this check produced two false positives,
and a criteria check that cries wolf is worse than none:

  * it matched `continue-on-error` inside a COMMENT that says the workflow has
    none — comments are excluded now;
  * it flagged `ANTHROPIC_API_KEY` in the release job as a cloud-judge secret.
    That key belongs to the STAND (the agent under test needs a provider); the
    judge secret is a different thing. The two are separated now, and what the
    perimeter does not cover is stated in gate-policy section 5 instead of
    being hidden by a green check.

    python check_criteria.py
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVALS = HERE.parent / "evals"
sys.path.insert(0, str(EVALS))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from loader import load  # noqa: E402

SIX_FIELDS = ("prompt_version", "set_hash", "profile", "judge_model",
              "rubric_version", "elapsed")
# secrets that would mean the judge itself runs in the cloud
JUDGE_SECRETS = ("OPENAI_API_KEY", "JUDGE_API_KEY", "ANTHROPIC_JUDGE")

results = []


def check(num: str, label: str, ok: bool, detail: str = "") -> None:
    results.append((num, label, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {num}. {label}"
          + (f" — {detail}" if detail else ""))


def code_lines(text: str) -> list[str]:
    """Workflow lines with comments stripped: a comment that mentions
    `continue-on-error` is documentation, not configuration."""
    out = []
    for line in text.splitlines():
        stripped = line.split("#", 1)[0].rstrip()
        if stripped.strip():
            out.append(stripped)
    return out


def job_block(lines: list[str], name: str) -> list[str]:
    """The lines belonging to one job, by indentation."""
    out, inside = [], False
    for line in lines:
        if line.strip().startswith(f"{name}:") and line.startswith("  "):
            inside = True
            continue
        if inside:
            if line.startswith("  ") and not line.startswith("   ") \
                    and line.strip().endswith(":"):
                break            # the next job at the same level
            out.append(line)
    return out


def main() -> int:
    wf = (HERE / "eval-gate.yml").read_text(encoding="utf-8")
    lines = code_lines(wf)
    cases = load(EVALS / "sets" / "l03_reference.jsonl")
    green = json.loads((HERE / "report-green.json").read_text(encoding="utf-8"))
    red = json.loads((HERE / "report-red.json").read_text(encoding="utf-8"))

    # 1 — the red case belongs to the student's own set
    failed = [c["id"] for c in red["cases"] if not c["verdict"]["passed"]]
    own = {c["id"] for c in cases}
    check("1", "the red case comes from the own set",
          bool(failed) and all(f in own for f in failed),
          f"red on {failed}")

    # 2 — integration by exit code only
    banned = [t for t in ("continue-on-error", "|| true", "grep ")
              if any(t in line for line in lines)]
    check("2", "no continue-on-error, no `|| true`, no log parsing",
          not banned, "" if not banned else f"found {banned}")
    check("2b", "the report is uploaded even on failure",
          any("if: always()" in line for line in lines))

    # 3 — two layers split by the `gate` field
    daily = [c for c in cases
             if c["additional_metadata"].get("gate", "daily") == "daily"]
    offenders = [c["id"] for c in daily
                 if c["additional_metadata"].get("runs", 1) > 1
                 or c["additional_metadata"]["assertion"] == "judge"]
    check("3", "daily carries no runs>1 and no judge cases",
          not offenders, f"{len(daily)} daily cases"
          if not offenders else f"offenders: {offenders}")
    release_block = job_block(lines, "release")
    check("3b", "release is not triggered by a pull request",
          any("github.event_name == 'push'" in line for line in release_block)
          or any("inputs.layer" in line for line in release_block))

    # 4 — the run record carries the six fields, and the pair is comparable
    missing = [k for k in SIX_FIELDS if k not in green or k not in red]
    check("4", "both records carry the six version fields", not missing,
          "" if not missing else f"missing {missing}")
    check("4b", "set_hash matches across the pair",
          green["set_hash"] == red["set_hash"], green["set_hash"])

    # 5 — the gate policy exists and answers all nine lines
    policy = (HERE.parent / "docs" / "gate-policy.reference.md").read_text(
        encoding="utf-8")
    headings = [ln for ln in policy.splitlines() if ln.startswith("## ")]
    check("5", "the gate policy has all nine lines", len(headings) == 9,
          f"{len(headings)} headings")
    check("5b", "the mandate line names the opposite case",
          "Don't break it" in policy and "Ship it" in policy)

    # 6 — the judge perimeter: the JUDGE is local; the stand's own provider
    #     key is a separate matter and is named in policy section 5
    leaked = [s for s in JUDGE_SECRETS
              if any(s in line for line in release_block)]
    check("6", "no cloud-judge secret in the release job", not leaked,
          "" if not leaked else f"found {leaked}")
    check("6b", "the release judge is local",
          any("JUDGE_BACKEND: ollama" in line for line in release_block))

    failures = [r for r in results if not r[2]]
    print()
    print(f"{len(results) - len(failures)}/{len(results)} criteria pass")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
