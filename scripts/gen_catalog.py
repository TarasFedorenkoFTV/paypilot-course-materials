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

# Windows consoles default to cp1252: any non-ASCII in the output kills the run
# with UnicodeEncodeError before the verdict is printed. Force UTF-8.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


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
    "D19": "text + tool args", "D20": "text",
    "D22": "tool result (check_limits.monthly_remaining_eur) — НЕ в тексті",
    "D21": "text + tool result (spread_amount)", "D23": "text (multi-turn)",
    "D24": "text", "D25": "text",
    "D26": "залежить від формулювання запиту — див. застереження",
    "D27": "trace (absence of escalate span)",
}


# Traps a lecturer would otherwise walk into. Measured, not assumed.
CAVEATS = {
    "D22": ("Агент **перераховує** місячний залишок з інших полів результату і "
            "часто називає в тексті **правильне** число. Дефект живий у "
            "`tool.check_limits` → `monthly_remaining_eur`, і ловиться лише "
            "assertion на результат інструмента. Це головний приклад класу "
            "«правильна проза, хибний payload» — текстова перевірка тут "
            "зелена, а система в хибному стані."),
    "D26": ("**Видно не завжди.** На запит-питання («чи можу я оскаржити…») "
            "агент переказує відповідь інструмента, і розбіжність із рушієм "
            "видно в тексті. На запит-дію («відкрий спір») агент просто "
            "виконує її й чесно звітує «Done, dispute opened» — текст "
            "**правдивий**, усі заборонені слова відсутні, перевірка тексту "
            "зелена. Дефект тоді живий лише в рядку БД "
            "(`GET /api/_test/state/disputes` для клієнта під комплаєнсом) і в "
            "порядку спанів. Формулюйте запит свідомо: це два різні заняття."),
    "D20": ("**Гасить D21 на одній конкретній сумі.** Обидва активні на "
            "`lesson-03`. D20 підіймає спред tier2 0.9% -> 1.5% (x1.667), "
            "D21 бере його лише з частини понад залишок ліміту. Коли сума = "
            "**2.5 x залишок безкоштовного ліміту**, множники дають рівно 1.0, "
            "і `final_amount` **побайтово однаковий** на `clean` і на "
            "`lesson-03`. Заміряно: залишок 200 -> сума 500; залишок 1000 -> "
            "сума 2500. Різниця лишається тільки в `spread_pct` у трейсі. "
            "Не показуйте цю суму й не ставте її в набір: перевірка на "
            "підсумкову суму зеленіє на двох critical-дефектах одночасно."),
    "D21": ("Див. застереження до D20: на сумі, що дорівнює 2.5 x залишок "
            "безкоштовного ліміту, ці два дефекти гасять один одного в "
            "`final_amount`. Це найкращий на курсі приклад того, чому один "
            "вхід не є перевіркою."),
    "D09": ("Заміряно **не** живим прогоном: юніт-тест перевіряє санітизацію "
            "payload, а не виконання інʼєкції. Модель, яку ми використовуємо, "
            "стабільно ігнорує інструкцію в назві мерчанта. Для L06 це "
            "**сам по собі результат** — показуйте як приклад того, що "
            "вирівняна модель тримає межу, і не обіцяйте студентам спрацювання."),
    "D06": ("Потрібно опустити поріг згортки: "
            "`PUT /api/_test/summarize_after {\"steps\": 2}` (без рестарту). "
            "На типовому значенні 8 діалог заняття просто не досягає згортки, "
            "і дефект не проявиться."),
    "D07": ("Той самий поріг згортки, що й D06. D07 має пріоритет над D06: "
            "коли обидва активні, підсумок **спотворюється**, а не "
            "вичищається — інакше агент перестає йому вірити й перепитує."),
    "D14": ("Атрибут повтору стоїть на спані `llm.call` як `retry.attempt`, "
            "а не на `tool.*`. Кожен повтор — повний оберт «модель → "
            "інструмент», тому він коштує токенів (заміряно ×5.03)."),
}


_REPORT_META = (json.loads(report_path.read_text(encoding="utf-8"))
                if report_path.exists() else {})
_ARMS = ", ".join(sorted({r.get("arm", "ізоляційна (до переробки інструмента)")
                          .split(":")[0] for r in REPORT.values()})) if REPORT else ""


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
                  f"{_REPORT_META.get('model') or '?'}"
                  + (" — **модель у звіті не зафіксована**; заміри вважати "
                     "орієнтовними, поки не буде прогону, який її запише"
                     if _REPORT_META.get('model') in ('default', '', None) else "")
                  + f", рука: {_ARMS or 'не зафіксована'}.",
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
        ]
        if did in CAVEATS:
            lines += ["", f"> ⚠️ **Застереження для лектора.** {CAVEATS[did]}"]
        lines += [""]
    out = ROOT / "docs" / "defect-catalog.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"catalog -> {out}  ({len(REGISTRY)} defects)")


if __name__ == "__main__":
    main()
