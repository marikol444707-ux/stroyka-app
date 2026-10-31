# Ограниченная адаптация CI fixtures, 31.10.2026

Основание: CI run 41193535137 для PR395, head aa4e287278c2601232e9304a31b8069ffb3c3f1b; CI checkout merge 970e41992d7093ec541e364636a4d6db6458b1e4. Полный набор ранее завершился 5 failures / 4 errors. Этот follow-up не запускает полный набор и не меняет бизнес-код, права, CI или флаги.

## Review до изменения hash expectations

Сравнение acb1a3838a13cb650440340a774be46f1a3830a8 → aa4e2872:
- Весь production-пакет warehouse_recommendation_preview, backend/db.py и agent_jobs/handler_registry.py не менялись.
- В main.py parser `_parse_warehouse_anomaly_preview_company_ids` и полный условный блок регистрации `WAREHOUSE_ANOMALY_PREVIEW_HTTP_ENABLED` побайтно идентичны исходнику. Сохранены explicit enable, allowlist, cookie-session dependency, parser/runner binding и отсутствие регистрации через agent jobs.
- SHA256 parser: dcb440959ce91b8b599c69a04d26d887d3091d461093c290b1e6b76e5ba9f78f.
- SHA256 registration block: 8c43da5677aebf1d80eab054bd4194f468a8615559f4cebecd0e7c631666f650.
- Изменения main.py относятся к init_db, room-work ownership/sync, interim-act sums/sync, price-history, TB journal и version owner/connection cleanup. Список изменённых top-level определений и полный diff сверены статически; production main не импортировался.

Три ожидания полного main.py обновлены с b9053387fd398ad5919e6411dcd22160c6e5a04f004deb111af7e5133a88bbcd на 2bbaa5d092abad146e7c7fcacfcf097ae10fa814a4729e4d4d0b839431beb0c6 после этого review. Сам контроль полного файла сохранён. Дополнительно зафиксированы два неизменных protected-сегмента отдельным static test. Существующие проверки закрытого списка импортов, порядка authorize → resolve → prepare → collect → lease.guard, запрета прямых DB/HTTP/thread вызовов, приватного __all__ и отсутствия write-функций не удалялись и не ослаблялись.

## Fixture corrections

- supply_history contracts builder передаёт явные record_scope/get_current_user. Позитивное удаление получает конкретный successful owner lookup (5,), затем проверяет soft-delete и его ID. Worker test проверяет exact master_id и точные project/company joins, без fallback по имени.
- prescriptions supervisor update получает позитивную owner-строку (5,), явного директора и отдельно проверяет owner lock перед UPDATE. Autonumber проверяется по act_number после company_id/project_id/project_name, а не по прежнему params[1].
- ReleaseRevisionGraphTests ожидает единственный head 0108 и дополнительно проверяет каждый parent от 0102 до 0108. Проверка длины ВСЕХ revision IDs <=32 сохранена. Это чтение графа, не применение миграций и не запуск PostgreSQL.

## Допустимая проверка

Запущены адресно 10 методов: 5 названных fixture tests, 1 статический граф миграций, 3 исходных hash/static methods, 1 новый protected-segments static method. Все PASS. Выбраны полные dotted names конкретных методов; discover, PG-классы, runtime preview requests, UI/role сценарии и security/full-remainder не запускались. У тестов preview выполнялись только source/hash/AST assertions. Guards бизнес-кода не менялись. git diff --check PASS.

Логи и данные review сохранены в /workspace/stroyka-fixes-2026-10-31: ci-fixture-tests.log, CI_CONTRACT_REVIEW.json, ci-main-review.patch. Это локальная проверка совместимости тестов, не новый зелёный CI. Коммит не опубликован, CI не перезапущен.

## Уточнение остатка

ST-018 и ST-019 — исторические проблемы старого fixture/AI-adapter, позднее разблокированные согласно CONSOLIDATED_TECHNICAL_AUDIT.md. Их нельзя называть текущими универсальными блокерами. Текущие препятствия функциональной приёмки: не установлена точная граница прежнего отказа; не подтверждён разрешённый готовый synthetic UI-контур; новая схема/миграции и browser/multi-role приёмка не приняты. Этот коммит не снимает эти ограничения и не исправляет ST-013/014.
