# PayPilot — навчальний стенд AI Quality Engineering

AI-агент підтримки необанку **Verta** з контрольованими, відтворюваними
дефектами. Студент вмикає профіль заняття, ловить закладені дефекти, пише
перевірки й доводить їх прогонами.

## Швидкий старт

```bash
cp .env.example .env          # заповніть ключ провайдера (або лишіть mock)
python scripts/doctor.py      # діагностика оточення
docker compose up --build -d  # або: make dev (локально без docker)
```

Перевірка: `curl http://localhost:8000/health`

## Поверхні (ТЗ §3.2)

| Поверхня | Де |
|---|---|
| Чат з агентом | `POST /chat` `{"message": "...", "session_id": "..."}` |
| Тестове API | `GET/PUT /api/_test/*` (див. нижче) |
| Трасування | `GET /api/_test/traces/{request_id}` + файл `traces/traces.jsonl` |

## Змінні оточення

| Змінна | Значення |
|---|---|
| `PROFILE` | `clean` \| `lesson-01` … `lesson-14` — набір дефектів заняття |
| `DEFECTS` | довільна комбінація поза профілем: `D19,D26` |
| `CLOCK_OVERRIDE` | фіксована «поточна» дата прогону (ISO), напр. `2026-09-15T10:00:00Z` |
| `LLM_PROVIDER` | `mock` (без ключа) \| `anthropic` \| `openai` |
| `LLM_MODEL` | перевизначення моделі (дефолти: claude-haiku-4-5 / gpt-5-mini) |
| `RAG_TOP_K`, `KB_INDEX` | параметри пошуку (`kb_clean` / `kb_broken`) |

## Тестове API (ТЗ §5.7)

| Ендпоінт | Призначення |
|---|---|
| `GET /api/_test/defects` | активні дефекти й профіль |
| `PUT /api/_test/defects` | поштучне вмикання без рестарту |
| `GET /api/_test/state/{table}` | вміст таблиць: `accounts`, `transactions`, `disputes`, `statements_sent`, `escalations`, `customers` |
| `GET /api/_test/seed` | перелік seed-даних |
| `GET/PUT /api/_test/clock` | читання/встановлення «поточного» часу |
| `POST /api/_test/reset` | скидання стану до seed |
| `GET /api/_test/prompt` | зібраний system prompt + активні overlay |
| `GET /api/_test/tools` | схеми інструментів (name, description, inputSchema) |
| `GET /api/_test/traces` | останні трейси; `/{request_id}` — дерево спанів |

## Структура

```
prompts/base.v1.md       версіонований системний промпт (артефакт L01)
prompts/overlays/Dxx.md  overlay-файли дефектів рівня специфікації
profiles/profiles.yaml   профілі занять -> дефекти
profiles/defects.yaml    реєстр дефектів D01–D27 (механізм, шар, режим)
app/engines/             доменні рушії-оракули: fx, limits, disputes
app/agent/loop.py        власний цикл оркестрації (D14, D15 живуть тут)
app/agent/tools.py       інструменти агента (дефектні гачки D09–D11, D19–D26)
app/rag/                 корпус Verta + два індекси (kb_clean / kb_broken)
app/tracing.py           дерева спанів: JSONL + API
scripts/doctor.py        діагностика оточення
```

## Статус реалізації дефектів

Детермінованих (код/конфіг) реалізовано й покрито тестами: D10, D11, D14,
D15, D16, D17, D19, D20, D22, D26. Промпт-шар (overlay) реалізовано: D01,
D02, D03, D08, D24, D27 — **коридори частот калібруються на живому
провайдері** (наступний етап). Заплановано: D04–D07, D12, D13, D18, D25.
Друга ітерація (поза обсягом): D21, D23.

## Тести стенду

```bash
python -m pytest tests/ -q
```
