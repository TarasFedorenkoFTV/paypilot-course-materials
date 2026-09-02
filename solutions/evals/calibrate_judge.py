"""Measure the judge before anything depends on it (ДЗ9).

Two numbers, and they answer different questions:

  self-consistency  does the judge agree with ITSELF across N runs of the same
                    case? A judge that flips its own verdict cannot be trusted
                    even when it happens to be right.
  agreement         does the judge agree with the human label? Reported with a
                    confidence interval, because 30 cases is a small sample and
                    a bare percentage invites over-reading.

Both are reported with a Wilson interval and broken down by thirds
(clear-PASS / clear-FAIL / disputed) so a systematic bias is visible rather
than averaged away.

    JUDGE_MODEL=claude-haiku-4-5 python calibrate_judge.py
    JUDGE_BACKEND=ollama JUDGE_MODEL=qwen2.5:7b python calibrate_judge.py
"""
import json
import math
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from judge import judge  # noqa: E402
from loader import load  # noqa: E402

SETS = HERE / "sets"
REPORTS = HERE / "reports"
MODEL = os.environ.get("JUDGE_MODEL", "claude-haiku-4-5")
RUNS = int(os.environ.get("JUDGE_RUNS", "5"))


def wilson(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval — honest at small n, unlike the normal
    approximation which can put a bound above 100%."""
    if total == 0:
        return (0.0, 0.0)
    p = successes / total
    denom = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denom
    margin = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denom
    return (max(0.0, centre - margin), min(1.0, centre + margin))


def pct(x: float) -> str:
    return f"{100 * x:.1f}%"


def main() -> int:
    cases = load(SETS / "l09_labels.jsonl")
    print(f"judge {MODEL}   {len(cases)} cases x {RUNS} runs\n")
    print(f"{'case':<10}{'label':<7}{'majority':<10}{'runs':<12}{'agree'}")
    print("-" * 56)

    rows, t0 = [], time.time()
    for case in cases:
        meta = case["additional_metadata"]
        verdicts = []
        for _ in range(RUNS):
            try:
                v = judge(case["input"], case["answer_under_test"],
                          meta["rubric"], MODEL)["verdict"]
            except Exception as e:
                print(f"  judge error on {case['id']}: {str(e)[:120]}")
                v = "ERROR"
            verdicts.append(v)
        majority = max(set(verdicts), key=verdicts.count)
        self_consistent = verdicts.count(majority) == RUNS
        agrees = majority == meta["label"]
        rows.append({
            "id": case["id"], "label": meta["label"], "majority": majority,
            "verdicts": verdicts, "self_consistent": self_consistent,
            "agrees": agrees, "disputed": bool(meta.get("disputed")),
            "criterion": meta["criterion"],
        })
        print(f"{case['id']:<10}{meta['label']:<7}{majority:<10}"
              f"{''.join(v[0] for v in verdicts):<12}"
              f"{'ok' if agrees else 'MISS'}")

    elapsed = round(time.time() - t0, 1)
    n = len(rows)
    agree_n = sum(r["agrees"] for r in rows)
    consist_n = sum(r["self_consistent"] for r in rows)
    a_lo, a_hi = wilson(agree_n, n)
    c_lo, c_hi = wilson(consist_n, n)

    def slice_stats(pred, name):
        sub = [r for r in rows if pred(r)]
        if not sub:
            return f"  {name:<16} —"
        hits = sum(r["agrees"] for r in sub)
        lo, hi = wilson(hits, len(sub))
        return (f"  {name:<16} {hits}/{len(sub)} = {pct(hits/len(sub))} "
                f"[{pct(lo)}..{pct(hi)}]")

    print("-" * 56)
    print(f"agreement with the human label: {agree_n}/{n} = "
          f"{pct(agree_n/n)}  [{pct(a_lo)}..{pct(a_hi)}]")
    print(f"self-consistency ({RUNS}/{RUNS} identical): {consist_n}/{n} = "
          f"{pct(consist_n/n)}  [{pct(c_lo)}..{pct(c_hi)}]")
    print("\nby third:")
    print(slice_stats(lambda r: not r["disputed"] and r["label"] == "PASS",
                      "clear PASS"))
    print(slice_stats(lambda r: not r["disputed"] and r["label"] == "FAIL",
                      "clear FAIL"))
    print(slice_stats(lambda r: r["disputed"], "disputed"))

    misses = [r for r in rows if not r["agrees"]]
    if misses:
        print("\nmisses (where the judge and the human disagree):")
        for r in misses:
            direction = ("false PASS" if r["majority"] == "PASS"
                         else "false FAIL")
            print(f"  {r['id']:<10} {direction:<11} "
                  f"{'disputed' if r['disputed'] else 'clear':<9} "
                  f"{r['criterion'][:60]}")

    record = {
        "judge_model": MODEL, "rubric_version": "rubric.v1",
        "runs_per_case": RUNS, "cases": n, "elapsed": elapsed,
        "ran_at": datetime.now(timezone.utc).isoformat(),
        "agreement": {"hits": agree_n, "pct": round(100 * agree_n / n, 1),
                      "ci": [round(100 * a_lo, 1), round(100 * a_hi, 1)]},
        "self_consistency": {"hits": consist_n,
                             "pct": round(100 * consist_n / n, 1),
                             "ci": [round(100 * c_lo, 1), round(100 * c_hi, 1)]},
        "rows": rows,
    }
    REPORTS.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    safe_model = MODEL.replace(":", "-").replace("/", "-")
    out = REPORTS / f"judge-{safe_model}-{stamp}.json"
    out.write_text(json.dumps(record, indent=2, ensure_ascii=False),
                   encoding="utf-8")
    print(f"\nreport -> {out.relative_to(HERE)}   elapsed {elapsed}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
