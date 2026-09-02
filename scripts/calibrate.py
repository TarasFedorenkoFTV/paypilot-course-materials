"""Calibration & acceptance harness (ТЗ §5.8 determinism, §10.2 acceptance).

For every defect scenario: run the reproduction N times with the defect on
(its profile) and N times on clean, detect firing each run, and report the
measured frequency next to the declared mode.

  deterministic  -> expect fired==N on the profile arm, 0 on clean
  probabilistic  -> the measured frequency must land inside the corridor
                    declared in profiles/corridors.yaml BEFORE the run, and
                    firing on clean is always a failure.

The profile arm really switches the lesson profile (set_runtime_profile), so
what is accepted is the configuration a student actually receives — including
the other defects that profile carries. Measuring one defect in isolation on
clean answers a different question than ТЗ 10.2 asks.

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

import yaml  # noqa: E402

from app import clock, config, db, defects, tracing  # noqa: E402
from app.agent import loop  # noqa: E402

# Windows consoles default to cp1252: any non-ASCII in the output kills the run
# with UnicodeEncodeError before the verdict is printed. Force UTF-8.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

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


_PROFILES = yaml.safe_load((ROOT / "profiles" / "profiles.yaml").read_text(
    encoding="utf-8"))["profiles"]

_corridor_file = ROOT / "profiles" / "corridors.yaml"
CORRIDORS = yaml.safe_load(_corridor_file.read_text(encoding="utf-8"))["corridors"]
CORRIDORS_FROZEN_AT = yaml.safe_load(
    _corridor_file.read_text(encoding="utf-8"))["frozen_at"]


def profile_for(scenario) -> str | None:
    """The lesson profile this defect is accepted on, or None if it has no
    profile of its own (D02, D18 and the combination scenarios)."""
    if scenario.get("profile"):
        return scenario["profile"]
    if scenario.get("activate"):
        return None            # explicit multi-defect activation wins
    hits = [p for p, ds in _PROFILES.items() if scenario["defect"] in ds]
    return hits[0] if len(hits) == 1 else None


def run_once(scenario, defect_on: bool) -> bool:
    db.reset()
    loop.reset_sessions()
    clock.set_override(None)
    prof = profile_for(scenario)
    if not defect_on:
        defects.set_runtime_profile("clean")
        defects.set_runtime_defects("")
    elif prof:
        # the real thing: the lesson profile, with everything it carries
        defects.set_runtime_profile(prof)
        defects.set_runtime_defects("")
    else:
        defects.set_runtime_profile("clean")
        defects.set_runtime_defects(",".join(
            scenario.get("activate") or [scenario["defect"]]))

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
        defects.set_runtime_profile("clean")


def calibrate(scenario, nprob, ndet, run_id: str) -> dict:
    did = scenario["defect"]
    n = ndet if scenario["declared"] == "deterministic" else nprob
    prof = profile_for(scenario)
    arm = f"profile:{prof}" if prof else (
        "defects:" + ",".join(scenario.get("activate") or [did]))

    fired_profile = sum(run_once(scenario, True) for _ in range(n))
    fired_clean = sum(run_once(scenario, False) for _ in range(n))
    freq_pct = round(fired_profile / n * 100, 1)

    corridor = None
    if scenario["declared"] == "deterministic":
        ok = fired_profile == n and fired_clean == 0
        verdict = "N/N on arm, 0/N on clean"
    else:
        c = CORRIDORS.get(did)
        if c is None:
            # No pre-declared corridor means there is nothing to accept
            # against. Refusing is the point: declaring one now would be the
            # after-the-fact threshold this file exists to prevent.
            ok = False
            verdict = "NO DECLARED CORRIDOR — add it to profiles/corridors.yaml"
        else:
            corridor = [c["low_pct"], c["high_pct"]]
            ok = (c["low_pct"] <= freq_pct <= c["high_pct"]) and fired_clean == 0
            verdict = f"corridor {c['low_pct']}-{c['high_pct']}%"

    return {"defect": did, "declared": scenario["declared"],
            "runs": n, "fired_profile": fired_profile, "fired_clean": fired_clean,
            "frequency_pct": freq_pct,
            "arm": arm, "profile": prof,
            "corridor_pct": corridor, "criterion": verdict,
            "isolation_ok": fired_clean == 0, "accept": ok,
            "measured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "run_id": run_id}


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

    run_id = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    print(f"Provider: {config.LLM_PROVIDER}  model: {config.LLM_MODEL or 'default'}")
    print(f"run_id={run_id}  nprob={args.nprob} ndet={args.ndet}  "
          f"scenarios={len(selected)}")
    print(f"corridors frozen at {CORRIDORS_FROZEN_AT} "
          f"({len(CORRIDORS)} probabilistic declared)" + chr(10))
    print(f"{'defect':<7}{'mode':<15}{'arm':<22}{'runs':<6}{'fired':<7}"
          f"{'clean':<7}{'freq%':<8}{'accept'}")
    print("-" * 88)

    results = []
    t0 = time.time()
    aborted = None
    for s in selected:
        try:
            r = calibrate(s, args.nprob, args.ndet, run_id)
        except Exception as e:
            # A provider outage or an exhausted balance must not throw away the
            # defects already measured: stop, keep them, and say why.
            aborted = f"{s['defect']}: {type(e).__name__}: {str(e)[:200]}"
            print("")
            print("!! aborted on " + aborted)
            break
        results.append(r)
        flag = "OK" if r["accept"] else ("ISO!" if not r["isolation_ok"] else "OUT")
        print(f"{r['defect']:<7}{r['declared']:<15}{r['arm']:<22}{r['runs']:<6}"
              f"{r['fired_profile']:<7}{r['fired_clean']:<7}"
              f"{r['frequency_pct']:<8}{flag}")

    elapsed = round(time.time() - t0, 1)
    accepted = sum(r["accept"] for r in results)
    print("-" * 60)
    print(f"accepted {accepted}/{len(results)}   elapsed {elapsed}s")

    # A mock run must never touch the real acceptance evidence. Before this
    # guard, `LLM_PROVIDER=mock python scripts/calibrate.py` silently merged
    # meaningless rows into docs/calibration-report.json — the file the whole
    # acceptance argument rests on.
    if config.LLM_PROVIDER == "mock":
        out = ROOT / "docs" / "calibration-report.mock.json"
        print("provider is mock -> writing to calibration-report.mock.json; "
              "the real report is left untouched")
    else:
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

    # Provenance, because the header used to describe only the last partial run
    # while the results spanned several. A reader could not tell "24/24 in one
    # pass" from "24 defects glued together over a week", and the acceptance
    # review could not either.
    rows = [merged[k] for k in sorted(merged)]
    run_ids = sorted({r.get("run_id", "pre-provenance") for r in rows})
    from_this_run = sum(1 for r in rows if r.get("run_id") == run_id)
    arms = sorted({r.get("arm", "?").split(":")[0] for r in rows})
    out.write_text(json.dumps(
        {"provider": config.LLM_PROVIDER, "model": config.LLM_MODEL or "default",
         "corridors_frozen_at": CORRIDORS_FROZEN_AT,
         "this_run": {"run_id": run_id, "nprob": args.nprob, "ndet": args.ndet,
                      "elapsed_s": elapsed, "defects_measured": len(results),
                      "aborted": aborted},
         "provenance": {
             "single_pass": len(run_ids) == 1 and from_this_run == len(rows),
             "defects_in_report": len(rows),
             "measured_in_this_run": from_this_run,
             "carried_over_from_earlier_runs": len(rows) - from_this_run,
             "run_ids": run_ids,
             "arms_used": arms,
             "note": ("Every row carries its own run_id, arm and measured_at. "
                      "Rows not measured in this run are carried over and are "
                      "only as current as their own timestamp.")},
         "results": rows}, indent=2),
        encoding="utf-8")
    stale = len(rows) - from_this_run
    print(f"report -> {out}  ({len(rows)} defects total)")
    if stale:
        print(f"!! {stale} of {len(rows)} rows were NOT measured in this run "
              f"(carried over). This report is a merge, not a single pass.")
    else:
        print(f"single pass: all {len(rows)} rows measured in run {run_id}.")
    if aborted:
        print("Run was cut short — re-run the remaining defects once the "
              "provider is available again.")
        sys.exit(2)


if __name__ == "__main__":
    main()
