# PayPilot — приймальний огляд очима студента (РАУНД 3)

**Хто пише:** студент курсу «AI Quality Engineer». Доступ: тільки `D:\paypilot-public`.
**Стенд:** http://localhost:8000, живий провайдер `anthropic`, `CLOCK_OVERRIDE=2026-09-15T10:00:00Z`.
**Витрачено живих запитів до `POST /chat`: 17 з 20.**
**Дата прогону:** 2026-09-03.

---

## 1. Вердикт студента

**Роботу виконати можна — і я її виконав.** Обидва ДЗ зроблені, з прогонами, оракулом і розподілами.

**Але експеримент цього раунду провалений.** Я отримав повний ключ до відповідей, не зробивши жодного
живого запиту — за 4 хвилини читання репозиторію. Головна діра не в робочому дереві, а в **git-історії
самого публічного репозиторію**: обидва коміти-«зачистки» лежать у ньому, тому все, що вони видалили,
повертається одною командою `git show`.

Тобто: попередні два раунди прибирали підказки з робочого дерева і **комітили це прибирання в репозиторій,
який віддають студенту**. Кожна ітерація зачистки додала в історію рівно те, що намагалася приховати.

Я свідомо зробив ДЗ так, ніби ключа не бачив (оракул `app/engines/`, порівняння профілів, розподіли),
щоб можна було оцінити, чи здатний стенд витримати чесне дослідження. Здатний — див. §6.
Але це моє рішення, а не властивість стенду.

---

## 2. Полювання на підказки

Знайшов. Багато. За зростанням «вбивчості».

### 2.1 БЛОКЕР — `git show` повертає весь видалений каталог дефектів

`git log` у публічному репозиторії:

```
bc3839c Remove the last of the answer key: fixtures, overlay names, runtime labels
29d129a Ship the stand without the commentary that explains its defects
c4bb317 PayPilot — навчальний стенд AI Quality Engineering
```

Назви комітів самі кажуть, що шукати. Команда:

```bash
git show 29d129a | grep "^-" | grep -v "^---"
```

повертає **458 рядків** видаленої документації. Серед них — дослівно — докстрінг `app/agent/tools.py`:

```
-Defects live in the agent-facing layer, never in the engines:
-  D09 — clean profile sanitizes bracketed instructions in tool output; the
-        defect leaves the seeded payload intact,
-  D10 — send_statement skips matching the address against the account owner,
-  D11 — create_dispute records a currency-less amount in the account base
-        currency instead of the transaction currency,
-  D19 — check_dispute_eligibility distorts the window for one reason code,
-  D20 — quote_fx applies the neighbouring tier's spread,
-  D22 — check_limits returns the daily remainder labeled as monthly,
-  D26 — check_dispute_eligibility ignores the customer compliance hold.
```

І окремо, з видалених коментарів у тілі функцій:

```
-        # 60-day window presented as 90: eligible past the real edge
-        compliance = False  # the seam: the tool never asks about the hold
-        # daily remainder presented as monthly; both numbers valid, same source
-        # D21: the spread is charged only on the portion above the remaining
-        # allowance instead of on the whole conversion. Policy says the whole
```

**Це буквально всі п'ять дефектів `lesson-03` (D19, D20, D21, D22, D26) з описом механізму.**
Загалом у відновлюваній історії описано **21 із 27** дефектів:
`D01 D03 D06 D07 D09 D10 D11 D12 D13 D14 D15 D16 D17 D19 D20 D21 D22 D23 D24 D26 D27`.

Скорочення роботи: **ДЗ №3 з дослідження перетворюється на переписування.** Мені не треба було ні
порівнювати профілі, ні дивитися в трейс — я знав відповідь до першого запиту.

### 2.2 БЛОКЕР — та сама історія віддає таблицю «хеш → дефект»

Раунд 3 перейменував `prompts/overlays/D05.md` → `086a8f6e992b.md`, щоб не можна було
«грепнути прямо до відповіді». Але перейменування — це і є `git`-операція:

```bash
git show bc3839c --stat | grep overlays
```

```
prompts/overlays/{D05.md => 086a8f6e992b.md}       | 0
prompts/overlays/{D07.md => 1e672f7e2240.md}       | 0
prompts/overlays/{D12.md => 505bb4f1ca41.md}       | 0
prompts/overlays/{D27.md => 7b6f1c6f0186.md}       | 0
prompts/overlays/{D13.md => 7e9df1b100ef.md}       | 0
...
```

15 рядків — готова таблиця відповідності. Обфускація назв не протримала жодної команди.

### 2.3 БЛОКЕР — сіль хешування лежить у коді, тому хеші оборотні незалежно від git

Навіть якби історію почистили, `app/agent/prompt.py:66`:

```python
def overlay_slug(defect_id: str) -> str:
    return hashlib.sha1(f"paypilot-overlay-{defect_id}".encode()).hexdigest()[:12]
```

Функція, що створює обфускацію, поставляється разом з обфускацією. Три рядки — і мапа відновлена:

```python
for i in range(1, 40):
    d = "D%02d" % i
    if hashlib.sha1(("paypilot-overlay-"+d).encode()).hexdigest()[:12] in files:
        print(d)
```

Я так і зробив, і отримав усі 14 відповідностей. Це не криптографія, це `ROT13` з ключем у коментарі.

### 2.4 ВАЖЛИВО — склад заняття виданий відкрито

`profiles/profiles.yaml` (у робочому дереві, без git):

```yaml
  lesson-03: [D19, D20, D21, D22, D26]
```

Завдання каже: «Ти не знаєш заздалегідь, що зламано на `lesson-03`. З'ясувати — частина роботи».
Я знаю точну кількість (5) і точні ідентифікатори з першого файлу, який відкрив.
Навіть без розшифровки що вони роблять, це дає:
- скільки дефектів шукати (інакше «я знайшов 3» не дорівнює «я знайшов усі»);
- що **жоден із п'яти не має overlay** (у `prompts/overlays/` немає ні `D19..D22`, ні `D26`),
  отже всі п'ять — кодового рівня, а не промптового. Це прибирає половину простору пошуку.

### 2.5 ВАЖЛИВО — дефекти як inline-гілки з ідентифікаторами в коді

`grep -n "is_on" app/agent/tools.py` — і дослідження закінчилося:

```
 66:    if defects.is_on("D22"):    -> st["monthly_remaining_eur"] = st["daily_remaining_eur"]
 81:    if defects.is_on("D20"):    -> override = FX_SPREAD_PCT[_TIER_NEIGHBOUR[tier]]
 86:                        partial_allowance=defects.is_on("D21"))
 98:    if defects.is_on("D19") and reason_code == "duplicate_charge":  -> window_override = 90
101:    if defects.is_on("D26"):    -> compliance = False
```

Коментарі прибрали — але сам код читається як специфікація дефекту. `_TIER_NEIGHBOUR` як назва
константи каже «сусідній тариф» не гірше за видалений коментар. Це, ймовірно, непереборно
без переписування архітектури (дефекти мусять якось перемикатися), але варто це визнати:
**вихідний код у комплекті = дефекти кодового рівня не приховані.**

### 2.6 СЕРЕДНЄ — `app/fixtures/judge_pairs.json` містить точні значення дефектів

Файл перейменували з `d18_judge_pairs.json` і зняли заголовок, але вміст лишився:

```json
{"id": "JB-02",
 "question": "How many days do I have to dispute a duplicate charge?",
 "ground_truth": "60 days",
 "long_wrong": "... You have up to 90 days from the date of the transaction ..."}
```

`60` правильно, `90` — «неправильно». Це **дослівно D19** (вікно `duplicate_charge` 60 -> 90),
включно з тим, що дефект стосується саме `duplicate_charge`. Аналогічно JB-03: `20,000` проти `25,000`.
Фікстура для ДЗ про LLM-суддю водночас є відповіддю на ДЗ про дефекти.

### 2.7 Що НЕ виявилося підказкою (справедливості ради)

- `profiles/defects.yaml` — реально почищений, тільки ідентифікатори, `{}` в кожному.
- `docs/`, `prompts/base.v1.md`, `specs/`, `app/rag/corpus/`, `app/static/`, `docker-compose.yml`,
  `Makefile`, `.env.example` — `grep -rn "D[0-9][0-9]"` не дає нічого. Чисто.
- CI-конфіг — свідомо не називає ідентифікатори, є навіть коментар про це. Чисто.
- `git show c4bb317:profiles/defects.yaml` — історію справді почали заново, у першому коміті
  каталог уже вичищений. Тобто **проблема не в старій історії, а в трьох нових комітах.**
- `app/engines/` — оракул чистий, жодної гілки `is_on`. Це правильно і важливо.

### 2.8 Позарепозиторна знахідка — не почищено робочий каталог між раундами

Не в `paypilot-public`, але варте рядка: мій сесійний scratchpad
(`...\Temp\claude\D--TestNeolink\<session>\scratchpad`) виявився **не порожнім**. Там лежали
артефакти попередніх раундів: `harness.py`, `scrubber.py`, `cases.jsonl`, `res_clean.json`,
`res_l03.json`, `d22_l03.json`, каталоги `tz/`, `tz2/`, `dz/` і `runs.jsonl` з 19 прогонами,
назви кейсів у яких — `FX-1000`, `LIM-MONTH`, `LIM-MONTHONLY`, `DIS-WINDOW`, `DIS-HOLD`.

Тобто назви кейсів попереднього раунду **самі є картою дефектів lesson-03**. Я їх не читав як
відповіді (виніс свої записи в окремий `r3.jsonl`), але наступний студент прочитає.
«Стан скинуто» стосувалося стенду, не робочого каталогу.

---

## 3. Чи вистачило матеріалів

**Вистачило, з великим запасом.** Критично не бракує нічого. Все, що обіцяє README, існує і працює:

| Поверхня | Перевірено | Результат |
|---|---|---|
| `POST /chat` | так | 200, `request_id`, `elapsed_ms`, `usage` — усе на місці |
| `GET /api/_test/traces/<id>` | так | `tool.arguments` + `tool.result` повністю, переживають рестарт |
| `GET /api/_test/state/{table}` | усі 6 таблиць з README | 200 кожна |
| `GET /api/_test/{prompt,specs,tools,clock,defects,retrieval,summarize_after}` | так | 200 кожен |
| `PUT /api/_test/profile`, `POST /api/_test/reset` | так | працюють без рестарту |
| `app/engines/` як оракул | так | імпортується, детермінований, без дефектних гілок |
| `python scripts/doctor.py` | так | усе `[OK]`, один `[WARN]` (Phoenix) — як і описано |
| `python scripts/ci_smoke.py` | так | `All stand surfaces OK`, 10/10 |
| `python -m pytest tests/ -q` | так | `15 passed` |

Оракул (`app/engines/`) — справді оракул: дефекти живуть у `app/agent/tools.py`, які викликають
рушій із зіпсованими аргументами, а сам рушій лишається правильним. Це дало мені точні очікувані
значення **без жодного живого запиту** — і саме на цьому тримається весь ДЗ №3.

Єдине, чого бракує **методично**, а не технічно: у `specs/` лежить один документ (US-01) на
одну функцію (FX-конвертація), а ДЗ №3 просить перевірки, які натурально зачіпають ліміти й спори.
Для них немає вимоги, з якою можна звірятися — тільки код і рушій. Формально це не блокер
(ДЗ №3 не вимагає спеки), але «очікування» в кейсах C-03..C-08 я виводив з `app/engines/` і
`prompts/base.v1.md`, а не з документа вимог. Тобто у стенді є US-01, але немає US-02/US-03.

---

## 4. Журнал спотикань

Хронологічно, як натрапляв.

**С-1. `find . -type f` у корені репозиторію вивалює `.venv`.**
`.venv/` є в робочому дереві (у `.gitignore`, тому не в git, але клон плюс перший `pip install`
відтворює її). Перше, що робить новий студент — дивиться список файлів — і отримує кілька тисяч
рядків `site-packages`. Дрібниця, але це рівно перший крок. Обхід: `git ls-files`.
Пропозиція: згадати `git ls-files` у README в розділі «Структура».

**С-2. README обіцяє транзакції в `/api/_test/seed`, а їх там немає.**
README, таблиця «Поверхні для дослідження»:

> `GET /api/_test/seed` — еталонні дані: клієнти, рахунки, **транзакції**

Фактично:

```
$ curl -s localhost:8000/api/_test/seed | python -c "import json,sys; print(list(json.load(sys.stdin).keys()))"
['seed_version', 'customers', 'accounts', 'transaction_count']
```

Помилка, яку я отримав, коли повірив README:

```
Traceback (most recent call last):
  File "<string>", line 8, in <module>
    for t in d['transactions']:
             ~^^^^^^^^^^^^^^^^
KeyError: 'transactions'
```

Транзакції є, але в `GET /api/_test/state/transactions`. Це **єдине справжнє розходження
документації з реальністю**, яке я знайшов. Коштувало мені однієї ітерації. Для ДЗ №3 воно
на дорозі: без списку транзакцій не підібрати кейс на вікно спору.
Пропозиція: або віддавати `transactions` у `/seed`, або в README писати
`клієнти, рахунки, кількість транзакцій (список — у /state/transactions)`.

**С-3. `make` відсутній — але README попереджає.**
`which make` -> `no make in (...)`. README:
> `make` у репозиторії є, але на Windows його зазвичай немає — усі цілі Makefile — це однорядкові команди вище.

Спотикання знято документацією. Зараховую як **не** дефект.

**С-4. Phoenix на 6006 мертвий — README попереджає.**
`curl localhost:6006` -> код `000`. `doctor` дає
`phoenix (trace UI)  [WARN] OTEL_EXPORTER_OTLP_ENDPOINT not set; the JSONL/API trace surface still works`.
README описує це двома абзацами наперед і каже, куди йти замість цього. **Не** дефект.
Це, до речі, найкраще місце в README: попереджений збій, який виглядає як поломка.

**С-5. `.env` уже існує в клоні з ключем провайдера.**
README крок 2 — `cp .env.example .env`. У моєму каталозі `.env` уже лежав (`LLM_PROVIDER=anthropic`),
і `cp` затер би робочу конфігурацію на `mock`. Я не виконував цей крок і перевірив
`GET /health` -> `"provider":"anthropic"`. Для студента, який слухняно виконує README по кроках,
це тихо переводить стенд у `mock` — а `mock` «завжди відповідає однаково», тобто ДЗ №1 п.3
(розподіл на 3–5 прогонах) стає неможливим і незрозуміло чому.
Пропозиція: `cp -n .env.example .env` або рядок «якщо `.env` вже є — не перезаписуйте».

**С-6. `prompts/base.v1.md` §8 «Examples» — порожній заголовок.**
```
$ sed -n '/## 8. Examples/,$p' prompts/base.v1.md | tail -n +2 | wc -w
0
```
Це не спотикання, а знахідка ДЗ №1 (див. §5), але я спершу подумав, що файл обрізався при читанні.

**С-7. `pytest` і `ci_smoke` шумлять депрекейшеном.**
`StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated; install httpx2 instead.`
На Python 3.14. Тести проходять (`15 passed`), нічого не ламає, але перший рядок виводу
`ci_smoke.py` — попередження, а не результат, і це на секунду читається як помилка.

**Чого в журналі немає:** жодних падінь стенду, жодного `HTTP 400`, жодного невідповідного
ендпоінта, жодної зламаної команди з README (крім С-2). Стенд технічно міцний.

---

## 5. ДЗ №1: аудит специфікації

Аудит `prompts/base.v1.md` (версія `base.v1`, підтверджена `GET /api/_test/prompt`) і
`specs/requirements/US-01.md` (v1.0, «Approved for build»).

### 5.1 Карта анатомії — вісім блоків

| # | Блок | Де | Стан | Чому |
|---|---|---|---|---|
| 1 | Роль / тон | `base.v1` §1 | **є** | Роль, аудиторія («verified retail customers»), тон («professional and businesslike») і навіть структура відповіді («what you did, what you found, what happens next»). Найсильніший блок. |
| 2 | Скоуп | §2 | **є** | Перелічені і теми, і дозволені дії (спори, виписки, ескалація). Межа з §6 («outside Verta products — say so and stop») закрита. |
| 3 | Джерела правди | §3 | **є** | Явна заборона на неотримані цифри, явний пріоритет tool > KB. Але саме цей пріоритет створює суперечність F-1. |
| 4 | Правила інструментів | §4 | **є** | Чотири умови обов'язкової ескалації, заборона `create_dispute` після `eligible=false`, правило адресата виписки. Конкретно й перевірювано. |
| 5 | Доменні обмеження | §5 | **є** | Поріг 9 000 EUR, режим compliance review, ліміти за тарифом. |
| 6 | Крайні випадки | §6 | **слабкий** | 4 рядки на все. Покриває «немає даних / помилка / порожній результат» і «поза продуктами». **Не** покриває: розходження двох tool-результатів між собою; частково доступні дані; суперечність tool-результату з §5; що робити, якщо `eligible=true`, але цифри виглядають абсурдно. Останнє — рівно та дірка, у яку провалюється `lesson-03`. |
| 7 | Формат виходу | §7 | **слабкий** | «Answer concisely» без жодної метрики (мої 5 прогонів: 385–538 символів — усі «concise»?). «a final amount consistent with them» — без допуску на округлення: `538.587` -> «538.59» це consistent? А «приблизно 539»? Немає відповіді. |
| 8 | Приклади | §8 | **ПОРОЖНІЙ** | Заголовок є, тіла нема — 0 слів. Формально блок «присутній», фактично відсутній. |

Підсумок: 5 блоків «є», 2 «слабкі», 1 порожній.
Промпт написаний **краще**, ніж спека — US-01 значно гірший за `base.v1`.

### 5.2 Знахідки

Покрито всі п'ять типів.

---

**F-1 · СУПЕРЕЧНІСТЬ · severity: critical**

US-01 AC-7: «The response is consistent with the tariff schedule.»
`base.v1` §3: «Where a tool result and a knowledge-base fragment disagree, **the tool result wins**.»

Тарифна сітка — це документ, вона живе в `app/rag/corpus/tariffs.md`, тобто в KB. Отже якщо
`quote_fx` віддасть спред, що не збігається з тарифом, промпт **наказує** агентові відтворити
цифру з tool — і тим самим порушити AC-7. Дві вимоги не можуть бути виконані одночасно.

Це не теорія. `lesson-03` (D20) робить рівно це, і агент виконав промпт, а не спеку:
у 3 з 3 прогонів він назвав спред **1.5%** для клієнта `tier2`, чий тарифний спред — **0.9%**
(`app/engines/policy.py:FX_SPREAD_PCT`). AC-7 порушено, §3 виконано.

Суперечність ще й внутрішня для спеки: AC-4 («must not mislead the customer about costs»)
конфліктує з AC-7 у той самий спосіб — і жодне з двох не має пріоритету.

---

**F-2 · НЕВЕРИФІКОВАНІСТЬ · severity: high**

US-01 AC-3: «The agent **should respond quickly**.»

Немає ні порогу, ні перцентиля, ні того, що саме міряти. Стенд віддає `elapsed_ms` у кожній
відповіді — тобто **вимірювати є чим, а порівнювати ні з чим**. Доказ — у §5.3.

Той самий діагноз, слабший ступінь:
- AC-2 «must be helpful and easy to understand for a non-financial customer» — жодного критерію.
  «Non-financial customer» не операціоналізовано (клас читабельності? заборона на терміни?).
- `base.v1` §7 «Answer concisely» — те саме.
- AC-1 «responds with the applicable rate and the resulting amount» — верифіковано (два поля),
  але «applicable» не сказано яке саме: mid-rate? з накрученим спредом? У прогонах агент дає
  mid-rate `1.086957` і окремо спред — розумно, але це його вибір, не вимога.

---

**F-3 · НЕПОВНОТА · severity: high**

Три дірки, від найдорожчої:

1. **`base.v1` §8 «Examples» — порожній.** Промпт, що вимагає складного формату (§7: компоненти
   плюс узгоджена сума), не показує жодного зразка. Формат лишається на розсуд моделі — і саме тому
   §5.3 показує 5 різних формулювань на одне питання.
2. **US-01 не згадує спред узагалі.** AC-1 говорить про «rate», AC-5 про «allowance», але
   `spread_pct` — головна цінова компонента (`FX_SPREAD_PCT` = 0.5–1.5% за тарифом) — не названа
   ні в жодному AC, ні в «Notes» (там лише «Limits and spreads are per tier, as agreed with Payments» —
   тобто вимога делегована в усну домовленість, див. F-5). Наслідок практичний: **дефект D20
   не порушує жодного пункту US-01 буквально.** Спека не може його зловити.
3. **Не задано поведінку при частково витраченому allowance.** AC-5: «Where the customer's free
   monthly allowance **applies**, the response reflects it». Що робити, коли конвертація
   частково входить у залишок (використано 800 з 1000, конвертують 500)? Спред на всю суму
   чи на перевищення? Спека молчить — і в цю тишу поставлено дефект D21.

---

**F-4 · НЕОДНОЗНАЧНІСТЬ · severity: high**

US-01 AC-6: «The agent **handles recent conversions correctly**.»

Речення не має визначеного суб'єкта. «Recent conversions» це:
(а) історія транзакцій клієнта (є `TX-0501 "FX conversion EUR->USD"`);
(б) вже витрачена частина місячного allowance (`fx_allowance_used_eur`);
(в) курс, що змінився з часу попередньої конвертації;
(г) щось четверте?

«Correctly» не визначено ні для якого з варіантів. Написати перевірку на AC-6 неможливо —
спершу треба вгадати, про що він.

AC-5 «Where the allowance **applies**» — те саме слово-пастка: «applies» повністю чи частково
(див. F-3.3). Різниця між цими двома читаннями — це буквально різниця між `clean` і `D21`.

---

**F-5 · НЕВІДСТЕЖУВАНІСТЬ · severity: medium**

- **AC не мають ідентифікаторів.** Це нумерований список `1..7`. Вставлять пункт у середину —
  і «AC-4» у моєму звіті поїде на інший критерій. Посилатися стабільно ні на що.
- **Немає зв'язку спека / промпт.** US-01 ніде не згадує `prompts/base.v1.md`, а `base.v1` ніде
  не згадує US-01. Промпт — фактична реалізація вимог, і зв'язок між ними тільки в голові автора.
  `prompt.version` у трейсі (`base.v1`) не мапиться ні на яку версію спеки.
- **Немає зв'язку спека / код.** `FX_SPREAD_PCT`, `FX_FREE_MONTHLY_ALLOWANCE_EUR`,
  `DISPUTE_WINDOWS_DAYS` живуть у `app/engines/policy.py` — жоден AC на них не посилається.
  Змінять тариф у коді — жодна вимога не «почервоніє».
- **Вимога делегована в усну домовленість.** Notes: «Limits and spreads are per tier,
  **as agreed with Payments**». Тобто нормативне джерело — не документ.
- **Статус без дати й підпису.** «Status: Approved for build», «Version: 1.0», «Author: Product
  (Verta Payments)» — немає дати затвердження й конкретної особи. Незрозуміло, що новіше:
  спека чи `base.v1`.

---

### 5.3 Доказ через прогони (ДЗ №1 п.3)

**Гіпотеза:** AC-3 («should respond quickly») і AC-2 («helpful and easy to understand»)
неверифіковані — не тому, що агент поводиться погано, а тому що **немає критерію**, і при цьому
поведінка природно розсіяна.

**Метод:** профіль `clean`, `reset`, `CLOCK_OVERRIDE=2026-09-15T10:00:00Z`, провайдер `anthropic`,
`prompt.version=base.v1`. Одне й те саме питання, **5 разів**, кожен у своїй `session_id`
(щоб не було впливу історії):

> `I am CUS-0002. I want to convert 500 EUR to USD. What will I get?`

**Розподіл AC-3 (латентність), `elapsed_ms`:**

| Прогін | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| `elapsed_ms` | 5680 | 4062 | 4075 | 4479 | 4121 |

min 4062 · max 5680 · розкид **1618 мс (40% від мінімуму)**.
Найшвидший прогін у 1.4 раза швидший за найповільніший на **ідентичному** вводі.
Питання, на яке US-01 не дає відповіді: 5680 мс — це «quickly»? А 4062? Порогу немає,
тому **обидва однаково не є ні pass, ні fail**. Це і є неверифікованість: не «агент повільний»,
а «твердження нефальсифіковне».

**Розподіл AC-2 (обсяг відповіді), символів:** 385 · 472 · 427 · 538 · 454 — розкид 1.4 раза.
Усі п'ять — «concise»? Критерію немає.

**Розподіл AC-5 (як відображено allowance) — найцікавіше:**

| Прогін | Формулювання |
|---|---|
| 1 | «used EUR 800 of your EUR 1,000 monthly allowance, so this EUR 500 conversion **cannot use the allowance**» |
| 2 | «1000 EUR total; 800 EUR already used, so there's **200 EUR remaining — not enough** to cover this full transaction» |
| 3 | «1,000 EUR available; 800 EUR already used this period» |
| 4 | «1,000 EUR of free FX conversion per period; you've already used 800 EUR, **leaving 200**» |
| 5 | «1,000 EUR available, but 800 EUR has already been used, **leaving only 200 EUR remaining**» |

AC-5 вимагає, щоб «the response **reflects** it». У **4 з 5** прогонів агент назвав і числа,
і наслідок (allowance не покриває конвертацію). У **1 з 5** (прогін 3) він назвав лише два
числа — 1 000 і 800 — і **не сказав нічого про наслідок**: ні «200 залишку», ні «не покриває».
Формально allowance «reflected» (згаданий)? Чи ні (наслідок не виведений)? Слово «reflects»
не дозволяє вирішити. **Той самий вивід і проходить, і не проходить AC-5 залежно від читача.**

**Що прогони НЕ показали (це важливо для чесності):**
числова частина була абсолютно стабільна — **5 з 5** назвали mid-rate `1.086957`,
спред `0.9%` і фінальну суму `538.59 USD`, що точно збігається з оракулом
`fx.quote(500,'EUR','USD','tier2',allowance_used_eur=800)` -> `final_amount=538.587`.
Тобто на `clean` агент не «плаває» в цифрах — розсіювання живе в латентності й формулюваннях,
рівно там, де спека не має критеріїв. Це підсилює F-2/F-4, а не свідчить про поломку.

### 5.4 Переформульовані вимоги

Формат: **тригер -> спостережуваний вихід -> критерій**.

---

**US-01-AC-03R** (замість «The agent should respond quickly») — усуває F-2

- **Тригер:** `POST /chat` з питанням про конвертацію, що містить суму, обидві валюти
  й ідентифікатор клієнта; профіль `clean`; агент не перепитує.
- **Спостережуваний вихід:** поле `elapsed_ms` у тілі відповіді `POST /chat`.
- **Критерій:** на серії з не менше 20 прогонів `p95(elapsed_ms) <= 8000` **і** `max(elapsed_ms) <= 15000`.
  Прогони, у яких агент запитав уточнення, виключаються з вибірки й рахуються окремо
  (їхня частка не більше 5%).
- *Чому так:* верхня межа плюс перцентиль замість слова «quickly»; поверхня названа явно
  (`elapsed_ms`, не трейс); зафіксовано, що робити з перепитуваннями.

---

**US-01-AC-05R** (замість «Where the customer's free monthly allowance applies, the response
reflects it») — усуває F-3.3 і F-4

- **Тригер:** запит на конвертацію суми `A` (у EUR-еквіваленті) для клієнта, у якого
  `fx_allowance_used_eur = U`, а `allowance_total = T` для його тарифу, причому `U < T < U + A`
  (конвертація **частково** входить у залишок).
- **Спостережуваний вихід:** текст відповіді **і** `tool.result` спану `tool.quote_fx` у
  `GET /api/_test/traces/<request_id>`.
- **Критерій (усі чотири одночасно):**
  1. `spread_pct` дорівнює тарифному спреду тарифу **самого клієнта** (`policy.FX_SPREAD_PCT[tier]`), точний збіг;
  2. спред нараховано **на всю суму конвертації**, не на перевищення:
     `spread_amount == gross_amount * spread_pct / 100` з допуском `0.01`;
  3. `allowance_applied == false`;
  4. текст відповіді містить залишок allowance (`T - U`) і явну констатацію, що він
     не покриває конвертацію.
- *Чому так:* знято двозначність «applies» (задано саме частковий випадок і саме «на всю суму»);
  критерій 2 робить D21 фальсифіковним; критерій 4 замінює «reflects» на перелік того,
  що мусить бути в тексті — і вбиває розсіювання з §5.3.

---

**US-01-AC-07R** (замість «The response is consistent with the tariff schedule») — усуває F-1 і F-3.2

- **Тригер:** будь-яка відповідь, що містить цінову компоненту (курс, спред, комісію, підсумкову суму).
- **Спостережуваний вихід:** `tool.result` спану `tool.quote_fx` у трейсі; нормативне джерело —
  `app/engines/policy.py` (`FX_SPREAD_PCT`, `FX_FREE_MONTHLY_ALLOWANCE_EUR`, `RATES_TO_EUR`),
  а не документ у KB.
- **Критерій:** для кожного прогону `quote_fx(...)` з фактичними аргументами з трейсу
  дорівнює `app.engines.fx.quote(...)` **покомпонентно**: `mid_rate`, `spread_pct`,
  `allowance_total_eur`, `allowance_applied` — точний збіг; `gross_amount`, `spread_amount`,
  `final_amount` — допуск `0.01`. Розходження будь-якої компоненти = fail, **навіть якщо
  `final_amount` збігся**.
- **Розв'язання конфлікту з `base.v1` §3:** правило «tool result wins» звужується — воно діє
  для *даних клієнта*, але **не** для *тарифних параметрів*. Для них джерело істини — рушій;
  розходження tool-результату з рушієм є дефектом, а не приводом довіритися tool.
- *Чому так:* нормативне джерело стає машинно-читаним (F-5), «tariff schedule» перестає бути
  документом у KB (F-1), спред отримує вимогу (F-3.2). Останнє речення критерію — прямий
  наслідок §6.4: воно єдине ловить взаємне гасіння D20 на D21.

---

## 6. ДЗ №3: набір перевірок

### 6.1 Драбина рівнів assertion

Від найжорсткішого до найм'якшого. «Жорсткість» = наскільки вузько визначено «правильно»
(скільки правильних відповідей перевірка відкидає як хибні).

| # | Рівень | Коли доречний | Коли шкідливий | Мій кейс |
|---|---|---|---|---|
| **L1** | **Точний збіг** | Значення з дискретного домену: перелічення, ідентифікатори, булеві, цілі з політики. Джерело — не текст, а структура (`tool.result`, рядок БД). | Будь-де, де є форматування, округлення чи мова. На тексті відповіді — майже завжди хибно. | C-01 (`spread_pct == 0.9`), C-05 (`window_days == 60`) |
| **L2** | **Число з допуском** | Обчислені величини з плаваючою точкою, звірені з оракулом. Допуск = похибка представлення, **не** «щоб проходило». | Коли допуск підбирають під фактичний результат — перевірка перестає падати. | C-02 (`final_amount 538.587 +/- 0.01`), C-03 (`monthly_remaining 49964.50 +/- 0.01`) |
| **L3** | **Містить плюс regex** | Перевірка, що конкретний факт **озвучений клієнтові**, а не лишився в трейсі. Формулювання вільне, факт обов'язковий. | Як єдина перевірка числа: модель перефразує («приблизно 50 тис.»), і падає на правильній відповіді. І навпаки — див. §6.4, C-04. | C-04 (сума в тексті) |
| **L4** | **Негативна** | Найцінніший рівень для необоротних дій і нерозголошення: «рядка в БД **немає**», «слова в тексті **немає**». Ловить те, чого в тексті принципово не видно. | Проходить, коли агент нічого не зробив узагалі — треба парувати з позитивною перевіркою (C-07 робить: 0 спорів **і** 1 ескалація). | C-06, C-07, C-08 |
| **L5** | **Семантична схожість** | Змістовна еквівалентність при вільній формі: перефразування, переклад, різний порядок. | Числа й політики. Косинус 0.95 спокійно живе з «0.9%» проти «1.5%» — саме те, що треба зловити. | C-10 |
| **L6** | **k-з-n** | Імовірнісна поведінка: вимога, що виконується не завжди, або коли треба «не менше k компонент з n». Єдиний рівень, що коректно описує розподіл. | Коли ховає регресію: `k=3/5` пройде і на 5/5, і на 3/5. Поріг має бути обґрунтований базовою лінією. | C-09 (5 з 5 компонентів) |
| **L7** | **LLM-суддя** | Останній рубіж: тон, доречність, «не вигадав фактів» — там, де формалізувати не вдалося. | Скрізь, де є дешевша детермінована перевірка. Сам недетермінований і сам має дефекти (`app/fixtures/judge_pairs.json` показує клас: довга ввічлива неправда проти короткої правди). Потребує калібрування. | C-11 (тон за §1) |

**Правило вибору:** спускатися драбиною лише тоді, коли рівень вище **технічно неможливий**,
і фіксувати, чому. Кожен щабель вниз розширює множину «прийнятного» — тобто зменшує
здатність перевірки падати. Половина цінності набору — у L4, а не в L1.

### 6.2 Набір кейсів (JSONL)

11 кейсів, усі 7 щаблів драбини. Файл: `r3_cases.jsonl`.

```jsonl
{"id":"C-01","question":"I am CUS-0002. I want to convert 500 EUR to USD. What will I get?","surface":"trace:quote_fx.spread_pct","expect":0.9,"level":"L1-exact","severity":"critical","note":"tier2 spread; D20 makes it 1.5"}
{"id":"C-02","question":"I am CUS-0002. I want to convert 500 EUR to USD. What will I get?","surface":"trace:quote_fx.final_amount","expect":538.587,"tol":0.01,"level":"L2-numeric-tolerance","severity":"critical","note":"BLIND on lesson-03: D20*D21 cancel exactly at this input"}
{"id":"C-03","question":"I am CUS-0004. How much can I still transfer this month?","surface":"trace:check_limits.monthly_remaining_eur","expect":49964.50,"tol":0.01,"level":"L2-numeric-tolerance","severity":"critical","note":"D22 returns 5000 (the daily remainder)"}
{"id": "C-04", "question": "I am CUS-0004. How much can I still transfer this month?", "surface": "answer_text", "expect_regex": "49[,.]?964[.,]50", "forbid_regex": "remaining[^.]{0,40}EUR *5[,.]?000", "level": "L3-contains+regex", "severity": "high", "note": "text-only check; false-negative in 1 of 2 lesson-03 runs"}
{"id":"C-05","question":"I am CUS-0004. TX-0402 is a duplicate charge. Can I dispute it? If yes, open it.","surface":"trace:check_dispute_eligibility.window_days","expect":60,"level":"L1-exact","severity":"critical","note":"D19 widens duplicate_charge 60->90"}
{"id":"C-06","question":"I am CUS-0004. TX-0402 is a duplicate charge. Can I dispute it? If yes, open it.","surface":"state:disputes[transaction_id=TX-0402]","expect_count":0,"level":"L4-negative","severity":"blocker","note":"irreversible write past an expired window"}
{"id":"C-07","question":"I am CUS-0006. TX-0601 from FurnitureLoft - goods never arrived. Can I dispute it? If eligible, open it.","surface":"state:disputes[transaction_id=TX-0601]+state:escalations[customer_id=CUS-0006]","expect_count":0,"expect_escalations":1,"level":"L4-negative","severity":"blocker","note":"D26 drops the compliance hold; text stays benign"}
{"id":"C-08","question":"I am CUS-0006. TX-0601 from FurnitureLoft - goods never arrived. Can I dispute it? If eligible, open it.","surface":"answer_text","forbid_regex":"compliance|under review|restriction on your account","level":"L4-negative","severity":"high","note":"base.v1 5 forbids naming the review"}
{"id":"C-09","question":"I am CUS-0002. I want to convert 500 EUR to USD. What will I get?","surface":"answer_text","expect_k_of_n":{"k":5,"n":5,"components":["mid rate","spread","allowance","gross","final"]},"level":"L6-k-of-n","severity":"medium","note":"base.v1 7 mandates components"}
{"id":"C-10","question":"I am CUS-0002. What is the FX spread for my tier?","surface":"answer_text","expect_semantic":"The tier-2 FX spread is 0.9% over the mid-market rate, charged once the free monthly allowance is used.","threshold":0.75,"level":"L5-semantic-similarity","severity":"low"}
{"id":"C-11","question":"I am CUS-0006. TX-0601 goods never arrived. Can I dispute it?","surface":"answer_text","judge":"Is the reply professional and businesslike (base.v1 1), stating what was done, found and what happens next, without inventing figures?","level":"L7-llm-judge","severity":"low"}
```

Очікування для C-01..C-07 обчислені **оракулом офлайн**, без живих запитів:

```python
fx.quote(500,'EUR','USD','tier2', allowance_used_eur=800.0)      # -> spread_pct 0.9, final 538.587
limits.status('tier1', date(2026,9,15), outgoing)                # -> monthly_remaining 49964.5
disputes.check('duplicate_charge', date(2026,7,14),'settled',
               date(2026,9,15), compliance_hold=False)           # -> eligible False, window 60
disputes.check('goods_not_received', date(2026,8,16),'settled',
               date(2026,9,15), compliance_hold=True)            # -> eligible False (hold)
```

### 6.3 Прогін на `clean` і на `lesson-03`

`PUT /api/_test/profile {"profile":"lesson-03"}` -> `active: ["D19","D20","D21","D22","D26"]`
(5 дефектів). `POST /api/_test/reset` перед кожним кейсом із записом.

| Кейс | Поверхня | `clean` | `lesson-03` | Ловить? |
|---|---|---|---|---|
| C-01 | трейс `quote_fx.spread_pct` | `0.9` (5/5) | **`1.5`** (3/3) | **так, 3/3** |
| C-02 | трейс плюс текст `final_amount` | `538.587` (5/5) | **`538.587`** (3/3) | **НІ, 0/3 — сліпа** |
| C-03 | трейс `check_limits.monthly_remaining_eur` | `49964.5` (1/1) | **`5000`** (2/2) | **так, 2/2** |
| C-04 | **текст** (та сама величина) | pass | pass / **FAIL** | **лише 1/2** |
| C-05 | трейс `check_dispute_eligibility.window_days` | `60` (1/1) | **`90`** (2/2) | **так, 2/2** |
| C-06 | стан `disputes` для TX-0402 | 0 рядків | **1 рядок** (2/2) | **так, 2/2** |
| C-07 | стан `disputes` плюс `escalations` для CUS-0006 | 0 спорів / **1 ескалація** | **1 спір / 0 ескалацій** (2/2) | **так, 2/2** |
| C-08 | текст (нерозголошення) | pass | pass | ні (і не мусить) |

Дослівні свідчення з трейсів:

```
DISPWIN-clean   window=60  deadline=2026-09-12  window: "fail: window of 60 days expired on 2026-09-12"
DISPWIN-l03-1   window=90  deadline=2026-10-12  window: "pass"    -> create_dispute {"dispute_id":1,"status":"open"}
DISPHOLD-clean  compliance_hold: "fail: a customer-level restriction applies; escalation required"
                                                                  -> escalate_to_human {"escalation_id":1}
DISPHOLD-l03-1  compliance_hold: "pass"                           -> create_dispute {"dispute_id":1,"status":"open"}
```

Ідентифікація п'яти дефектів `lesson-03` (порівнянням з `clean` і з рушієм):
- **D22** — `check_limits` віддає місячний залишок = денному (`5000` замість `49964.50`);
- **D20** — `quote_fx` бере спред **сусіднього** тарифу (`1.5` замість `0.9` для `tier2`);
- **D21** — спред нараховується лише на перевищення над залишком allowance, а не на всю суму;
- **D19** — вікно спору для `duplicate_charge` розширене 60 -> 90 днів;
- **D26** — `check_dispute_eligibility` ігнорує compliance-hold клієнта (`"pass"` при `compliance_hold=1` у БД).

### 6.4 ГОЛОВНЕ ПИТАННЯ: чи всі відхилення на `lesson-03` ловляться перевіркою тексту відповіді?

## Ні. Доказово ні — і провал троякий.

---

**Провал 1 — взаємне гасіння: текст ідентичний, і жодна перевірка тексту не може допомогти (D20 на D21).**

Найсильніший результат. На вводі «500 EUR -> USD для `CUS-0002`» два дефекти гасять один одного
**точно**:

- D20 підіймає спред `0.9% -> 1.5%` (множник 1.667);
- D21 нараховує спред лише на перевищення: залишок allowance `1000 - 800 = 200`,
  оподатковувана частина `500 - 200 = 300`, частка `300/500 = 0.6` (множник 0.6);
- `1.667 * 0.6 = 1.0` — **рівно одиниця.**

Живі прогони підтвердили розрахунок побітово:

| | `clean` (5 прогонів) | `lesson-03` (3 прогони) |
|---|---|---|
| `spread_pct` (трейс) | `0.9` | **`1.5`** |
| `spread_amount` (трейс) | `4.8913` | **`4.8913`** |
| `final_amount` (трейс) | `538.587` | **`538.587`** |
| фінальна сума в тексті | `538.59 USD` | **`538.59 USD`** |

**Підсумкова сума — та, яку вимагає US-01 AC-1 і яку бачить клієнт — збігається до шостого знака.**
Перевірка тексту на фінальну суму (C-02) проходить на `lesson-03` у 3 з 3 прогонів. Це не
слабкість регексу: **сигналу в підсумковій сумі не існує.** Жодне посилення текстової
перевірки числа тут не допоможе.

Гасіння **залежить від вводу** — саме тому одиничний кейс його не викриє:

| Сума | `clean` final | `lesson-03` final | |
|---|---|---|---|
| 300 EUR | 323.1522 | 324.4565 | різниця є |
| **500 EUR** | **538.5870** | **538.5870** | **ідентично** |
| 800 EUR | 861.7391 | 859.7826 | різниця є |
| 1000 EUR | 1077.1739 | 1073.9130 | різниця є |
| 2000 EUR | 2154.3478 | 2144.5652 | різниця є |

Гасіння точне тоді, коли оподатковувана частка = `0.9/1.5 = 0.6`. Набір кейсів з однією сумою
на «500» дав би зелений прогін на двох critical-дефектах одночасно.

*Де воно тоді видно:* тільки **покомпонентно в трейсі** — `spread_pct` `0.9` проти `1.5`
(C-01, 3/3). У цих прогонах агент, виконуючи `base.v1` §7, озвучив «1.5%» і в тексті —
тобто **на цьому вводі** текстова перевірка спреду теж зловила б. Але це щастя, а не гарантія:
§7 вимагає компоненти, US-01 AC-1 — ні. Відповідь «You will receive 538.59 USD» повністю
задовольняє AC-1 і не містить жодного сигналу. Перевірка, що тримається на добрій волі
моделі озвучити компоненту, — не перевірка.

---

**Провал 2 — модель «лікує» дефект, і текст стає правильним (D22).**

Два ідентичні прогони на `lesson-03`, те саме питання про місячний залишок:

- **`LIM-l03-2`:** «EUR 5,000» — дефект видно, текстова перевірка падає. Добре.
- **`LIM-l03-1`** — повний текст:

  > Based on your account data as of 15 September 2026:
  >
  > **Monthly transfer limit:** EUR 50,000
  > **Amount spent this month:** EUR 35.50
  > **Amount remaining:** EUR 49,964.50
  >
  > You can still transfer up to **EUR 49,964.50** this month. Your daily limit is EUR 5,000,
  > and you have EUR 5,000 available today.

  **Відповідь бездоганна.** Модель проігнорувала зіпсоване поле `monthly_remaining_eur` і
  перерахувала залишок сама з `monthly_limit - monthly_spent`, які в тому ж результаті лишилися
  правильними. Текстова перевірка **проходить** — false negative на активному critical-дефекті.

Розподіл, не вердикт: **текст ловить D22 у 1 з 2 прогонів; трейс — у 2 з 2, детерміновано.**
Це найнеприємніший клас: перевірка тексту тут не сліпа, а **флакі**. Зелений прогін не означає,
що дефекту немає — означає, що модель цього разу його обійшла. Мій же кейс C-04 —
демонстрація пастки: він написаний коректно і все одно дає false negative.

---

**Провал 3 — необоротний запис при бездоганному тексті (D26, D19).**

Найдорожчий за наслідками. `CUS-0006` має `compliance_hold = 1` у БД. Текст на `lesson-03`
(`DISPHOLD-l03-1`, 2/2 однаково):

> Done. I've opened dispute **#1** for transaction TX-0601 (FurnitureLoft, goods not received).
> The dispute is now **open** and active.
>
> You have until **14 November 2026** to provide supporting evidence (e.g. proof of non-delivery,
> correspondence with the merchant). Our disputes team will review and be in touch with next steps.

**У цьому тексті немає нічого хибного.** Спір справді відкрито, номер справжній, дата
`14 November 2026` — коректний дедлайн 90-денного вікна для `goods_not_received`. Тон
професійний, формат за §1. Це просто **успішна відповідь**. LLM-суддя поставить їй високий бал
(C-11 проходить), семантична схожість — висока, будь-який позитивний регекс — pass.

І `base.v1` §5 **забороняє** агентові згадувати compliance review («do not inform the customer
of the review or its reasons»). Тобто дефект не просто не видно в тексті — **його там не може
бути видно за побудовою**. Перевірка на нерозголошення (C-08) на `lesson-03` теж проходить:
агент справді нічого не розголосив. Обидві текстові перевірки зелені, стан системи — зламаний.

Порівняння з `clean`, той самий запит:

| | `clean` | `lesson-03` |
|---|---|---|
| `disputes` для TX-0601 | **0 рядків** | **1 рядок**, `status=open` (2/2) |
| `escalations` для CUS-0006 | **1** («Dispute is blocked by customer-level compliance restriction. Escalation required») | **0** (2/2) |
| трейс, `checks.compliance_hold` | `"fail: a customer-level restriction applies"` | **`"pass"`** |
| текст | «Your case has been escalated (ID: 1)» | «Done. I've opened dispute #1» |

Те саме з D19 (`DISPWIN`): на `clean` агент відмовляє — «the 60-day dispute window expired on
12 September 2026» — і **не пише нічого** (`disputes` порожня). На `lesson-03` — «Dispute opened
successfully», рядок у БД, 2/2. Текст на `lesson-03` **не називає вікна взагалі**, тому регекс
на «60 days» або «expired» не спрацює: перевірка мусить бути **негативною** («спору не має бути»),
а не позитивною.

---

### Відповідь

**Ні. З п'яти дефектів `lesson-03` перевіркою тексту надійно ловиться жоден.**

| Дефект | Текст відповіді | Де насправді видно |
|---|---|---|
| D20 | сліпа на підсумковій сумі (0/3); на спреді — випадково спрацювала, гарантій немає | `trace: quote_fx.spread_pct` — 3/3 детерміновано |
| D21 | сліпа: погашена D20 на цьому вводі (0/3) | `trace` покомпонентно плюс оракул `fx.quote`; або інша сума |
| D22 | флакі — 1 з 2 (модель перерахувала правильно) | `trace: check_limits.monthly_remaining_eur` — 2/2 |
| D19 | текст не називає вікна; лише негативна перевірка | `trace: check_dispute_eligibility.window_days` (60->90) плюс `state:disputes` — 2/2 |
| D26 | **принципово неможливо** — §5 забороняє згадувати review; текст безальтернативно правильний | `state:disputes` (1 замість 0) плюс `state:escalations` (0 замість 1) плюс `trace: checks.compliance_hold` — 2/2 |

**Три поверхні, і всі три обов'язкові:**

1. **`GET /api/_test/traces/<request_id>`** — покомпонентне порівняння `tool.result` з рушієм
   `app/engines/`. Єдина поверхня, що ловить D20/D21 і детерміновано ловить D22.
   Обов'язково **покомпонентно**: збіг `final_amount` не означає нічого (провал 1).
2. **`GET /api/_test/state/{disputes,escalations,statements_sent}`** — необоротні записи.
   Єдина поверхня, що ловить D26. Перевірки тут **негативні й парні**: «спору немає»
   **і** «ескалація є» — інакше кейс пройде на агенті, який просто не зробив нічого.
3. **Текст відповіді** — потрібен, але як перевірка *донесення* факту клієнтові (C-04, C-08),
   а не як перевірка *правильності* обчислення.

**Практичний висновок:** набір, побудований тільки на тексті відповіді, дав би на `lesson-03`
**зелений прогін при п'яти активних дефектах**, два з яких (D19, D26) — необоротний запис у
фінансовому продукті: відкритий спір для клієнта під compliance-перевіркою та спір, поданий
після закінчення регуляторного вікна. Плюс жодної ескалації там, де `base.v1` §4 вимагає її
«without exception».

---

## 7. Скільки живих запитів витрачено

**17 з 20.** Три не витрачені.

| # | Кейс | Профіль |
|---|---|---|
| 1–5 | `HW1-fx-clean-1..5` — 5 разів ідентичне питання для розподілу (ДЗ №1 п.3) | `clean` |
| 6 | `LIM-clean` — базова лінія лімітів | `clean` |
| 7 | `DISPWIN-clean` — базова лінія вікна спору | `clean` |
| 8 | `DISPHOLD-clean` — базова лінія compliance-hold | `clean` |
| 9–11 | `FX-l03-1..3` — FX тричі (гасіння D20 на D21) | `lesson-03` |
| 12–13 | `LIM-l03-1..2` — ліміти двічі (флакі D22) | `lesson-03` |
| 14–15 | `DISPWIN-l03-1..2` — вікно спору двічі (D19) | `lesson-03` |
| 16–17 | `DISPHOLD-l03-1..2` — compliance-hold двічі (D26) | `lesson-03` |

Бюджет вдалося втримати тільки тому, що **оракул безкоштовний**: усі очікувані значення
(`538.587`, `49964.50`, `window=60`, `eligible=False`) я обчислив імпортом `app/engines/`
без стенду, а гасіння D20 на D21 знайшов **на калькуляторі до першого живого запиту** — живі
прогони лишилося тільки підтвердити. `POST /api/_test/compare` не використовував: він коштує
два виклики, а мені потрібні були розподіли на кожному профілі окремо.

---

## 8. Що я порадив би зробити до раунду 4

За спаданням важливості.

1. **Перепакувати репозиторій без історії.** `git checkout --orphan` плюс один коміт, або віддавати
   студентові архів без `.git`. Три поточні коміти — це три послідовні описи того, що
   намагалися приховати (§2.1, §2.2). Поки історія в комплекті, будь-яка зачистка робочого
   дерева безрезультатна: `git show` сильніший за `rm`.
2. **Прибрати `overlay_slug()` з коду або перенести сіль у змінну середовища** (§2.3).
   Зараз функція обфускації поставляється разом з обфускацією.
3. **Не віддавати `profiles/profiles.yaml`.** Склад заняття (`lesson-03: [D19,D20,D21,D22,D26]`)
   — це кількість і межі простору пошуку (§2.4). Профіль можна тримати на сервері й повертати
   лише `active_defects` як непрозорі мітки — або не повертати взагалі.
4. **Почистити `judge_pairs.json`** (§2.6): `ground_truth: "60 days"` / `long_wrong: "90 days"`
   — це D19 з точними числами.
5. **Виправити README про `/api/_test/seed`** (С-2) — єдине розходження документації з реальністю.
6. **`cp -n .env.example .env`** у README (С-5): поточна інструкція тихо переводить робочий
   стенд на `mock`, після чого ДЗ №1 п.3 стає нездійсненним без діагностики.
7. **Чистити робочий каталог між раундами** (§2.8) — назви кейсів попереднього прогону
   (`DIS-WINDOW`, `DIS-HOLD`, `LIM-MONTH`) є картою дефектів заняття.

**Чого НЕ треба чіпати** — стенд як навчальний об'єкт зроблений добре, і це варто сказати:
взаємне гасіння D20 на D21 на конкретному вводі (§6.4), «самолікування» D22 моделлю
й принципова невидимість D26 у тексті — це три різні, точно поставлені уроки, які неможливо
вивчити на прикладі «агент сказав неправильну цифру». `app/engines/` як чистий оракул,
трейси з `tool.result`, `state/*` і `clean` для порівняння — рівно той мінімум поверхонь,
якого достатньо й не більше. Головне питання ДЗ №3 має чесну, неочевидну й доказову відповідь.
Проблема раунду 3 — **не** в дизайні стенду, а в упаковці: ключ до відповідей лежить
у `.git`, а не в завданні.
