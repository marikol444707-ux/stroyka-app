# ONBOARDING — stroyka-app

Короткий гайд для новой сессии Claude. Прочитай первым делом — потом сможешь сразу работать.

## О пользователе

- **Уровень в разработке:** 1/10 (новичок, не пишет код руками сам)
- **Общаться:** по-русски, простыми словами, без жаргона
- **Объяснять:** что от чего зависит, логику решений с аналогиями
- **Не задавать вопросы:** требующие технических знаний — выбирать самому и объяснять почему
- **Решения принимаю я**, кроме продуктовых развилок ("общий прайс или по специализациям") и destructive операций (push, force, mass delete)
- Полная памятка: `/Users/nikolas/.claude/projects/-Users-nikolas-stroyka-app/memory/`

## Контекст проекта

**stroyka-app** — система учёта для строительной компании «СтройКа». Сметы, склад, выдача материалов, наряды бригадам, AI-помощник.

**Размер бизнеса:** ~40 сотрудников, разные бригады по специализациям, работа с ТД / ГПХ / Самозанятыми / ИП.

**Домен:** https://stroyka26.pro
**Репозиторий:** https://github.com/marikol444707-ux/stroyka-app (публичный — рекомендовали приватный)
**Воркфлоу:** работаем в worktree `claude/cool-bohr-af2b82`, fast-forward merge в main, push в origin. Деплой делает пользователь сам.

## Стек

- **Frontend:** React 19 (CRA) — монолит `src/App.js` ~5000 строк, inline-стили в JS, минимум классов в `src/App.css`
- **Backend:** Python FastAPI + PostgreSQL — `backend/main.py` ~120 KB монолит
- **AI:** YandexGPT-5.1 и qwen3.6-35b-a3b через OpenAI SDK (base_url=ai.api.cloud.yandex.net). Fallback между моделями встроен в `/ai-chat`
- **Сервер:** Ubuntu 24.04 (msk-1-vm-zh4n), nginx + systemd service `stroyka`, uvicorn на 8001
- **Деплой:** `cd /var/www/stroyka-app && bash deploy.sh` → git pull + npm build + systemctl restart

## Архитектура секретов

- `backend/.env` (gitignored): `YANDEX_API_KEY`, `YANDEX_FOLDER_ID`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`
- Мини-загрузчик в начале `backend/main.py` (без python-dotenv)
- `deploy.sh` БОЛЬШЕ НЕ патчит main.py через sed — креды только из .env

## Nginx whitelist

В `/etc/nginx/sites-enabled/stroyka` есть `location ~* ^/(endpoints|здесь|перечислены|...)`. **При добавлении нового endpoint** — обязательно проверь покрывает ли его префикс в whitelist, иначе nginx вернёт HTML вместо JSON (классическая ошибка `Unexpected token '<'`). `proxy_read_timeout 300s` для долгих AI запросов, `client_max_body_size 25m` для сканирования фото.

## Роли и доступ

`const ROLES` (около строки 55 App.js):
- `директор`, `зам_директора`, `бухгалтер` — полный доступ
- `прораб` — объекты + материалы + сканер накладных + контроль объекта + наряды
- `мастер`, `субподрядчик` — свои работы и наряды, выдачи материалов
- `кладовщик`, `снабженец` — склад
- `заказчик` — портал клиента
- `поставщик` — каталог + офферы

**Дефолтные тестовые аккаунты:**
- `admin@stroyka.ru` / `admin123` (директор)
- `prorab@stroyka.ru` / `prorab123` (прораб)
- `master@stroyka.ru` / `master123` (мастер)
- `buh@stroyka.ru` / `buh123` (бухгалтер)
- `zxc@mail.ru` / `12345` (мастер, создан вручную через SQL)

## Что готово (по фичам)

### 📋 Сметы (новый источник правды для всех работ)
- Импорт LSR/Grand Smeta из Excel (`/parse-smeta` `backend/main.py:1998`)
- Парсер берёт цены работ из col[13], материалов из col[15], делает totalWork/totalMaterial раздельно
- В UI каждый раздел делится на **🔨 Работы** и **📦 Материалы**
- **Inline-редактирование** каждой позиции (имя, ед, кол-во, цены) — PUT на blur
- **Колонки прогресса в каждой строке:** 👷 Кому (dropdown бригад) / ✅ Сделано / 📉 Осталось / 🔒 Скрытая работа (toggle)
- **При увеличении doneQuantity** — backend автоматически пишет в `work_journal` (status='Автоматически из сметы')
- **Если позиция помечена 🔒 (hiddenWork=true)** — backend дополнительно создаёт черновик в `hidden_works_acts` (АОСР)
- ⭐ Шаблоны смет (`is_template`, выбор при создании)
- 📜 История версий — `estimate_versions`, snapshot при каждом PUT, восстановление
- 🤖 AI-сравнение версий — `jsonOnly` qwen, выдаёт diff
- 🤖 AI-генерация сметы из описания — `/ai-generate-estimate`
- 🤖 AI-анализ сметы — структурированный JSON: top/sections/risks/actions
- 🤖 AI-проверка при импорте — фоновый запрос, плашка с warnings
- 💬 Чат по смете — `estimate_chat_messages`, диалог с памятью на 20 turns
- 👷 **Распределение сметы по бригадам** — POST `/estimates/:id/distribute` создаёт `brigade_contract` per бригаду + `brigade_contract_items` (LEGACY, рабочее но избыточное)

### 🎯 Работы мастера (новый flow — источник: смета)
- На странице «Работы» секция **«🎯 Мои работы по смете»** — позиции сметы где `brigadeName === user.name || === user.brigade`
- Мастер вводит «Сделано» — сохраняется в смету (sections_json.items[].doneQuantity)
- Backend при сохранении сам пишет в журнал и АОСР
- Старая секция «Наряды по объекту (старая система)» осталась для legacy
- Свободные работы через прайс остаются доступны если наряд не выбран

### 🏷️ Прайс-листы
- Доступ через вкладку в Сметах (не в сайдбаре)
- 4 способа создания:
  1. Ручной ✏️
  2. 🤖 AI-генерация из описания (`/ai-generate-pricelist`)
  3. 📋 Из сметы (`/pricelists/from-estimate`) — копирует позиции сметы как прайс, категория = раздел сметы
  4. Копирование существующего
- Каждая позиция имеет `item_type`: 'work' / 'material'
- При создании из сметы тип определяется автоматически по `itemType` или `priceWork`/`priceMaterial` сплиту
- Группировка в UI по фактическим категориям (не только хардкод-списку)

### 👷 Наряды бригадам (brigade_contracts)
- Опциональная привязка прайс-листа (`pricelist_id`)
- **Авто-подгрузка позиций из прайса** при создании наряда с прайсом
- **Кнопка «Подгрузить из прайса»** для существующих нарядов
- При подгрузке **берутся только работы** (item_type='work' или NULL), материалы пропускаются по умолчанию
- При подгрузке **объёмы берутся из сметы** этого проекта (fuzzy match по имени)
- **Inline-редактирование** план/факт прямо в таблице
- **Alert при превышении плана** ("Нельзя превышать план — это перебор по смете")
- Дублирование прайса в работах мастера скрыто когда наряд открыт

### 📦 Материалы и склад
- Единый поток: **«Принять материал»** → диалог **📷 Скан / ✍️ Вручную** → форма накладной
- Сканер накладных через qwen (`/scan-invoice`) → авто-заполнение формы
- При сохранении накладной материалы попадают на склад
- **Передача мастеру списывает со склада** (POST `/material-transfers` в транзакции, отказ если не хватает)
- При работе мастер может указать использованные материалы — `materials_used` в work_journal, автосписание
- Подтверждение получения мастером — в БД через `material_transfers.signed`

### 🏗 Контроль объекта
- Блок «📊 Контроль объекта» на вкладке «Общее» проекта (только для leadership)
- 4 таблицы: прогресс по смете / план vs закуплено / выдачи / остаток на складе
- Матчинг work_journal ↔ estimate items через fuzzy token overlap (≥40% общих слов ≥3 символа)
- AI-сводка с кешем — таблица `project_ai_summary`, hash payload для определения свежести
- Кнопка «AI-сводка» → «Обновить ИИ» при наличии кеша, плашка зелёная/жёлтая

### 👥 Персонал (объединённый раздел)
- **Вкладки:** 👥 Сотрудники / 📅 Табель / 💵 Сдельные (вкладка «Мастера» удалена — слилась с «Штатом»)
- **Расширенная форма** сотрудника со свёртываемыми секциями:
  - Базовое: ФИО (Фам/Имя/Отч), должность, специализация, телефон, объект, тип оплаты, статус, тип занятости
  - 🔐 Доступ в систему (опционально) — системная роль + email + пароль. **Валидация: либо все три, либо ничего**
  - 📄 Документы — паспорт, ИНН, СНИЛС
  - 💰 Финансы — банк, счёт, БИК
  - 📝 Дополнительно — даты, бригада, заметки
- **Раскрываемая карточка сотрудника** при клике на строку:
  - 4-картовая сводка (тип занятости, паспорт, ИНН, банк)
  - Договоры / Акты / Согласия ПД / Инструктажи ТБ (агрегированы из всех источников)
  - **Прочие документы** (custom `staff_documents`) — добавить с типом, файлом, датами
  - Последние работы
- **Раздел «Пользователи» удалён** из сайдбара — слился с Персоналом
- Кнопка «🔐 Выдать доступ» в строке если ещё нет user

## Структура БД (ключевые таблицы)

```sql
projects(id, name, client, status, budget, deadline, progress, tasks, pricelist_id, floors, liters)
estimates(id, project_id, project_name, name, version, sections_json, is_template)
estimate_versions(id, estimate_id, version_label, sections_json, total, comment, created_at)
estimate_chat_messages(id, estimate_id, role, content, created_at)
pricelists(id, name, description, for_who, coefficient)
pricelist_items(id, pricelist_id, name, unit, price, category, specialization, item_type)
brigade_contracts(id, project_id, project_name, brigade_name, contractor_type, contractor_id,
                  total_amount, status, signed_at, notes, pricelist_id, created_at)
brigade_contract_items(id, contract_id, description, unit, quantity, price_smeta,
                       price_brigade, done_quantity, estimate_section, created_at)
                       -- NB: description, не name! Нет колонки status!
materials(id, name, project, quantity, unit, price, category, min_quantity)
warehouse_main(id, name, unit, quantity, price, min_quantity, category)
warehouse_invoices(...)
warehouse_history(material, type, quantity, date, project, issued_by, date_time)
material_transfers(id, project_name, from_location, to_person, to_person_role,
                   material_name, quantity, unit, transfer_date, signed, notes)
work_journal(id, master_id, master_name, project, description, quantity, unit,
             price_per_unit, total, date, status, materials_used, photo_url)
staff(id, name, role, phone, salary, project, pay_type,
      ... 31 поле для расширенной карточки)
staff_documents(id, staff_id, doc_type, title, file_url, status, signed_at, expires_at, notes)
project_ai_summary(project_name PK, payload_hash, summary, updated_at)
hidden_works_acts(id, project_name, estimate_id, act_number, work_name, section_name, brigade,
                  quantity, unit, price_per_unit, total, work_date, materials_used, project_docs,
                  conclusion, signed_customer, signed_supervisor, signed_contractor,
                  signed_subcontractor, status, comments, created_at)
                  -- АОСР: создаётся автоматически при заполнении doneQuantity по позиции с hiddenWork=true
users(id, name, email, password, role, project_id, project_name)
master_profiles(id, user_id, full_name, passport, inn, contract_type, ogrnip, bank_account,
                bank_name, phone, specialization)
contracts(id, master_id, contract_number, project, start_date, end_date, signed_at, status)
interim_acts(id, master_id, act_number, project, period_from, period_to,
             total_amount, paid_amount, status)
pd_consents(id, user_id, signed_at, scan_url, uploaded_by)
tb_journal(id, project_name, instructor, instruction_type, date, master_name, ...)
```

## Особенности БД (ловушки)

- **Таблицы создавались от `postgres`**, потом приложение начало подключаться как `stroyka`. Если backend падает с `must be owner of table`:
  ```sql
  DO $$ DECLARE r RECORD; BEGIN
    FOR r IN SELECT tablename FROM pg_tables WHERE schemaname='public' LOOP
      EXECUTE 'ALTER TABLE public.' || quote_ident(r.tablename) || ' OWNER TO stroyka';
    END LOOP;
    FOR r IN SELECT sequence_name FROM information_schema.sequences WHERE sequence_schema='public' LOOP
      EXECUTE 'ALTER SEQUENCE public.' || quote_ident(r.sequence_name) || ' OWNER TO stroyka';
    END LOOP;
  END $$;
  ```
- **`brigade_contract_items` использует `description`, не `name`!** Также нет колонки `status` — статус вычисляется на лету по `done_quantity` vs `quantity`. Это legacy таблица созданная вручную раньше моих правок.
- **`work_journal` уже имеет колонку `description`** (не `name`).
- При ALTER TABLE моих новых колонок — использовать `ADD COLUMN IF NOT EXISTS` чтобы не сломать существующее.

## API endpoints (новые/важные)

- `/ai-chat` — общий AI, `jsonOnly:true` → qwen, иначе yandexgpt; с fallback на другую модель
- `/ai-generate-estimate` — генерация сметы из описания
- `/ai-generate-pricelist` — генерация прайс-листа из описания
- `/pricelists/from-estimate` — копирование сметы в прайс
- `/estimates/:id/distribute` — распределение позиций сметы по бригадам (POST с assignments)
- `/estimates/:id/ai-distribute-suggest` — AI предлагает распределение по бригадам
- `/brigade-contracts/:id/load-from-pricelist` — копирует позиции прайса в наряд, объёмы берутся из сметы проекта (`?with_materials=1` чтобы включить материалы)
- `/estimate-chat`, `/estimates/:id/chat-history` — чат по смете
- `/estimates/:id/versions`, `/estimate-version/:id`, `/estimates/:id/toggle-template`
- `/material-transfers` — передача мастеру (POST списывает со склада)
- `/project-ai-summary`, `/project-ai-summary/:name` — кеш AI-сводки
- `/staff/:id/profile` — досье сотрудника (все документы из всех источников)
- `/staff/:id/documents`, DELETE `/staff-documents/:id` — custom документы
- `/hidden-works-acts` (GET с ?project_name=) — список АОСР
- PUT/DELETE `/hidden-works-acts/:id` — обновление и удаление АОСР
- PUT `/estimates/:id` — теперь дополнительно автоматически пишет в `work_journal` и `hidden_works_acts` при изменении doneQuantity. Возвращает `{ok, journalEntries, hiddenWorkActs}` с количеством созданных записей.

## 🗺 ROADMAP — план развития системы

> Активный список задач. Каждая выполненная — **удаляется** из roadmap в том же коммите что и реализация.
> Приоритеты: 🔥 критично · 🟡 важно · 🟢 опционально
> Объём: S (≤1 час) · M (1-3 часа) · L (3-6 часов) · XL (1+ день)
> Идём по порядку Ф1 → Ф2 → … Каждая фаза = отдельный коммит + push, после которого пользователь проверяет.

<!-- Ф1.2 закрыта: модалка КС-6а работает (формально это и есть переключатель); две точки печатных форм сделаны намеренно — Документы проекта для прорабов/технадзора, Бухгалтерия→По объектам для финансов -->



<!-- Ф4.1 закрыта: SMS-подпись решили не делать (пока «впиши ФИО» хватает) -->

### 🟢 Ф5a.2 — Что осталось от Ф5a.1 [M]

- [ ] Полная автоинтеграция Поставщик→Бухгалтер (поставщик в портале загружает счёт → автосоздание supplier_invoice)
- [ ] Уведомление снабженцу при утверждении счёта
- [ ] Реестр движений по подотчёту (история выдач/возвратов)

### 🟢 Ф5b.2 — Что осталось от Ф5b.1 [M]

- [ ] 💬 Чат с прорабом — текущая коммуникация по объекту (нужна привязка messages по project_id)
- [ ] PDF-экспорт документов вместо HTML-печати (weasyprint/pdfkit)

### 🟢 Ф6.2 — Что осталось от Ф6.1 [M]

- [ ] Журнал ТБ во фронте по ГОСТ 12.0.004-2015 (форма с типом инструктажа + кнопка «🤖 Сгенерировать текст» — backend готов)
- [ ] Версионирование критических документов (АОСР, КС-2 — snapshot, бэк готов: таблица document_versions)
- [ ] Журнал авторского надзора (если есть проектная организация)
- [ ] Расширить интеграцию audit_log на остальные endpoints (сейчас только update_hidden_works_act + pay_hidden_works_act)

### 🟢 Ф7.1 — Что осталось от Ф7 [S]

- [ ] UI вкладка для inspection_orders (журнал замечаний ГСН/Роспотребнадзор) в Документы проекта (бэк готов: GET/POST/PUT/DELETE /inspection-orders)
- [ ] Полноценные модели АОСК как отдельной сущности с подписями (сейчас печать берёт данные из АОСР по эвристике)

### 🟢 Ф8 — Специальные журналы (по выбору каких видов работ) [M each]

- [ ] Журнал **сварочных** работ (РД-03-606-03) — для металлоконструкций
- [ ] Журнал **бетонных** работ (ГОСТ 31108-2020) — для монолитных конструкций
- [ ] Журнал монтажа **сборных ж/б** конструкций
- [ ] Журнал **антикоррозийной** защиты металлоконструкций
- [ ] Журнал **изоляционных** работ (гидро/тепло)
- [ ] Журнал **свайных** работ — если есть свайный фундамент

### 🟡 Ф9 — Расширенный материальный учёт [M]

- [ ] М-2 — Доверенности на получение материалов у поставщика
- [ ] М-8 — Лимитно-заборные карты (месячный лимит материала на мастера/объект)
- [ ] Расчёт потребности материалов из сметы (автоматический по объёмам и нормам расхода)
- [ ] Связка «оплачено → доставлено → смонтировано» — единый статус по каждой позиции
- [ ] UI для заявок на снабжение от прорабов (таблица `supply_requests` уже есть в БД)
- [ ] **Бронирование материалов на складе** — резерв под конкретный наряд до выдачи мастеру

### 🟢 Ф10 — Гарантийный период [M]

- [ ] Гарантийные обязательства после сдачи объекта (срок гарантии, контактное лицо)
- [ ] Учёт дефектов в гарантийный период (отдельная таблица `warranty_defects`)
- [ ] Гарантийный ремонт — отдельные записи в журнале работ с пометкой «гарантия»

### 🟢 Ф11 — Непредвиденные работы (полная версия) [M]

- [ ] AI-оценка стоимости непредвиденной работы по прайсу или аналогии с похожими позициями сметы
- [ ] Лимит % от суммы сметы — автоматическое уведомление leadership при превышении
- [ ] Версионирование договора — каждое доп.соглашение увеличивает версию договора
- [ ] Журнал доп.соглашений (история всех ДС по объекту)
- [ ] Печать доп.соглашения по форме (новая `buildAdditionalAgreementContent`)

### 🛠 Инфраструктура (вписываем между фазами по мере необходимости)

- [ ] Автоматический бэкап БД в Яндекс.Облако (cron `pg_dump`, раз в сутки)
- [ ] Восстановление пароля (email-токен)
- [ ] 2FA для критических ролей (директор, бухгалтер)
- [ ] PDF-экспорт через библиотеку (weasyprint / pdfkit) вместо браузерной HTML-печати
- [ ] Доделать мобильную адаптацию (sidebar на мобиле)
- [ ] QR-коды для документов (быстрый доступ на стройке)
- [ ] Глобальный поиск по документам / журналам
- [ ] Email / Telegram уведомления (расширение внутренних плашек)
- [ ] **Хранилище файлов в Яндекс.Объект-стор** (S3-совместимое) вместо `/uploads` на сервере — иначе упрётся при росте
- [ ] **Мониторинг ошибок** (Sentry) — чтобы видеть падения у пользователей
- [ ] **Защита API** — rate limits, токены вместо паролей в заголовках, проверка прав на каждый endpoint
- [ ] **Сроки хранения документов** — по закону первичка 5 лет, личные дела 75 лет; авто-архивация и предупреждения при удалении

### 👥 Кабинеты ролей на доработку (когда дойдут руки)

- [ ] **Главный инженер** — полноценный кабинет (как у прораба, но шире)
- [ ] **Стройконтроль** (от подрядчика) — выдача предписаний и осмотры (как у технадзора, но изнутри)
- [ ] **Снабженец** — заявки от прорабов + сравнение цен поставщиков
- [ ] **Кладовщик** — рабочее место для приёма/выдачи материалов
- [ ] **Сметчик** — нормативные расценки, шаблоны смет
- [ ] **Менеджер CRM** — воронка, лиды, звонки
- [ ] **Поставщик** — расширение портала (отзывы, история заказов)
- [ ] **Мастер Stage 2** — AI-проверка документов, генератор договоров, импорт Excel

### 🏗 Бизнес-функции которые не вошли в фазы

- [ ] **Договор подряда с заказчиком** как отдельная сущность — приложения, доп.соглашения, расчёты, гарантия (сейчас `contracts` только для мастеров)
- [ ] **Договоры с субподрядчиками** — полный субподрядный договор (сейчас только наряды бригадам)
- [ ] **График Ганта** для этапов — сетевой график (сейчас просто список этапов)
- [ ] **Календарное планирование работ** — увязка work_journal во времени, ресурсы
- [ ] **Эквайринг** — если планируете принимать оплату от физлиц картой
- [ ] **Multi-tenancy** — несколько стройкомпаний на одной системе (только если будете продавать систему)

### 🌐 Интеграции (опц., только при запросе)

- [ ] 1С Бухгалтерия — обмен документами
- [ ] СБИС / Контур.Диадок — ЭДО
- [ ] Госуслуги / ЕСИА — для ФЗ-44 / ФЗ-223
- [ ] Банк-клиент — выгрузка выписки, авто-сверка платежей
- [ ] Тендеры — сравнение поставщиков по нескольким предложениям
- [ ] БИМ-модели (Revit / Renga) — для крупных объектов

### 🐛 Техдолг и мелочи

- [ ] `App.js` — монолит 5000+ строк, разбить на компоненты
- [ ] `backend/main.py` — монолит 120 KB+, разбить на роутеры
- [ ] 2 eslint warnings с `eslint-disable-next-line` (useEffect dep, loop func)
- [ ] Тёмная тема
- [ ] Контроль общей суммы нарядов vs смета по объекту (чтобы суммарно по всем нарядам не превысило смету)
- [ ] Дублирующие nginx-конфиги в `/etc/nginx/sites-enabled/` (warnings про conflicting server name)
- [ ] `.claude/` добавить в `.gitignore`

## Известные пользовательские особенности

- Repo пока публичный (приватизация не подтверждена)
- Старый Yandex API-ключ был отозван, новый в `backend/.env`
- На сервере иногда падает web-консоль провайдера — лучше работать через SSH
- Пользователь иногда вводит команды на экране входа в систему вместо терминала

**АОСР** — это унифицированная форма по СНиП 12-01-2004. Отдельный документ от КС-2 (`interim_acts`). Используется для приёмки работ которые закрываются другими конструкциями (армирование под бетон, гидроизоляция под облицовку, утепление под отделку и т.п.). Требует подписей: представитель заказчика / технадзор / генподрядчик / субподрядчик.

**Что нужно сделать в следующей сессии:**
1. Обсудить с пользователем какую форму нужно генерировать (стандартная по СНиП или своя)
2. Сделать UI: вкладка «Скрытые работы» в проекте, список АОСР с возможностью открыть карточку
3. Карточка АОСР: реквизиты, материалы, ссылки на ПД, поля для подписей, кнопка «Печать»
4. Подпись через геолокацию / фото подписи / простая отметка

### Текущая радикальная перестройка нарядов
Сделано — смета теперь источник правды:
- В смете у каждой позиции колонки 👷 Кому / ✅ Сделано / 📉 Осталось / 🔒 Скрытая работа
- У мастера на странице «Работы» появилась секция «🎯 Мои работы по смете» (фильтр по brigadeName == user.name или user.brigade)
- Старая вкладка «Наряды» в проекте переименована в «старая система», но осталась для legacy данных
- brigade_contracts остались как реестр контактов и договоров

### Следующие шаги (по выбору пользователя)
- UI для АОСР (см. выше)
- Stage 2 карточки сотрудника (AI-проверка документов, генератор договоров)
- Тёмная тема
- Push-уведомления
- Доделка мобильной адаптации
- Окончательное удаление старой вкладки «Наряды (старая система)» когда все привыкнут к новому flow

## Workflow

- Worktree `claude/cool-bohr-af2b82`, fast-forward merge в main, push в origin
- Деплой — пользователь сам через `bash deploy.sh` на сервере
- **Не коммитить без явного «давай коммить»** — кроме случаев когда явно идёт работа над фичей
- При проблеме спрашивать что видит на сайте + логи `journalctl -u stroyka -f`
- **Скриншоты** — пользователь умеет (Cmd+Shift+4 на маке)
- Часто использовать **AskUserQuestion** для развилок где нужно его мнение

## Полезные команды на сервере

```bash
# Деплой
cd /var/www/stroyka-app && bash deploy.sh

# Логи в реальном времени
journalctl -u stroyka -f

# Последние 30 строк логов
journalctl -u stroyka -n 30 --no-pager

# Статус сервиса
systemctl status stroyka | head -10

# Тест и перезагрузка nginx
nginx -t && systemctl reload nginx

# psql от postgres
su - postgres -c "psql stroyka"

# Быстрая SQL-команда от postgres
su - postgres -c "psql stroyka -c \"SELECT ...\""

# Просмотр пользователей
su - postgres -c "psql stroyka -c \"SELECT id, email, role, name FROM users ORDER BY id;\""

# Создать тестового мастера
su - postgres -c "psql stroyka -c \"INSERT INTO users (name, email, password, role) VALUES ('Имя', 'email@x.ru', 'pass', 'мастер');\""
```

## Стиль общения с пользователем

- Никаких терминов без объяснения. «.env» → «файл с настройками».
- Аналогии из быта: склад=мешок, рефакторинг=уборка в шкафу.
- Перед изменением: «я меняю X, это повлияет на Y, потому что Z».
- После: «что от чего зависит» + команды для сервера.
- Используй **скриншоты** для диагностики UI-проблем — пользователь умеет их делать.
- **AskUserQuestion** — для развилок где нужен его выбор; не использовать для технических вопросов

## Полная история коммитов (последние, для ориентации)

См. `git log --oneline -60` для актуального списка. Ключевые вехи:

**Эстимат-центричный flow (последние):**
- `4050f9d` Auto-create work_journal entries and АОСР drafts on done qty change
- `44e7300` Estimate-centric workflow: brigade & done qty inline in estimate
- `613759f` Brigade contract: align row cells with reordered header
- `f908889` Show 'Осталось' (remaining)
- `a519f9b` UI polish: tabs, sums card, brigade button gradient

**UI/UX полировка:**
- `a519f9b` UI polish: tabs, sums card, brigade button gradient

**Карточка сотрудника и Персонал:**
- `5e02254` Employee profile expandable card with documents (Stage 1)
- `6cf48f6` Collapse Masters tab, single employees list
- `98f5c2a` saveStaff validate access trio, surface errors
- `17054a8` Merge users into staff form

**Наряды и прайсы:**
- `56bc820` Alert when done > plan
- `816d672` Load-from-pricelist pulls qty from estimate
- `f9cfcde` Hide duplicate pricelist on works page
- `58b8fbc` Editable planned qty, fix done input when plan=0
- `d968d2a` Pricelist items: work vs material, filter brigade autoload
- `a0c78b7` Fix brigade_contract_items column mismatch
- `22cc8b3` Auto-load brigade items from pricelist
- `7e17be0` Distribute estimate items to brigades
- `2d2c10c` Brigade pricelist binding
- `c102f51` Pricelist from estimate
- `605c590` AI-generated pricelist

**Сметы:**
- `c127ef4` Inline edit estimate items
- `1403d91` Parser cost capture, split works/materials in UI
- `3339a7d` Templates + history + AI diff + AI import check
- `96c50ec` Estimate chat with memory
- `4161b99` AI-generate-estimate

**Склад / материалы:**
- `fcbd971` Deduct materials on work entry
- `db3e9c5` Material transfer deducts stock, scan role-gated
- `0141c80` Unified receipt flow scan/manual

**Контроль объекта:**
- `2f9ce88` Cache AI summary per project
- `96444df` Object control dashboard

**Безопасность и инфра:**
- `25c9f34` DB creds to .env
- `4570dd7` Yandex keys to .env

**Чистка:**
- `5bdb04b` Cleanup warnings
- `7c66763` Mobile adaptation
