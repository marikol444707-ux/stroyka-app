# Стройка — локальные исправления подтверждённых дефектов, 31.10.2026

Статус: код исправлений подготовлен на отдельной локальной ветке `fix/audit-stabilization-20261031`. База: `acb1a3838a13cb650440340a774be46f1a3830a8`. Итоговый commit указан в сопровождающих артефактах `COMMIT.txt`. Это не завершённый полный аудит и не готовность к публикации. Production, рабочие данные, внешние сервисы и флаги не изменялись. Push, PR, merge и deployment не выполнялись.

## Дополнение ко второму пакету и реестр

Статус «изменено» означает наличие кода, а не закрытый реальным сквозным тестом дефект.

| ID | Локальное изменение | Проверка и предел |
|---|---|---|
| ST-001 | Точные company_id/project_id для rooms/windows/doors; проверка родителя и блокировка в транзакции. Смежные room-works и синхронизация из ЖПР также получают owner и company-scoped поиск дублей | Unit и статические контракты. Не выполнена реальная PostgreSQL/ролевая приёмка |
| ST-002 | Projects загружает складские источники для соответствующих ролей; основная сверка и финансовый блок ждут готовности. Кеш и отложенные результаты учитывают company scope. Единое правило procurementEligible для «Докупить»; счётчик переименован в «Позиций по накладным» | Hook/unit tests и сборка. Нужна браузерная проверка исходного A→склад→A→reload, дополнительных панелей и пагинации |
| ST-003–007 | Ошибки HTTP/сети не выдаются за сохранение помещения, окон/дверей, допработы, инструктажа и этапа; формы/неподтверждённые drafts сохраняются | Mock frontend tests. Частичное сохранение комнаты сохраняет подтверждённый parent ID; это не общая атомарная batch-команда |
| ST-008 | Сохранён контекст объекта при навигации, поиск объектов/клиентов передаёт ID; URL хранит страницу/объект/вкладку, восстановление проверяет доступность объекта | Hook tests. Частично: складские search-results несут entity ID, но точное открытие карточки материала/инструмента ещё не реализовано; другие документы/формы не имеют общего deep-link контракта |
| ST-009 | navigateTo больше не стирает выбранный объект склада при быстрой выдаче | Hook regression; реальные формы/браузер не пройдены |
| ST-010 | Общий ref блокирует двойной клик; UUID команды сохраняется при неопределённом сетевом результате. POST /projects хранит команду в той же транзакции, повтор возвращает существующий объект; другой payload с тем же ключом даёт 409 | Unit tests frontend/backend. Нужна миграция 0108 и PG concurrency. Ключ в браузере не переживает refresh; старые клиенты без requestKey сохраняют прежнее поведение |
| ST-011 | Погода явно обозначена как локальные данные браузера | Код/сборка. Общая командная синхронизация не добавлялась |
| ST-012 | Известные ALTER перенесены после CREATE estimates, warehouse_main, work_journal, interim_acts, hidden_works_acts; новые owner-колонки без присвоения компании 1 | AST contract test. Чистый bootstrap и полная цепочка миграций не запускались, ST-012 не принят |
| ST-013 | Панель честно сообщает, что доступен черновик запуска, а применение не реализовано | Код/сборка. Полный workflow запуска не внедрён |
| ST-014 | Не изменялся: требуется утверждённая матрица зрелости release/ролей/флагов | Открытый продуктовый/приёмочный пункт, а не блокер независимых правок кода |
| ST-015 | Сигнал входного контроля включает фильтр незакрытых записей и сбрасывает scroll; полный печатный журнал явно подписан и использует все записи | Код/сборка. Реальный браузерный сценарий не повторялся |
| ST-016 | Legacy act-scan PUT проверяет HTTP-успех; сетевой отказ не разблокирует локальную оплату | Код/сборка. Нужен UI negative path и серверная приёмка основания оплаты |
| ST-017 | Группы вкладок переведены на native button с aria-expanded | Сборка/существующий unit набор. Tab/Enter/focus в реальном браузере не проверены |
| ST-018–019 | Исторические блокеры fixture документов и устаревшего AI-test adapter | Стенд и заблокированный тест не восстанавливались. Нового результата нет |
| ST-020 | Существующий 404 на чужой DELETE не заменён на 403 | Нужен согласованный контракт и persisted-state контроль; прежнее несовпадение ожидания не доказательство утечки |
| ST-021 | Табель фильтруется по владельцу staff и выбранной роли; toggle блокирует сотрудника | Unit. Toggle намеренно остаётся переключателем, не идемпотентной командой |
| ST-022 | Чек-листы/пункты привязаны к точному project_id и выбранной компании; owner lock при изменении | Unit; неприсвоенные legacy-записи недоступны |
| ST-023 | material-price-history фильтрует покупки по доступной компании/объектам до расчёта статистики | Изолированно скомпилированный handler + mock SQL; публичный каталог поставщиков сохранён |
| ST-024 | document-versions хранит владельца и проверяет текущий typed parent hidden_works_act; внешний snapshot ограничен скалярными публичными полями | Unit/static. Старые версии без owner скрыты; неизвестные типы не открываются. Сохранение истории остаётся отдельной транзакцией от изменения документа |
| ST-025–027 | Inspection orders, contracts, project chat: exact owner при списках и mutations, selected-company роль; masterId договора проверяется в разрешённой компании | Unit/mock scope. Старые записи без owner не backfill по имени; name-only вызовы при неоднозначном parent отклоняются |
| ST-028, ST-030 | PD consents и master profiles доступны управляющим только для разрешённых users/memberships; отозванная membership не превращается в legacy fallback; личный self-profile сохранён | Unit. Модель остаётся user-owned: профиль участника нескольких компаний не разделён на отдельные company-owned копии. Не утверждается новая бизнес-политика согласий/профилей |
| ST-029 | Только собственные supplier-documents POST/DELETE исключены из несовместимой company billing middleware; проверки supplier ownership в handler сохранены | Unit. Реальная middleware/HTTP приёмка не запускалась |
| ST-031–033 | Supervisor acts, interim acts и журнал ТБ используют exact owner; interim-act work IDs/contract и daily sync учитывают компанию | Unit/static. Некоторые legacy read-пути требуют выбора одной компании (409 в агрегированном режиме). Полный multi-membership UI не принят |
| ST-034 | Новая миграция 0105 восстанавливает refund/credit/reversal семантику SQL guard, сохраняя сравнение даты из 0072 | Статическая проверка SQL, миграция не применялась. Возврат и зависимые цепочки не перезапускались |
| ST-035 | Импорт кандидатов: явный ON CONFLICT(company_id,source,identity_key), autocommit=False | Unit. Дополнительная уникальность URL может дать контролируемый конфликт; автоматического слияния разных идентичностей нет. Real-PG upsert/batch rollback не принят |
| ST-036 | POST project-payments: autocommit=False и company advisory lock перед существующей проверкой дубликата с непустым note | Unit. Это запись учёта, не банковский перевод. Пустой note/остальные writers не объявлены идемпотентными; concurrent PG не запускался |
| ST-037 | Include/reconcile смет теперь транзакционные: существующие row locks/rollback работают в общей транзакции | Unit. PostgreSQL rollback/concurrency не проверены |
| ST-038 | CRM approve-worker/approve-supplier/create-invite/transfer-documents используют autocommit=False | Unit. Не заявляется полная дедупликация приглашений и разных CRM-лидов |

Дополнительно исправлена подпись команды карты директора: «Открыть задачи» отражает фактический переход вместо обещания создать задачу.

## Совместимость и обязательные условия перед выпуском

Новые миграции 0103–0108 НЕ применены. Они добавляют точных владельцев rooms, legacy project records, document_versions, room_works, восстанавливают settlement guard и вводят project_create_requests. Исторические миграции не переписаны. До согласованного применения новой схемы изменённые handlers нельзя выпускать.

Данные владельцев не присваиваются по названию. Legacy-записи без достоверного owner останутся недоступны; нужен проверяемый план их сопоставления по авторитетным связям. Это намеренный запрет доступа, не удаление данных. Downgrade части миграций запрещает автоматическую потерю owner/command identities. Требуются schema review и отдельная процедура отката.

URL основных API сохранены; room POST сохраняет прежние snake_case поля и добавляет owner IDs. Новое requestKey проекта необязательно для старых клиентов. Shared user-owned profiles/consents, name-based legacy assignments, ограниченная проекция document snapshots и single-company legacy reads требуют отдельного бизнес/совместимого review.

## Фактически выполнено

- **155 backend unit/static-contract tests PASS** в последнем едином запуске (`backend-tests.log`). Первоначальные 70 входят в эти 155; повторы не суммируются.
- **71 frontend unit/hook test PASS**, 7 suites (`frontend-tests.log`). Первоначальные 43 входят в эти 71.
- Python AST всех изменённых/новых Python файлов и `git diff --check`: PASS (`static-checks.log`).
- Финальная локальная production-сборка frontend: PASS, exit 0 (`frontend-build.log`). Это не публикация.
- Review diff: проверены место регистрации RecordScope, owner-joins/параметры, transaction boundaries, взаимный порядок CREATE/ALTER, сохранение response-форматов, закрытие version DB connection и повтор после сетевой ошибки. Это собственное ревью, не независимая приёмка.

В mock fixtures позитивный RecordScope подставлен для адаптации старых unit-тестов; новые негативные тесты отдельно проверяют отказ без mutation. Такие тесты не доказывают реальные SQL permissions и всю ролевую матрицу.

Команды финального набора:

```sh
.venv/bin/python -m unittest backend.features.rooms.test_routes backend.features.project_checklists.test_routes backend.features.checklist_items.test_routes backend.features.timesheet.test_routes backend.features.customer_cabinet.test_record_scope backend.features.project_payment_access.test_routes backend.features.crm.test_routes backend.features.estimate_changes.test_include_routes backend.features.inspection_orders.test_routes backend.features.project_chat.test_routes backend.features.pd_consents.test_routes backend.features.master_profiles.test_routes backend.features.interim_acts.test_routes backend.features.document_versions.test_routes backend.features.job_candidates.test_routes backend.features.supplier_access.test_subscription_scope backend.features.legacy_project_records.test_scope backend.features.legacy_project_records.test_main_contracts backend.features.projects.test_routes -q
CI=true npm test -- --watchAll=false --runInBand --runTestsByPath src/features/navigation/appNavigationRuntime.test.js src/features/projects/projectCrudActions.test.js src/components/ProjectTabsNav.test.js src/utils/materialReconciliationUtils.test.js src/features/project-operations/projectOperationActions.failures.test.js src/features/project-operations/projectOperationActions.companyRequisites.test.js src/features/data-loaders/useAppDataLoaders.test.js
CI=true BUILD_PATH=/tmp/stroyka-fix-build-20261031 GENERATE_SOURCEMAP=false npm run build
git diff --check
```

Промежуточные ошибки проверки: старые mocks не содержали нового scope, ожидания SQL требовали обновления; JSDOM не предоставлял UUID crypto. Fixtures адаптированы, продуктовые guards не ослаблялись. Последние наборы полностью прошли. Сохранились предупреждения datetime.utcnow/Browserslist/Node; зависимости не обновлялись.

## Измеримый остаток и блокеры

1. **Код частично/не реализован:** ST-008 (точное открытие складских результатов/общий контракт deep links), ST-013 (применение запуска остаётся недоступно и теперь явно обозначено), ST-014 (матрица зрелости). Это оставшаяся продуктовая работа, не технический запрет unit-тестов. Не внедрялся редизайн или новый launch workflow.
2. **Не приняты в PostgreSQL:** ST-001, ST-010, ST-012, ST-021–038. Нужны согласованная схема/миграции, свои позитивные и чужие отрицательные контроли, persisted state, rollback/concurrency. Текущий проход не запускал PG и не восстанавливал ранее заблокированный широкий security-аудит.
3. **Не приняты в реальном UI:** ST-002–010, ST-015–017, переходы ролей/компаний, mobile. Mock hooks не заменяют браузер.
4. **Исторические блокеры/контракт:** ST-018, ST-019, ST-020 не получили нового результата. Требуют отдельного разрешённого тестового маршрута/адаптера/согласования HTTP ожидания.
5. Успехи тестов этого патча не закрывают весь каталог 648 карточек/43 маршрутов и не доказывают всех 22 обозначений ролей.

В этом проходе новых отказов автоматического согласования не было. Ранее запрещённый запуск не повторялся и не обходился другим инструментом, агентом или стендом. Новый стенд не создавался. Отдельное разрешение на безопасный способ будущей PG/браузерной приёмки не означает снятия прежнего запрета.

## Сохранение и очистка

Код и регрессионные тесты сохранены локальным коммитом этой ветки; `changes.patch` содержит diff от указанной базы до commit, `CHANGED_FILES.txt` — полный список. Отчёт и логи находятся в `/workspace/stroyka-fixes-2026-10-31`; краткая копия отчёта включена в репозиторий `docs/audit-fixes-2026-10-31.md`.

Временная сборка `/tmp/stroyka-fix-build-20261031` удаляется после фиксации результатов; подтверждение — `RESOURCE_MANIFEST.json`. Новых БД, контейнеров, копий репозитория нет. Исходный checkout, исторические отчёты, доказательства и прототип дизайна сохранены.
