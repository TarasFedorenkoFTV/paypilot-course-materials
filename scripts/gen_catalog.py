"""Generate docs/defect-catalog.md from the registry, profiles and the
measured calibration report (ТЗ §9). One row per defect: mechanism, location,
determinism mode + measured frequency, profiles it is active in, reproduction
scenario, and where the effect is visible."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402
from scripts.scenarios import SCENARIOS_BY_ID  # noqa: E402

REGISTRY = yaml.safe_load((ROOT / "profiles" / "defects.yaml").read_text(
    encoding="utf-8"))["defects"]
PROFILES = yaml.safe_load((ROOT / "profiles" / "profiles.yaml").read_text(
    encoding="utf-8"))["profiles"]

report_path = ROOT / "docs" / "calibration-report.json"
REPORT = {}
if report_path.exists():
    REPORT = {r["defect"]: r
              for r in json.loads(report_path.read_text(encoding="utf-8"))["results"]}

# where the effect is observable, per defect
SURFACE = {
    "D01": "text", "D02": "prompt document", "D03": "text", "D04": "text",
    "D05": "text", "D06": "text + trace (summary span)", "D07": "text",
    "D08": "text", "D09": "text + tool result", "D10": "DB (statements_sent)",
    "D11": "DB (disputes.currency)", "D12": "DB (disputes.account_id)",
    "D13": "trace (tool call order)", "D14": "trace (repeated spans)",
    "D15": "trace (input tokens grow)", "D16": "trace (retrieval.index)",
    "D17": "trace (retrieval.fragments)", "D18": "fixtures (judge pairs)",
    "D19": "text + tool args", "D20": "text", "D22": "text + tool result",
    "D21": "text + tool result (spread_amount)", "D23": "text (multi-turn)",
    "D24": "text", "D25": "text", "D26": "text",
    "D27": "trace (absence of escalate span)",
}


def profiles_for(did):
    return [p for p, ds in PROFILES.items() if did in ds] or ["—"]


def freq_cell(did):
    r = REPORT.get(did)
    if not r:
        return "not yet measured"
    if r["declared"] == "deterministic":
        base = f"deterministic — {r['fired_profile']}/{r['runs']} profile, {r['fired_clean']}/{r['runs']} clean"
    else:
        base = f"probabilistic — {r['frequency_pct']}% ({r['fired_profile']}/{r['runs']}), clean {r['fired_clean']}/{r['runs']}"
    return base + ("  ✅" if r["accept"] else "  ⚠️ needs work")


def repro_for(did):
    sc = SCENARIOS_BY_ID.get(did)
    if not sc:
        return "—"
    act = sc.get("activate")
    prefix = f"(activate {','.join(act)}) " if act else ""
    turns = " → ".join(f'"{t}"' for t in sc["turns"])
    return prefix + turns


def main():
    lines = ["# PayPilot — каталог дефектів", "",
             "Автогенеровано з `profiles/defects.yaml`, `profiles/profiles.yaml` "
             "і `docs/calibration-report.json`. Оновлювати: "
             "`python scripts/gen_catalog.py`.", ""]
    if REPORT:
        acc = sum(1 for r in REPORT.values() if r["accept"])
        lines += [f"Заміряно: **{len(REPORT)} дефектів**, приймається "
                  f"**{acc}/{len(REPORT)}**. Провайдер: "
                  f"{json.loads(report_path.read_text(encoding='utf-8')).get('model','?')}.",
                  ""]
    for did in sorted(REGISTRY):
        d = REGISTRY[did]
        lines += [
            f"## {did} — {d['title']}",
            f"- **Механізм:** {d['mechanism']}",
            f"- **Місце:** {d['layer']}",
            f"- **Ітерація:** {d['iteration']}   **Статус реалізації:** {d['status']}",
            f"- **Режим і заміряна частота:** {freq_cell(did)}",
            f"- **Активний у профілях:** {', '.join(profiles_for(did))}",
            f"- **Видно в:** {SURFACE.get(did, '—')}",
            f"- **Сценарій відтворення:** {repro_for(did)}",
            "",
        ]
    out = ROOT / "docs" / "defect-catalog.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"catalog -> {out}  ({len(REGISTRY)} defects)")


if __name__ == "__main__":
    main()
