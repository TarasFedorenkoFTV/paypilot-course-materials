"""Run both test sets against the fixed mutant list (L11).

Each mutant is applied to a COPY of app/engines/fx.py, both suites run against
it, and the file is restored. A mutant is "killed" when the suite fails.

    python run_mutants.py

Writes mutation_results.json and prints the breakdown by class, because a
single mutation score hides which KIND of bug a suite is blind to.
"""
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
TARGET = ROOT / "app" / "engines" / "fx.py"
BACKUP = HERE / "_fx_original.py"

sys.path.insert(0, str(HERE))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from mutants import CLASSES, FIXED_ON, MUTANTS  # noqa: E402

SUITES = {"manual": HERE / "manual", "generated": HERE / "generated"}
PYTHON = str(ROOT / ".venv" / "Scripts" / "python.exe")
if not Path(PYTHON).exists():
    PYTHON = sys.executable


def run_suite(path: Path) -> bool:
    """True when the suite passes (i.e. the mutant SURVIVED)."""
    proc = subprocess.run(
        [PYTHON, "-m", "pytest", str(path), "-q", "--no-header", "-x"],
        cwd=str(ROOT), capture_output=True, text=True,
        env={**__import__("os").environ,
             "PYTHONPATH": str(ROOT), "LLM_PROVIDER": "mock",
             "CLOCK_OVERRIDE": "2026-09-15T10:00:00Z"})
    return proc.returncode == 0


def main() -> int:
    original = TARGET.read_text(encoding="utf-8")
    shutil.copyfile(TARGET, BACKUP)

    # a mutant that does not apply is a broken mutant, not a survived one
    unusable = [m[0] for m in MUTANTS if m[3] not in original]
    if unusable:
        print(f"these mutants no longer match the source: {unusable}")
        print("fx.py changed since the list was fixed — fix the list "
              "deliberately and date it, do not edit it to fit the result.")
        return 2

    print(f"mutant list fixed on {FIXED_ON}   {len(MUTANTS)} mutants "
          f"x {len(SUITES)} suites\n")
    print(f"{'id':<5}{'class':<12}{'manual':<9}{'generated':<11}description")
    print("-" * 88)

    rows, t0 = [], time.time()
    try:
        for mid, cls, desc, find, replace in MUTANTS:
            TARGET.write_text(original.replace(find, replace, 1),
                              encoding="utf-8")
            killed = {}
            for name, path in SUITES.items():
                killed[name] = not run_suite(path)
            rows.append({"id": mid, "class": cls, "description": desc,
                         **{f"killed_by_{k}": v for k, v in killed.items()}})
            print(f"{mid:<5}{cls:<12}"
                  f"{('killed' if killed['manual'] else 'SURVIVED'):<9}"
                  f"{('killed' if killed['generated'] else 'SURVIVED'):<11}"
                  f"{desc[:44]}")
    finally:
        TARGET.write_text(original, encoding="utf-8")
        BACKUP.unlink(missing_ok=True)

    elapsed = round(time.time() - t0, 1)
    total = len(rows)
    scores = {name: sum(r[f"killed_by_{name}"] for r in rows)
              for name in SUITES}

    print("-" * 88)
    for name, score in scores.items():
        print(f"{name:<10} mutation score {score}/{total} = "
              f"{100 * score / total:.0f}%")

    print("\nby class:")
    print(f"{'class':<12}{'n':<4}{'manual':<9}{'generated'}")
    by_class = {}
    for cls in CLASSES:
        sub = [r for r in rows if r["class"] == cls]
        if not sub:
            continue
        m = sum(r["killed_by_manual"] for r in sub)
        g = sum(r["killed_by_generated"] for r in sub)
        by_class[cls] = {"n": len(sub), "manual": m, "generated": g}
        print(f"{cls:<12}{len(sub):<4}{m}/{len(sub):<7}{g}/{len(sub)}")

    only_manual = [r["id"] for r in rows
                   if r["killed_by_manual"] and not r["killed_by_generated"]]
    only_generated = [r["id"] for r in rows
                      if r["killed_by_generated"] and not r["killed_by_manual"]]
    neither = [r["id"] for r in rows
               if not r["killed_by_manual"] and not r["killed_by_generated"]]
    print(f"\nkilled only by manual:    {only_manual or '-'}")
    print(f"killed only by generated: {only_generated or '-'}")
    print(f"survived both:            {neither or '-'}")

    record = {"fixed_on": FIXED_ON, "mutants": total, "elapsed": elapsed,
              "scores": scores, "by_class": by_class,
              "only_manual": only_manual, "only_generated": only_generated,
              "survived_both": neither, "rows": rows}
    (HERE / "mutation_results.json").write_text(
        json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n-> mutation_results.json   elapsed {elapsed}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
