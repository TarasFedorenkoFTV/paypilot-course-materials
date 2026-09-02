# Наскрізна перевірка лабораторних (ТЗ §10.3)

Провайдер: anthropic · модель claude-haiku-4-5 · тривалість 5.7 с

**Пройдено 8 з 8 кроків.**

Перевіряються кроки лабораторних, що торкаються стенду. Кроки, де студент користується власними артефактами (`make eval`, `loader.py`, `evals/sets/*.jsonl`), поза обсягом стенду й тут не перевіряються.

| Заняття | Крок | Статус | Що показав прогін | с |
|---|---|---|---|---|
| L10 | profile leaves the stand clean | ✅ | lesson-10 is clean; only the student's judge model changes | 0.0 |
| L11 | engines are unit-testable without the agent | ✅ | engines/fx.py is plain importable Python with a stable dataclass | 0.0 |
| L12 | version fields for the run record are obtainable | ✅ | prompt.version, run.profile and run.active_defects come from the run | 5.6 |
| L12 | the joint-failure class is expressible | ✅ | every component check passes, the engine still refuses, the tool agrees — the 'each right, together wrong' class | 0.0 |
| L13 | DEFECTS=D19 produces the red build the gate needs | ✅ | DEFECTS=D19 flips one case red and clean back to green | 0.0 |
| L13 | stand itself is runnable in CI | ✅ | stand CI runs keyless and fails on a non-zero exit | 0.0 |
| L14 | mixed DEFECTS combinations used by the optional parts | ✅ | 5 mixed DEFECTS combinations all configure cleanly | 0.0 |
| L14 | misconfiguration fails loudly (ТЗ §5.8) | ✅ | bad ids and bad profiles raise an explicit configuration error | 0.0 |
