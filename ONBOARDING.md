# ONBOARDING — stroyka-app

Короткий гайд для новой сессии Claude. Прочитай это первым делом — потом сможешь сразу работать.

## О пользователе

- **Уровень в разработке:** 1/10 (новичок, не пишет код руками сам)
- **Общаться:** по-русски, простыми словами, без жаргона
- **Объяснять:** что от чего зависит, логику решений с аналогиями
- **Не задавать вопросы:** требующие технических знаний — выбирать самому и объяснять почему
- Полная памятка: см. файлы в `/Users/nikolas/.claude/projects/-Users-nikolas-stroyka-app/memory/`

## Что за проект

**stroyka-app** — система учёта для строительной компании «СтройКа». Сметы, склад, выдача материалов мастерам, AI-помощник.

**Домен:** https://stroyka26.pro
**Репозиторий:** https://github.com/marikol444707-ux/stroyka-app (был публичный, рекомендовали сделать приватным — не подтверждено)

## Стек

- **Frontend:** React 19 (CRA) — монолит `src/App.js` ~4800 строк, inline-стили в JS
- **Backend:** Python FastAPI + PostgreSQL — `backend/main.py` ~110 KB монолит
- **AI:** YandexGPT-5.1 и qwen3.6-35b-a3b через OpenAI SDK (base_url=ai.api.cloud.yandex.net)
- **Сервер:** Ubuntu 24.04 (msk-1-vm-zh4n), nginx + systemd service `stroyka`, uvicorn на 8001
- **Деплой:** `cd /var/www/stroyka-app && bash deploy.sh` — git pull + npm build + restart

## Архитектура секретов

- `backend/.env` (gitignored) содержит `YANDEX_API_KEY`, `YANDEX_FOLDER_ID`, `DB_*`
- Мини-загрузчик в начале `backend/main.py` (без python-dotenv)
- `deploy.sh` БОЛЬШЕ НЕ патчит main.py через sed — креды теперь только из .env

## Роли и доступ

В коде `const ROLES` (около строки 55 App.js):
- `директор`, `зам_директора`, `бухгалтер` — полный доступ
- `прораб` — объекты + материалы + сканер накладных + контроль объекта
- `мастер`, `субподрядчик` — свои работы, видят выдачи материалов
- `кладовщик`, `снабженец` — склад
- `заказчик` — портал клиента (свой проект)
- `поставщик` — каталог + офферы

Дефолтные тестовые аккаунты:
- `admin@stroyka.ru` / `admin123` (директор)
- `prorab@stroyka.ru` / `prorab123` (прораб)
- `master@stroyka.ru` / `master123` (мастер)
- `buh@stroyka.ru` / `buh123` (бухгалтер)

## Что готово (по фичам)

### Сметы
- Импорт LSR/Grand Smeta из Excel — `/parse-smeta` (backend/main.py:1998)
- Парсер берёт цены работ из col[13], материалов из col[15], делает totalWork/totalMaterial раздельно
- В UI каждый раздел сметы делится на **🔨 Работы** и **📦 Материалы**
- ⭐ Шаблоны смет (`is_template` flag, копирование структуры при создании)
- 📜 История версий — таблица `estimate_versions`, snapshot при каждом PUT
- 🤖 AI-сравнение версий — `jsonOnly` через qwen, выдаёт diff
- 🤖 AI-генерация сметы из описания — `/ai-generate-estimate` (qwen + парсер с фолбэком)
- 🤖 AI-анализ сметы — структурированный JSON: top / sections / risks / actions
- 🤖 AI-проверка при импорте — фоновый запрос после парсинга, плашка с warnings
- 💬 Чат по смете — таблица `estimate_chat_messages`, диалог с памятью на 20 turns

### Материалы и склад
- Единый поток: кнопка **«Принять материал»** → диалог **📷 Скан / ✍️ Вручную** → форма накладной
- Сканер накладных через qwen → `/scan-invoice` → авто-заполнение формы
- При сохранении накладной материалы попадают на склад (warehouse_main или materials по project)
- Старые «примитивные» формы добавления материала удалены
- **Передача мастеру списывает со склада** (POST `/material-transfers` в транзакции, блокирует выдачу >stock)
- При работе мастер может указать использованные материалы — `materials_used` в work_journal, тоже списываются с транзакцией
- Подтверждение получения мастером — в БД через `material_transfers.signed`, не в localStorage

### Объект (Контроль)
- Блок «📊 Контроль объекта» на вкладке «Общее» проекта (только для leadership)
- 4 таблицы: прогресс по смете / план vs закуплено / выдачи / остаток на складе
- Матчинг work_journal ↔ estimate items через fuzzy token overlap (≥40% общих слов длиной ≥3)
- AI-сводка с кешем — таблица `project_ai_summary`, hash payload для определения свежести
- Кнопка «AI-сводка» становится «Обновить ИИ» при наличии кеша, плашка зелёная/жёлтая

### Сервис
- Все API endpoints прописаны в nginx whitelist в `/etc/nginx/sites-enabled/stroyka`
- `proxy_read_timeout 300s` (для долгих AI запросов)
- `client_max_body_size 25m` (для сканирования с фото)
- AI-чат имеет **fallback на вторую модель** если первая возвращает пустоту

## Структура БД (ключевые таблицы)

```
estimates(id, project_id, project_name, name, version, sections_json, is_template)
estimate_versions(id, estimate_id, version_label, sections_json, total, comment, created_at)
estimate_chat_messages(id, estimate_id, role, content, created_at)
project_ai_summary(project_name PK, payload_hash, summary, updated_at)
work_journal(id, master_id, project, description, quantity, materials_used, ...)
material_transfers(id, project_name, from_location, to_person, material_name, quantity, signed)
materials(id, name, project, quantity, unit, price, category)
warehouse_main(id, name, quantity, unit, price)
warehouse_history(material, type, quantity, date, project, issued_by, date_time)
```

## Особенности БД (важно при ошибках)

- Раньше таблицы создавались от `postgres`, потом приложение начало подключаться как `stroyka`
- Если backend падает с `must be owner of table` — выполнить от postgres:
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

## Точки входа в API (новые после серии правок)

- `/ai-chat` — общий AI, поддерживает `jsonOnly:true` и `skipContext:true`, с fallback
- `/ai-generate-estimate` — генерация сметы из описания
- `/estimate-chat`, `/estimates/:id/chat-history` — чат по смете
- `/estimates/:id/versions`, `/estimate-version/:id`, `/estimates/:id/toggle-template`
- `/material-transfers` — передача (POST списывает со склада)
- `/project-ai-summary`, `/project-ai-summary/:name` — кеш AI-сводки

## Известные нерешённые

- App.js — монолит, не разбит на компоненты
- main.py — монолит, не разбит на роутеры
- 2 eslint warnings в App.js помечены `eslint-disable-next-line` (useEffect dep, loop func)
- Тёмная тема — не сделана
- Push-уведомления — не сделаны
- Боковое меню/sidebar на мобиле — не доадаптировано после общей mobile-правки

## Известные пользовательские проблемы

- Repo пока публичный (по словам пользователя — не подтверждено приватизировано)
- Старый Yandex API-ключ был отозван, новый в `backend/.env`
- На сервере иногда падает web-консоль провайдера — лучше работать через SSH

## Текущий приоритет (по запросу пользователя)

Закончили рефакторинг (чистка warnings, mobile adaptation). Готовимся к дизайну: тёмная тема + единый стиль карточек.

## Workflow

- Работаем в worktree `claude/cool-bohr-af2b82`, мерджим в main, пушим в origin
- Деплой делает пользователь сам (`bash deploy.sh` на сервере)
- Не коммитить без явного «давай коммить»
- При проблеме спрашивать у пользователя что он видит на сайте + логи `journalctl -u stroyka -f`

## Полезные команды на сервере

```bash
# Деплой
cd /var/www/stroyka-app && bash deploy.sh

# Логи в реальном времени
journalctl -u stroyka -f

# Статус сервиса
systemctl status stroyka

# Тест nginx
nginx -t && systemctl reload nginx

# psql от postgres
su - postgres -c "psql stroyka"
```

## Стиль общения с пользователем

- Никаких терминов без объяснения. «.env» → «файл с настройками».
- Аналогии из быта: склад=мешок, рефакторинг=уборка в шкафу.
- Перед изменением: «я меняю X, это повлияет на Y, потому что Z».
- После: «что от чего зависит» + команды для сервера.
- Использовать **скриншоты** для диагностики UI-проблем — он умеет.

## Полная история коммитов (последние)

См. `git log --oneline -40` для актуального списка. Ключевые:
- `54b37fd` Прайс-листы → вкладка в Сметах
- `bea891c` AI-fallback при пустом ответе
- `f9d673c` Логи и устойчивый парсинг AI-генерации
- `7c66763` Мобильная адаптация
- `5bdb04b` Чистка warnings
- `4161b99` AI-генерация сметы
- `96c50ec` Чат по смете с памятью
- `3339a7d` Шаблоны + история версий + AI diff + AI import check
- `fcbd971` Списание материалов при работе
- `2f9ce88` Кеш AI-сводки контроля объекта
- `96444df` Дашборд «Контроль объекта»
- `db3e9c5` Списание материалов при передаче + ограничение сканера
- `271d3bc` Переключение анализа сметы на qwen
- `25c9f34` DB-креды в .env
- `4570dd7` Yandex-ключи в .env
