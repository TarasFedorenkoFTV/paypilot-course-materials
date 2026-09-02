"""Score the triage agent (ДЗ14 criterion 3): two numbers with intervals,
a 2x2 matrix, a breakdown by hypothesis, and the misses spelled out.

    python score.py
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def wilson(hits: int, total: int, z: float = 1.96) -> tuple[float, float]:
    if total == 0:
        return (0.0, 0.0)
    p = hits / total
    denom = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denom
    margin = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denom
    return (max(0.0, centre - margin), min(1.0, centre + margin))


def pct(x: float) -> str:
    return f"{100 * x:.0f}%"


def main() -> int:
    triage = json.loads((HERE / "triage_result.json").read_text(encoding="utf-8"))
    heal = json.loads((HERE / "heal_result.json").read_text(encoding="utf-8"))
    by_id = {h["build"]: h for h in heal}

    n = len(triage)
    hyp_hits = sum(r["agrees"] for r in triage)
    act_hits = sum(r["action_agrees"] for r in triage)
    h_lo, h_hi = wilson(hyp_hits, n)
    a_lo, a_hi = wilson(act_hits, n)

    print("=== two numbers ===")
    print(f"triage agreement (hypothesis): {hyp_hits}/{n} = {pct(hyp_hits/n)} "
          f"[{pct(h_lo)}..{pct(h_hi)}]")
    print(f"action agreement:              {act_hits}/{n} = {pct(act_hits/n)} "
          f"[{pct(a_lo)}..{pct(a_hi)}]")

    # what the healer would have applied on its own
    auto = [h for h in heal
            if not h["proposal"].get("needs_human")
            and not h["proposal"].get("blocked_by_boundary")]
    # an autonomous application is WRONG when the correct action was not
    # fix_system: rerunning, moving a layer or editing a case are all things
    # the healer must not do to the code
    false_heals = [h for h in auto if h["correct_action"] != "fix_system"]
    f_lo, f_hi = wilson(len(false_heals), max(1, len(auto)))
    rate = len(false_heals) / len(auto) if auto else 0.0
    print(f"false heal rate:               {len(false_heals)}/{len(auto)} = "
          f"{pct(rate)} [{pct(f_lo)}..{pct(f_hi)}]"
          + ("   (interval is wide: the autonomous surface is tiny)"
             if len(auto) < 5 else ""))

    print("\n=== 2x2: what the healer did vs what was correct ===")
    rows = {"auto": {"fix_system": 0, "other": 0},
            "escalated": {"fix_system": 0, "other": 0}}
    for h in heal:
        did = ("auto" if not h["proposal"].get("needs_human")
               and not h["proposal"].get("blocked_by_boundary") else "escalated")
        want = "fix_system" if h["correct_action"] == "fix_system" else "other"
        rows[did][want] += 1
    print(f"{'':<12}{'correct: fix_system':<22}{'correct: other'}")
    for did in ("auto", "escalated"):
        print(f"{did:<12}{rows[did]['fix_system']:<22}{rows[did]['other']}")
    print("\n  auto + other        = a false heal (the dangerous cell)")
    print("  escalated + fix_sys = a missed opportunity (the cheap cell)")

    print("\n=== by hypothesis ===")
    print(f"{'hypothesis':<14}{'n':<4}{'hyp ok':<8}{'action ok':<11}"
          f"{'auto':<6}{'blocked'}")
    for hyp in ("real_defect", "stale_case", "flaky", "environment"):
        sub = [r for r in triage if r["label"] == hyp]
        if not sub:
            continue
        ids = {r["id"] for r in sub}
        autos = sum(1 for h in heal if h["build"] in ids
                    and not h["proposal"].get("needs_human")
                    and not h["proposal"].get("blocked_by_boundary"))
        blocked = sum(1 for h in heal if h["build"] in ids
                      and h["proposal"].get("blocked_by_boundary"))
        print(f"{hyp:<14}{len(sub):<4}"
              f"{sum(r['agrees'] for r in sub):<8}"
              f"{sum(r['action_agrees'] for r in sub):<11}{autos:<6}{blocked}")

    print("\n=== misses ===")
    misses = [r for r in triage if not r["agrees"] or not r["action_agrees"]]
    if not misses:
        print("  none")
    for r in misses:
        kind = ("hypothesis" if not r["agrees"] else "action")
        print(f"  {r['id']} ({kind}): label {r['label']}/"
              f"{r['correct_action']} vs agent {r['agent_hypothesis']}/"
              f"{r['agent_action']}")
        prop = by_id.get(r["id"], {}).get("proposal", {})
        if prop:
            print(f"      proposed: {str(prop.get('target'))[:60]} "
                  f"(needs_human={prop.get('needs_human')})")

    record = {
        "cases": n,
        "triage_agreement": {"hits": hyp_hits, "pct": round(100 * hyp_hits / n),
                             "ci": [round(100 * h_lo), round(100 * h_hi)]},
        "action_agreement": {"hits": act_hits, "pct": round(100 * act_hits / n),
                             "ci": [round(100 * a_lo), round(100 * a_hi)]},
        "false_heal_rate": {"hits": len(false_heals), "of": len(auto),
                            "pct": round(100 * rate),
                            "ci": [round(100 * f_lo), round(100 * f_hi)]},
        "matrix": rows,
    }
    (HERE / "score.json").write_text(
        json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\n-> score.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
