# Довідник по трейсах

Кожен хід діалогу породжує одне дерево спанів. Студент пише assertions поверх
них (ДЗ7, ДЗ8), тому формат стабільний і задокументований.

## Як отримати

| Спосіб | Де |
|---|---|
| Phoenix UI | `http://localhost:6006` (піднімається разом зі стендом) |
| API, одне дерево | `GET /api/_test/traces/{request_id}` — `request_id` повертає `/chat` |
| API, останні N | `GET /api/_test/traces?limit=20` |
| Файл | `traces/traces.jsonl` — по одному JSON-дереву на рядок |

API і файл працюють завжди; Phoenix — додаткова поверхня (якщо колектор не
піднятий, стенд працює без нього, `make doctor` це показує).

## Структура дерева

```
agent.request                     ← корінь, один на хід діалогу
├── agent.summarize               ← лише коли спрацювала згортка історії
├── llm.call                      ← крок циклу оркестрації
├── tool.<name>                   ← виклик інструмента
│   └── (повтори при D14)
├── llm.call
└── ...
```

## Атрибути

### `agent.request`
| Атрибут | Значення |
|---|---|
| `session.id` | ідентифікатор сесії |
| `dialog.step_number` | номер репліки в діалозі — щоб вибрати спани конкретного кроку |
| `run.profile` | активний профіль |
| `run.active_defects` | список активних дефектів |
| `prompt.version` | напр. `base.v1+D01+D03` |
| `llm.provider` | `mock` / `anthropic` / `openai` |
| `context.replay_active` | `true`, коли працює роздування контексту (D15) |
| `gen_ai.usage.total_input_tokens` / `...output_tokens` | сумарні токени ходу |

### `llm.call`
`gen_ai.request.model`, `gen_ai.usage.input_tokens`,
`gen_ai.usage.output_tokens`, `agent.loop_step`.

На повторах D14 додатково: **`d14.retry_attempt`** (номер повтору) і
`agent.loop_step` у формі `d14-retry-<N>`. Атрибут стоїть саме на `llm.call`,
а не на `tool.*`, і це принципово: повторюється **повний** оберт «модель →
інструмент», тому кожен повтор коштує токенів. Повтор лише інструмента був би
безкоштовним і в бюджетному занятті (L08) нічого б не показав.

### `tool.<name>`
`tool.name`, `tool.arguments`, `tool.result` (аргументи й результат читаються
окремо — це різні заняття).

Для `tool.search_knowledge_base` додатково: `retrieval.query`,
`retrieval.index` (`kb_clean` / `kb_broken` — ядро D16),
`retrieval.fragments` (id + score; довжина списку — ядро D17).

### `agent.summarize`
`summary.text` (текст зведення — тут видно втрату числових сутностей D06 і
підміну коду причини D07), `summary.replaced_messages`.

## Приклад: assertion поверх спанів

```python
import httpx
r = httpx.post("http://localhost:8000/chat",
               json={"message": "Open a dispute for TX-0401, duplicate charge"})
tree = httpx.get(f"http://localhost:8000/api/_test/traces/{r.json()['request_id']}").json()

calls = [c for c in tree["children"] if c["name"].startswith("tool.")]
assert any(c["name"] == "tool.create_dispute" for c in calls)          # дію виконано
assert len(calls) == len({c["name"] for c in calls})                   # без повторів (D14)
assert tree["attributes"]["gen_ai.usage.total_input_tokens"] < 20000   # бюджет
```

## Що дефекти лишають у трейсі

| Дефект | Слід |
|---|---|
| D14 | кілька `tool.<name>` поспіль з ідентичними `tool.arguments` |
| D15 | `context.replay_active: true`, вхідні токени ростуть із кроком |
| D16 | `retrieval.index: kb_broken` |
| D17 | `retrieval.fragments` довжиною 1 |
| D13 | є `tool.get_transactions`, немає `tool.check_limits` |
| D27 | **відсутній** спан `tool.escalate_to_human` — дефект як відсутність спана |
| D06/D07 | `summary.text` без числових сутностей / з підміненим кодом причини |
