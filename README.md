# PayPilot — навчальний стенд AI Quality Engineering

AI-агент підтримки необанку **Verta** з контрольованими, відтворюваними
дефектами. Студент вмикає профіль заняття, ловить закладені дефекти, пише
перевірки й доводить їх прогонами.

## Швидкий старт

```bash
cp -n .env.example .env                       # ключ провайдера (або лишіть mock)
python scripts/doctor.py                      # діагностика оточення
docker compose up --build -d                  # або локально, без docker:
python -m uvicorn app.main:app --port 8000
```

Чат відкривається на **http://localhost:8000** — там же перемикач профілів,
точкове вмикання дефектів, керування часом і дерево спанів останнього ходу.

Phoenix (UI трасування) на **http://localhost:6006** піднімається **лише
через docker compose**. При запуску через uvicorn цей порт мертвий, і `doctor`
дасть `WARN` — це нормально: трейси однаково доступні через
`GET /api/_test/traces/...` і файл `traces/traces.jsonl`.

## Поверхні (ТЗ §3.2)

| Поверхня | Де |
|---|---|
| Чат з агентом | UI на `http://localhost:8000` · API `POST /chat` |
| Тестове API | `GET/PUT /api/_test/*` (див. нижче) |
| Трасування | Phoenix UI на `http://localhost:6006` + `GET /api/_test/traces/{request_id}` + `traces/traces.jsonl` |

## Змінні оточення

| Змінна | Значення |
|---|---|
| `PROFILE` | `clean` \| `lesson-01` … `lesson-14` — набір дефектів заняття |
| `DEFECTS` | довільна комбінація поза профілем: `D19,D26` |
| `CLOCK_OVERRIDE` | фіксована «поточна» дата прогону (ISO), напр. `2026-09-15T10:00:00Z` |
| `LLM_PROVIDER` | `mock` (без ключа) \| `anthropic` \| `openai` |
| `LLM_MODEL` | перевизначення моделі (дефолти: claude-haiku-4-5 / gpt-5-mini) |
| `RAG_TOP_K`, `KB_INDEX` | параметри пошуку (`kb_clean` / `kb_broken`) |

## Як розмовляти зі стендом

Єдиний змістовний ендпоінт — `POST /chat`. Усе інше довкола нього діагностичне.

```bash
curl -X POST localhost:8000/chat   -H 'content-type: application/json'   -d '{"session_id": "my-run-1", "message": "I am CUS-0001. What is my balance?"}'
```

```json
{"session_id": "my-run-1", "request_id": "770b66331f4f42fd",
 "answer": "Your balance is ...", "step_number": 1,
 "usage": {"input_tokens": 4791, "output_tokens": 157}}
```

Чотири речі, які варто знати одразу:

1. **Клієнт називається в тексті повідомлення.** Окремого поля немає:
   агент дізнається, з ким говорить, зі слів `I am CUS-0001`. Не назвете —
   агент перепитає й витратить крок.
2. **`session_id` — це і є діалог.** Той самий рядок продовжує розмову, новий
   починає з чистого аркуша. Для дефектів памʼяті (L05) це критично.
3. **Трейс у відповіді не приходить.** Візьміть `request_id` і заберіть
   дерево спанів окремо: `GET /api/_test/traces/<request_id>`. Саме там
   аргументи й результати інструментів — тобто все, чого немає в тексті.
   Трейси переживають перезапуск стенду (читаються з `traces/traces.jsonl`).
4. **`POST /api/_test/compare` коштує два виклики моделі**, бо шле запит на
   обидва профілі. Зручно, але це подвійна ціна.

> `.env.example` за замовчуванням ставить `LLM_PROVIDER=mock` — детерміновані
> відповіді без ключа. Це добре для перевірки, що все піднялося, і **не
> годиться** для завдань, де треба показати розподіл відповідей: mock завжди
> відповідає однаково. Для таких завдань потрібен живий провайдер.

## Тестове API (ТЗ §5.7)

| Ендпоінт | Призначення |
|---|---|
| `GET /api/_test/defects` | активні дефекти й профіль |
| `PUT /api/_test/defects` | поштучне вмикання без рестарту |
| `GET /api/_test/state/{table}` | вміст таблиць: `accounts`, `transactions`, `disputes`, `statements_sent`, `escalations`, `customers` |
| `GET /api/_test/seed` | версія seed, клієнти, рахунки і **кількість** транзакцій; самі транзакції — `GET /api/_test/state/transactions` |
| `GET/PUT /api/_test/clock` | читання/встановлення «поточного» часу |
| `POST /api/_test/reset` | скидання стану до seed |
| `GET /api/_test/prompt` | зібраний system prompt + активні overlay |
| `GET /api/_test/tools` | схеми інструментів (name, description, inputSchema) |
| `GET /api/_test/specs` | документи вимог (US-01) — артефакт аудиту L01 |
| `PUT /api/_test/profile` | перемикання профілю заняття без рестарту |
| `POST /api/_test/compare` | той самий запит на clean і на профілі, поруч |
| `GET /api/_test/traces` | останні трейси; `/{request_id}` — дерево спанів |
| `GET/PUT /api/_test/summarize_after` | після якого кроку історія згортається (ядро L05) |
| `GET/PUT /api/_test/retrieval` | `top_k` і індекс пошуку без рестарту (ядро L04) |

## Структура

```
prompts/base.v1.md       версіонований системний промпт: вісім блоків анатомії (L01)
specs/requirements/      user story US-01 — другий артефакт аудиту L01
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

Реалізовано **всі 27 дефектів** — 24 першої ітерації плюс D21 і D23 з другої
(зроблені понад обсяг ТЗ). Заміряні частоти —
`docs/calibration-report.json`, розгорнутий каталог — `docs/defect-catalog.md`.
D02 (документний дефект), D09 (покрито юніт-тестом) і D18 (набір фікстур
`app/fixtures/d18_judge_pairs.json`) за задумом ТЗ не міряються живим прогоном.


Приймальний прогін:

```bash
make calibrate                     # усі дефекти: профіль проти clean
python scripts/calibrate.py --only D19   # один дефект
make catalog                       # оновити каталог із заміряного звіту
python scripts/ci_smoke.py         # перевірити всі поверхні без ключа
```

## Документація

| Файл | Про що |
|---|---|
| `docs/ONBOARDING.md` | **почніть звідси**: що це таке, навіщо, кому що робити, де брати ключі |
| `docs/acceptance-criteria.md` | **для приймання**: пункт ТЗ → де реалізовано → чим доведено |
| `docs/lecturer-runbook.md` | **для лектора**: що має статися, чому не сталося, що робити зараз |
| `docs/lesson-guide.md` | профіль і готові запити на кожне заняття |
| `docs/defect-catalog.md` | по кожному дефекту: механізм, місце, заміряна частота, сценарій |
| `docs/architecture.md` | компоненти, потоки даних, життєвий цикл запиту |
| `docs/seed-data.md` | усі клієнти й транзакції з прив'язкою до сценаріїв |
| `docs/traces.md` | склад спанів і як писати assertions поверх них |
| `docs/methodologist-tasks.md` | **для методолога**: що підписати, за годину |
| `docs/divergences.md` | повний інвентар розбіжностей із лонгрідами |
| `docs/walkthrough-report.md` | наскрізний прохід 14 лабораторних: крок → статус |
| `docs/acceptance-evidence.md` | приймальні докази: команда → дослівний результат |
| `profiles/corridors.yaml` | коридори приймання, зафіксовані до прогону |
| `docs/calibration-history/` | історія ітерацій калібрування — довідково, не докази |

## Звірка з навчальними матеріалами

Профілі занять і доменні числа звірені з 17 лонгрідами курсу (`Grids/*.pdf`).
Усе, що зроблено інакше, ніж у текстах, — у `docs/divergences.md`; це робочий
вхід методолога (ТЗ §9, п. 6).

## Тести стенду

```bash
make test         # юніт-тести рушіїв, дефектів і API (без ключа)
python scripts/ci_smoke.py   # усі поверхні стенду відповідають (без ключа)
make walkthrough  # кроки лабораторних усіх 14 занять (потрібен ключ)
```

CI: `.github/workflows/stand-ci.yml` ганяє doctor, тести, smoke і збірку
Docker-образу на mock-провайдері — стенд придатний до CI без API-ключа
(ТЗ §11: власний гейт студент будує сам на L13).

## Еталон рішень

`solutions/` — резервні артефакти, які ДЗ обіцяють студентові після дедлайну.
Не частина стенду: стенд від них не залежить. Див. `solutions/README.md`.
