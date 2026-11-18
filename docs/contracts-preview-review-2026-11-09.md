# Первый пакет: автоматический подбор договора и мобильный просмотр

09.11.2026, Москва. Основа — точный установленный commit `700a5c29309d674d35c66367625b409ad37528f5`, полученный чтением серверного Git в отдельную локальную копию. Ветка `fix/contracts-preview-20261109`. В рабочем приложении, БД и GitHub ничего не изменялось; push для origin этой копии отключён. Исходные исправления смет и мастера сохранены в основе.

## Исправления

1. Перенесена идея #326 с учётом более новой contractor_identity. Автоматический поиск использует только один точный черновик в company/project/package/user scope. Подписанные, закрытые и иные нечерновые договоры не выбираются автоматически. Два подходящих черновика дают 409 вместо произвольного выбора; пустой раздел нормализуется в «Основная». Сохранены advisory/row locks, точная идентичность пользователя и отсутствие подбора аккаунта по имени.
2. Из #391 перенесены только недостающие изменения просмотра договора: доступная с клавиатуры область горизонтальной прокрутки таблицы, перенос заголовка/кнопок, размеры и отступы мобильного окна. Текст, суммы и защитная очистка HTML сохранены; недействительный предпросмотр по-прежнему нельзя печатать.

**Граница договора:** это защита автоматического выбора, а не новый общий запрет изменения подписанных договоров. Более новый явный `contractorRef={type:'contract',id}` имеет отдельное поведение и существующие HTTP-тесты, в том числе выбор подписанного договора с подтверждённой идентичностью. Оно сохранено. Повтор ручной команды тоже не переводится на новый случайный договор. Если требуется полная неизменяемость всех подписанных договоров/строк, это отдельное изменение бизнес-правил и всех writers.

Новых назначений работ в кабинете мастера, миграций, зависимостей и feature flags пакет не добавляет. Проверка существующих work-assignment/distribute API не объявляет соответствующий новый пользовательский workflow реализованным.

## Доказательства RED → GREEN

| Проверка | До исправления | После |
|---|---|---|
| PostgreSQL automatic selector | 10 тестовых методов: 10 failed assertions с учётом subtests, 4 метода проходили. Подписанный вытеснял черновик, ambiguity не давала 409, пустой package не находил основной раздел | 10/10 PASS: точный scope, legacy NULL/empty, rollback и два конкурентных первых writer |
| PreviewModal regression | Новый тест не находил доступную область таблицы: 1 failed, 5 passed | 6/6 PASS в том же файле |
| Узкие backend unit | Актуализированы ожидания старого fetchone в двух route fixtures | 35/35 PASS: brigade_access, work_assignment, estimate_distribution |
| Typed selection/manual unit | Существующие правила | 9/9 PASS |
| Новые реальные HTTP/PostgreSQL | Проверяют интеграционную границу исправленного selector | 6/6 PASS: create/assignment/distribute × signed preservation и ambiguous 409/rollback |
| Совместимость explicit/manual HTTP/PostgreSQL | Существующие правила | 5+7=12 PASS, без пропусков |
| Frontend и связанные экраны | Первый узкий RED выше | 16+31=47 тестов в 7 непересекающихся suites PASS |
| Браузер компонента с реальными стилями приложения | На 320px таблица работ была block, scrollWidth 870px, отдельной доступной области не было | 320/390/1365px PASS: без горизонтального выхода страницы, кнопки в viewport; таблица прокручивается, печать получает обе строки и 59 500 руб., закрытие работает, pageErrors=0 |
| Frontend build | — | Compiled successfully; флаги взяты из последнего установленного выпуска, штатная verify-frontend-feature-build.py PASS |
| Статика | — | Python AST, CI YAML, git diff --check PASS |

Итого выполнено 72 backend test cases (44 unit + 28 PostgreSQL/HTTP) и 47 frontend tests. Это число запусков выбранных проверок, а не обещание полного покрытия приложения. Новый CI step запускает оба новых PostgreSQL-набора; GitHub CI этого ещё не опубликованного пакета не запускался.

Окружение: Python 3.12.13, PostgreSQL 15, Node 24.15.0/npm 11.12.1. Установленный сервер использует Python 3.12.3/PostgreSQL 16/Node 18.19.1; этот пакет на нём не собирался и не устанавливался. Build сообщил известное устаревание caniuse-lite и deprecation fs.F_OK; сборка успешна, зависимости массово не обновлялись.

Для БД использованы только новые socket-only кластеры с синтетическими данными. У нового launcher нет аргумента DSN/чужой базы; у существующих HTTP fixtures есть проверка пустой разрешённой базы, отключено чтение .env и внешние соединения. После проверок кластеры остановлены и удалены.

Браузерный стенд рендерит реальные PreviewModal/contractTemplates/App.css/index.css. Печать проверяется по переданному HTML, не физическим принтером. Один начальный assertion браузерного скрипта ошибочно искал число в HTML с `&nbsp;`; он исправлен на сравнение текстового содержимого. Это ошибка harness, не потеря суммы. Доступный рабочий браузер показал форму входа, авторизованной сессии нет: приёмка прошлой production-установки остаётся незавершённой, её резерв не удалялся.

## Изменённые файлы и назначение

| Файл | Зачем |
|---|---|
| backend/features/brigade_access/service.py | Только автоматический selector: черновик, ambiguity 409, нормализация раздела |
| backend/features/brigade_access/test_service.py | Проверки scope/результатов; переход fake cursor на fetchall |
| backend/features/brigade_access/test_draft_selection_postgres.py | Реальные SQL, блокировки, неоднозначность, изоляция, конкуренция |
| backend/features/brigade_access/test_draft_routes_postgres.py | Три реальные HTTP-точки, сохранность signed и полный rollback |
| backend/features/estimate_distribution/test_routes.py | Согласовать fake cursor с несколькими строками selector |
| backend/features/work_assignment/test_routes.py | То же для второго route fixture |
| scripts/run_brigade_draft_tests.py | Создать только собственную одноразовую тестовую БД и убрать её после проверки |
| .github/workflows/ci.yml | Явно выполнять оба новых PostgreSQL-набора вместо opt-in skip |
| src/components/PreviewModal.css | Прокрутка таблицы и мобильная компоновка |
| src/components/PreviewModal.jsx | CSS-классы оболочки и кнопок без изменения прав/печати |
| src/components/PreviewModal.test.jsx | Регрессия таблицы, данных для печати и закрытия |
| src/utils/contractTemplates.js | Доступная область таблицы; числовые расчёты не менялись |
| docs/contracts-preview-review-2026-11-09.md | Область, доказательства, воспроизведение и ограничения |

## Воспроизведение

Из отдельной полной копии приложения с Python 3.12 и зависимостями requirements.txt; PostgreSQL initdb/pg_ctl/createdb должны быть в PATH. Ни одну команду тестов не направлять в рабочую БД.

```sh
python scripts/run_brigade_draft_tests.py
python scripts/run_supplier_catalog_postgres_tests.py \
  backend.features.brigade_access.test_draft_routes_postgres.DraftSelectionRoutesPostgresTests
python -m unittest -v backend.features.brigade_access.test_service \
  backend.features.work_assignment.test_routes backend.features.estimate_distribution.test_routes \
  backend.features.contractor_identity.test_selection backend.features.contractor_identity.test_manual
python scripts/run_supplier_catalog_postgres_tests.py \
  backend.features.contractor_identity.test_contract_selection_postgres.ExactContractSelectionPostgresTests \
  backend.features.contractor_identity.test_manual_postgres.ManualBrigadePostgresTests
CI=true npm test -- --watchAll=false --runInBand --runTestsByPath \
  src/components/PreviewModal.test.jsx src/hooks/usePreviewInvalidation.test.js \
  src/components/MasterCabinetPage.contracts.test.js src/utils/performerUtils.test.js \
  src/components/MasterDocumentsPage.test.jsx src/components/QualityJournalConsumers.test.jsx \
  src/components/MobileEstimateSummary.test.jsx
```

Для сборки передать актуальные разрешённые REACT_APP-флаги из будущей среды, затем npm run build и штатную проверку флагов. Не использовать весь production environment или секреты для тестов. В выполненном прогоне использован сохранённый список frontend-флагов прошлого выпуска; свежие производственные флаги перед будущей установкой нужно сверить отдельно.

Логи и браузерный harness: `tmp/first-package-evidence/`. Исходные RED-логи сохранены, успешные прогоны без причины не повторялись.

## Выпуск и оставшаяся работа

Пакет подготовлен локально, установка не выполнялась. Миграция 0107_estimate_revisions остаётся без изменений. Перед выпуском нужны отдельное решение на установку, проверка актуальной серверной основы/флагов и текущих пользовательских черновиков, резерв по действующему порядку и согласованное переключение backend/frontend. Предыдущие подтверждения закрытия вкладок относятся к предыдущей установке.

При двух старых черновиках будет явный 409: никаких автоматических объединений, удалений или переноса строк. Откат к предыдущей паре не требует downgrade БД, но возвращает риск автоматического выбора подписанного договора; при проблеме сначала закрыть запись и сохранить новые операции. Очистка резервов только после четырёх проверок по docs/deployment-retention.md.

GitHub #374/#395/#397, склад #372, счета #392, статистика #401/#402, полноценный подрядчик/поддержка #403 и Jev в этот ограниченный пакет не включены. Основу удалось подготовить локально; синхронизация установленного commit с GitHub и публикация первого пакета ещё не выполнялись.
