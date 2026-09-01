"""Calibration & acceptance harness (ТЗ §5.8 determinism, §10.2 acceptance).

For every defect scenario: run the reproduction N times with the defect on
(its profile) and N times on clean, detect firing each run, and report the
measured frequency next to the declared mode.

  deterministic  -> expect fired==N on profile, 0 on clean
  probabilistic  -> measured frequency on profile is the declared corridor
                    (declared after the fact), and must be 0 on clean; a
                    defect firing below 30% is not acceptable.

Usage:
  python scripts/calibrate.py                 # all scenarios
  python scripts/calibrate.py --only D06,D25  # a subset
  python scripts/calibrate.py --nprob 20 --ndet 5
Writes docs/calibration-report.json.
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# load .env
env_file = ROOT / ".env"
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

os.environ.setdefault("CLOCK_OVERRIDE", "2026-09-15T10:00:00Z")

from app import clock, config, db, defects, tracing  # noqa: E402
from app.agent import loop  # noqa: E402
from scripts.scenarios import SCENARIOS, SCENARIOS_BY_ID  # noqa: E402


class RunResult:
    def __init__(self):
        self.traces = []
        self.answers = []
        self.last_question = ""

    @property
    def final(self):
        return self.answers[-1] if self.answers else ""

    def state(self, table):
        return db.table_dump(table)


def run_once(scenario, defect_on: bool) -> bool:
    db.reset()
    loop.reset_sessions()
    clock.set_override(None)
    activation = scenario.get("activate") or [scenario["defect"]]
    defects.set_runtime_defects(",".join(activation) if defect_on else "")

    saved = {}
    for k, v in scenario.get("env", {}).items():
        saved[k] = getattr(config, k)
        setattr(config, k, v)
    try:
        rr = RunResult()
        sid = None
        for turn in scenario["turns"]:
            rr.last_question = turn
            out = loop.run_turn(sid, turn)
            sid = out["session_id"]
            rr.answers.append(out["answer"])
            rr.traces.append(tracing.get(out["request_id"]))
        return bool(scenario["detect"](rr))
    finally:
        for k, v in saved.items():
            setattr(config, k, v)
        defects.set_runtime_defects("")


def calibrate(scenario, nprob, ndet) -> dict:
    n = ndet if scenario["declared"] == "deterministic" else nprob
    fired_profile = sum(run_once(scenario, True) for _ in range(n))
    fired_clean = sum(run_once(scenario, False) for _ in range(n))
    freq = fired_profile / n
    if scenario["declared"] == "deterministic":
        ok = fired_profile == n and fired_clean == 0
    else:
        ok = freq >= 0.30 and fired_clean == 0
    return {"defect": scenario["defect"], "declared": scenario["declared"],
            "runs": n, "fired_profile": fired_profile, "fired_clean": fired_clean,
            "frequency_pct": round(freq * 100, 1),
            "isolation_ok": fired_clean == 0, "accept": ok}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--nprob", type=int, default=10)
    ap.add_argument("--ndet", type=int, default=5)
    args = ap.parse_args()

    selected = SCENARIOS
    if args.only:
        ids = {x.strip().upper() for x in args.only.split(",")}
        selected = [s for s in SCENARIOS if s["defect"] in ids]

    print(f"Provider: {config.LLM_PROVIDER}  model: {config.LLM_MODEL or 'default'}")
    print(f"nprob={args.nprob} ndet={args.ndet}  scenarios={len(selected)}\n")
    print(f"{'defect':<7}{'mode':<15}{'runs':<6}{'profile':<9}{'clean':<7}"
          f"{'freq%':<8}{'accept'}")
    print("-" * 60)

    results = []
    t0 = time.time()
    aborted = None
    for s in selected:
        try:
            r = calibrate(s, args.nprob, args.ndet)
        except Exception as e:
            # A provider outage or an exhausted balance must not throw away the
            # defects already measured: stop, keep them, and say why.
            aborted = f"{s['defect']}: {type(e).__name__}: {str(e)[:200]}"
            print("")
            print("!! aborted on " + aborted)
            break
        results.append(r)
        flag = "OK" if r["accept"] else ("ISO!" if not r["isolation_ok"] else "LOW")
        print(f"{r['defect']:<7}{r['declared']:<15}{r['runs']:<6}"
              f"{r['fired_profile']:<9}{r['fired_clean']:<7}"
              f"{r['frequency_pct']:<8}{flag}")

    elapsed = round(time.time() - t0, 1)
    accepted = sum(r["accept"] for r in results)
    print("-" * 60)
    print(f"accepted {accepted}/{len(results)}   elapsed {elapsed}s")

    out = ROOT / "docs" / "calibration-report.json"
    merged = {}
    if out.exists():
        try:
            prev = json.loads(out.read_text(encoding="utf-8"))
            merged = {r["defect"]: r for r in prev.get("results", [])}
        except (ValueError, KeyError):
            merged = {}
    for r in results:                     # newer partial runs override per defect
        merged[r["defect"]] = r
    out.write_text(json.dumps(
        {"provider": config.LLM_PROVIDER, "model": config.LLM_MODEL or "default",
         "nprob": args.nprob, "ndet": args.ndet, "elapsed_s": elapsed,
         "results": [merged[k] for k in sorted(merged)]}, indent=2),
        encoding="utf-8")
    print(f"report -> {out}  ({len(merged)} defects total)")
    if aborted:
        print("Run was cut short — re-run the remaining defects once the "
              "provider is available again.")
        sys.exit(2)


if __name__ == "__main__":
    main()
