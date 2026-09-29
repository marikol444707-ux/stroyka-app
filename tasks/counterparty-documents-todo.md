# Документы контрагентов — исполнение

План: [counterparty-documents-plan.md](counterparty-documents-plan.md).

- [x] Проверить существующие архивы и привязку договоров к КП.
- [x] Зафиксировать решение пользователя: покупатель = плательщик.
- [x] Определить разделы кабинетов, единый оригинал, публикацию и изоляцию.
- [x] Уточнение пользователя: отдельный архив каждой компании, в том числе одного владельца; без объединённого архива «Все компании».
- [ ] D0. Read-only инвентаризация документов/владельцев/связей и исходные контрольные суммы.
- [ ] D0a. Изоляция существующих юрдокументов: список/создание/удаление/вложения/смена компании, до расширения архива.
- [ ] D1a. Серверное правило покупатель = плательщик для новых версий.
- [ ] D1b. Две стороны в формах; исторические версии без изменений.
- [ ] D2a. Добавочный реестр и связи без копирования оригиналов.
- [ ] D2b. Изолированные список/поиск/карточка/скачивание.
- [ ] D2c. Раздел документов выбранной компании: «Моя компания / Поставщики / Заказчики»; настройки открывают тот же архив юрдокументов.
- [ ] Контрольная точка A: формы, реестры двух компаний, тесты/сборка.
- [ ] D3a. Договор пары контрагентов, срок/область действия и версии.
- [ ] D3b. Однократная загрузка/распознавание/проверка.
- [ ] D3c. Выбор договора для нескольких КП и счетов.
- [ ] D3d. Допсоглашения/архив и сохранение исторических связей.
- [ ] D4a. Адресная передача версии и права на сам файл.
- [ ] D4b. Библиотека поставщика по компаниям-покупателям.
- [ ] D4c. Библиотека заказчика по разрешённым объектам, входящие файлы.
- [ ] D4d. Запрос исправления, новая версия, внутреннее уведомление.
- [ ] D5. Dry-run и идемпотентное подключение подтверждённых старых документов.
- [ ] Контрольная точка B: цепочка сторон, изоляция, проверенный перенос.
- [ ] D6. Финальные проверки, выпуск, проверка рабочего сайта и очистка резерва.

Не объявлять реализацию завершённой по наличию этого плана.


## Дополнение: автозаполнение реквизитов

См. `tasks/requisites-autofill-matrix.md`: проверенные разрывы, источники, потребители и проверки.
- [ ] D1c. Единый источник реквизитов, разрешение конфликтов и неизменные снимки документов; подключение всех потребителей по матрице.

2026-09-28: правила закреплены в AGENTS.md. D0a, серверный шаг: CRUD company-documents ограничен выбранной компанией и эффективной ролью, загрузка проверяет владельца защищённого файла, автор определяется сервером. 13 маршрутных unit-тестов прошли (включая соседние маршруты). Не развёрнуто; D0a остаётся открытым до проверки файлового доступа, UI при смене компании и интеграционного/браузерного прогона.

2026-09-28, D0a UI: SettingsPage получает выбранную компанию, фильтрует документы по владельцу, закрывает общий режим; операции передают явный company header, ошибки не сбрасывают форму, поздняя загрузка после смены компании игнорируется. 3 UI-теста прошли; 48 тестов company_documents/document_access прошли; production build успешен. Проверен вызов authorize_file перед выдачей tenant-files content. Браузерный прогон, инвентаризация старых ссылок и установка ещё не выполнены; D0a не закрыт.

2026-09-28: выпуск 28f84354 установлен. 51 серверный тест и 3 UI-теста прошли, БД/schema OK, 251 frontend-файл совпал, финансовые/складские контрольные суммы неизменны. В рабочем браузере архив показывает документы 1/2/3 компании 1, файлы 265/266/267 дают 200; запрос файла 265 с контекстом компании 2 отклонён 409. Мобильная ширина/scrollWidth 390/390. Владельцы трёх старых документов восстановлены по точным активным file_ownership-ссылкам, оригиналы не изменены. Резерв выпуска удалён после четырёх проверок. Следующий шаг D1c: единый источник реквизитов и сохранение снимков; дальнейшие сквозные сценарии матрицы остаются обязательными.

2026-09-28, D1c первый шаг (локально): contract-review-context передаёт полную карточку компании через company_requisites_to_api вместо одного названия/ИНН. Существующие разрешения сторон и сохранённые снимки не изменяются. Пропущенные поля не дополняются выдуманными должностями/основаниями; реквизиты компании не подставляются поставщику. Добавлены проверки backend и формы. Остальное покрытие матрицы, конфликты источников и выпуск этого шага ещё впереди.

2026-09-28, D1c второй локальный шаг: реквизиты поставщика берутся из точной карточки supplier_id утверждённого КП, bank/account/kor_account преобразуются в bankName/rs/ks; отсутствующее основание полномочий не придумывается. Форма сохраняет исходное значение карточки рядом с распознанным текстом и ручным вводом; применение OCR остаётся явным. Добавлены тесты независимых сторон и конфликта банка. Ещё не выпущено; полный охват матрицы, отказ от отдельного плательщика и браузерная проверка впереди.

2026-09-28, D1 локально: новые версии сторон не могут вводить отдельного плательщика; историческая отличающаяся пара может сохраняться неизменной. Для одной компании форма показывает две стороны и передаёт реквизиты покупателя также плательщику; сервер сохранения договора отклоняет различающиеся реквизиты одной компании. Тесты: 19 backend прошли, 15 PostgreSQL-тестов пропущены без настроенной БД; 6 UI прошли. Установка и сквозной PostgreSQL/браузерный прогон этой группы изменений ещё не выполнены.

2026-09-28: deployed 3facb676. All 34 PostgreSQL tests passed (no skips), including immutable snapshots, unified parties, bank conflicts, access and concurrency. Production browser: VIST offer, two party tabs, both bank/account profiles filled, review checkbox unchecked, no real contract saved. 251 frontend files verified; financial/stock/contract hashes unchanged; mobile width/scrollWidth 390/390; no JS errors. Four release gates passed; backup cleaned. Remaining matrix consumers and shared archive are still pending.

2026-09-28 D0 initial live read-only inventory: 3 company legal files with exact ownership; 15 project document records with no scan_url; supplier_documents and supplier_contract_versions empty. No owner/reference conflicts in these four sources. Report: tasks/counterparty-documents-inventory.json. Supplier invoices, quotations and shipment attachments are separate sources and remain to inventory before D0 completion. No data changed. Inventory command uses REPEATABLE READ and read-only transaction; two unit tests passed.

2026-09-28 D0 procurement inventory (read-only): 7 offers (companies 1/2), 49 invoices, 2 deliveries, 54 warehouse records. Explicit attachment fields contain one protected offer reference and one protected invoice reference; remaining records have no attachments in those fields. No ownership conflicts found in observed references or selected parent links. 47 invoices have no offer link and must remain standalone, not inferred by name/amount. Report expanded in tasks/counterparty-documents-inventory.json; five inventory unit tests passed. No production mutations or release required for this diagnostic step. D2 registry must distinguish business records from attached files and preserve independent source IDs.

2026-09-28 D2 initial API projection (local, not deployed): company-document-archive reads company_documents/supplier_documents without copying originals. Selected-company leadership only, search/pagination, safe file status. Five route tests passed. Read-only SQL rehearsal: company 1 returns 3 available records, company 2 returns zero (synthetic actors; not production auth proof). See docs/company-document-archive.md. Remaining sources, archive UI and browser verification are pending; D2 is not complete.

2026-09-28 D2 procurement API increment (local): offers/invoices/deliveries/warehouse records added, stable source IDs and original numbers retained; paginated parameterized search, multiple attachment references deduplicated, unresolved/malformed references explicitly flagged. Seven API tests passed and SQL rehearsal against production was read-only with synthetic actors. Project-scoped files are conservatively withheld (two observed), pending project-aware access checks. Cross-record relationship expansion and UI remain pending; no deployment.

2026-09-28 D2 local increment: project file access uses the existing project resolver/authorization, same full-view role configuration as file contents. Nine API tests passed; read-only SQL rehearsal now yields five available attachments for company 1. New Settings Archive tab with selected-company search, sections, pagination and attachments. Six UI tests passed, including late-response and foreign-company rejection. Not deployed; browser check and remaining customer/source navigation work pending.

2026-09-28 D2 customer increment: exact company/project ownership required for customer project records; file project must match document project. Company leadership archive keeps original signature status; customer cabinet publication unchanged. 16 server tests, 3 archive UI tests passed; actual component browser fixture passed navigation, search, file callback, company switch and mobile width. Read-only SQL: 15 customer records in company 1, none in company 2. Not deployed; real API/browser integration and release gates pending.

2026-09-28: archive read-view deployed at dcadb4d8. Added nginx proxy route company-document-archive after live browser detected SPA fallback; nginx config validated/reloaded, then all browser checks repeated. 16 server / 6 UI tests passed; 251 frontend files match; DB and archive/financial/stock checksums unchanged. Live: own=3, customer=15, supplier pages=30/30, file opens HTTP200, foreign company=403, anonymous=401, mobile390/390. Release receipt saved and backup cleaned only after four verification gates. Follow-up proxy smoke now covers the new route. Reusable contracts, expanded relationship navigation, full actor coverage and cabinet sharing remain pending.

## 2026-09-28 — D3: reuse reviewed original, first slice
- Review context offers latest reviewed contracts for exact owner/buyer/payer/supplier and current INNs, with source offer access checked. Active company-level originals only; no project files or deal-specific payment schedules in this slice.
- Explicit selection populates draft from saved snapshot, retains original file ID, requires fresh review; does not upload or run OCR. Manual draft edits hide the selector to avoid overwrites. Current profile stays visible for comparison.
- Verification: 8 focused Python tests; 13 real isolated PostgreSQL tests including second-offer save with unchanged file count; 18 UI/client tests; production build; local real-browser fixture at 390px without overflow, selection does not confirm/save automatically.
- Remaining D3: canonical contract/version registry and machine-readable reuse lineage, project-scoped eligibility, deal-specific schedule handling. No claim that whole document plan is complete.
- Installed `92de983efaba` on production. Server tests 8/8; 251 frontend files matched; financial/stock/document hashes unchanged. Authenticated browser opened VIST offer #71 review context and form with zero errors/no alerts; no eligible saved contracts currently, so positive reuse remains isolated-test evidence. Closed form without mutation. All four release gates recorded; finalizer removed stage/backup and retained receipt. Health/DB OK after cleanup.

## 2026-09-29 — payment window readability
- Replaced technical contract-binding language with choose/confirm contract, shortened blocked-payment explanation, placed contract before invoice lines, omitted duplicate same-company payer.
- Payment dialog now uses c-* application theme tokens, fixed readable typography, compact cards, clear confirmation action and responsive spacing. Removed redundant choose button after opening a contract; secondary actions follow confirmation.
- 27 existing UI tests passed. Local browser at 390px: no horizontal overflow, same-company payer omitted. No accounting rules or API authorization changed; backend change is error wording only.
- Deployed `0130f76714c4`. Production browser invoice #161: 14px typography, actual dark theme background rgb(30,41,59), short prerequisite message, contract #362 loaded, duplicate payer absent, explicit confirmation still required. No mutation submitted. 251 frontend files matched, table hashes unchanged, health/DB passed. Verified receipt written; release staging/backup removed.

## 2026-09-29 — payment window copy follow-up
- Simplified opening balance, refund, receipt allocation and cancellation explanations; removed UUID/server implementation wording from the main flow.
- Unconfirmed operation keeps readable operation/document/amount summary; raw saved command remains available under technical details. Retry/cancel semantics unchanged.
- 29 relevant UI tests passed; dialog tests repeated after adding the pending-operation summary.
- Installed `1098f2493bbd`. Production payment window confirmed updated copy; local real-browser pending-operation fixture verified collapsed technical details, toggle, readable amount and retry availability. 251 assets and unchanged data hashes verified; health/DB passed. No business mutations submitted. Receipt retained; release backup/staging removed after all four gates.

## 2026-09-29 — explicit reused-contract lineage
- Contract review accepts optional source contract ID. Server resolves source within the owner company, checks source offer access, same original and exact buyer/payer/supplier IDs and INNs; project originals and deal schedules remain excluded.
- Immutable snapshot records source contract ID, offer, version and snapshot hash. Client sends selection and verifies it on response/retry; new upload clears selection. Existing snapshots stay unchanged.
- 13 real isolated PostgreSQL tests passed, including reuse and rejected missing source/wrong original; 18 UI/client tests passed. Full shared-contract registry and expanded archive navigation remain pending.
- Deployed `1aa160bb62d2`. Local browser fixture submitted original file9/source contract3 and verified response. Production VIST review form opened read-only without alerts/JS errors, save remains disabled until review. 251 assets and unchanged data hashes verified, health/DB OK. Four release gates recorded, staging/backup removed, receipt retained.

## 2026-09-29 — reviewed contracts in company archive
- Added reviewed contract versions to supplier archive, with original protected file and originating quotation. No file copies or data migration.
- Invoice rows display quotation and bound contract number/version only through exact same-company, same-offer joins. Unlinked old invoices remain unlinked.
- 12 archive route tests, 4 UI tests passed. Read-only SQL rehearsal with synthetic leadership context found one actual reviewed contract and its quotation; not an authentication proof. Reverse navigation and canonical registry still pending.
- Deployed `7f159bbc729d`. Authenticated production archive search362 shows contract362 version1 and offer71; original file opens HTTP200, zero JS errors. 12 server tests rerun on production, 251 assets and unchanged source/financial/stock hashes verified. Health/DB OK. Backup/staging removed after four release gates; receipt retained. Invoice relation rendering tested synthetically; unbound production invoices are not altered.

## 2026-09-29 — archive relationship navigation
- Added exact source/recordId archive lookup; both parameters required together, source allowlisted, ID bounded. Existing company/role/file authorization remains in every query.
- Invoice can open its verified contract; invoice/contract can open its quotation. Return restores the original section/search/page. Focused response must match requested source and ID; stale responses remain ignored.
- 14 route and 5 UI tests passed. Read-only SQL rehearsal verified exact contract lookup against actual schema (synthetic leadership context, not auth proof).
- Deployed `45fae9209e10`. Authenticated browser search362 -> contract -> quotation71 -> return preserved query362 and original result. No JS errors. Invoice-to-contract covered by UI test. 14 server tests, 251 assets, unchanged data hashes, health/DB passed; all four release gates recorded and backup/staging removed.

## 2026-09-29 — invoices by exact contract version
- Contract archive rows offer “Счета по этой версии”. New bounded contractId filter selects invoice rows using exact contract ID, company and offer, never inferred names or amounts. Conflicting lookup modes rejected.
- Separate pagination and back preserve prior list/contract context. Foreign-version response rejected. Empty state explains missing bindings.
- 16 route tests and7 UI tests passed. Read-only SQL rehearsal: current contract362 has zero bound invoices; no data modified.
- Deployed `91f68d0c0e2f`. Authenticated browser contract362 -> invoices for version -> correct empty state -> back preserved search362. Zero JS errors. 16 server tests, 251 files, unchanged data hashes, health/DB passed. No invoice binding changed. Four verification gates recorded; backup/staging removed.

## 2026-09-29 — original contract navigation
- Reused versions link to the original reviewed version only through validated same-company source ID, offer, version, snapshot hash and original file. No inference or old data rewriting.
- Archive button “Исходный договор” uses exact scoped lookup and preserves list filters on return.
- 18 route tests passed including real isolated PostgreSQL lineage rejection cases; 8 UI tests passed. Local browser fixture verified original version and return.
- Deployed `df168115e06a`. Authenticated production archive contract362 -> quotation71 -> return preserved search362; original HTTP200, zero JS errors. Existing contract has no reuse source; positive lineage remains local PostgreSQL/browser evidence. 17 production tests passed (isolated PG test skipped), 251 assets matched, data hashes unchanged, health/DB OK. Four gates recorded; staging/backup removed and receipt retained.

## 2026-09-29 — archive document category filter
- Added “Вид документа”: supply contracts, quotations, invoices, shipments, warehouse waybills and company/counterparty document records. Server filters before pagination under existing company scope; incompatible filters rejected.
- Related navigation preserves category/search/page; company and section switch clear category. Client rejects unexpected source rows.
- 20 route tests passed including isolated PostgreSQL; 11 UI tests passed.
- Deployed `618493dbc5a8`. Authenticated browser: contract category -> offer71 -> return preserved filter; invoices pages30+19 contain only company1 invoices; section change resets category. Mobile390/page390 visually checked, zero JS errors. 19 production tests passed (isolated PG skipped), 251 assets matched, source/financial/stock hashes unchanged, health/DB OK. Four gates recorded; stage and backup removed, receipt retained.

## 2026-09-29 — D3 explicit term and project scope
- Review records explicit company/project scope and fixed/open-ended dates in immutable snapshot; UI never assumes missing means unlimited. Archive displays reviewed conditions.
- Reuse checks inclusive Moscow dates and exact authorized project, and revalidates unchanged conditions on save. Project originals supported only within the same project; ambiguous legacy names cannot establish scope. Unknown/expired/future contracts excluded from reuse.
- Compatibility: older review commands may omit conditions and remain non-reusable; existing documents/snapshots are unchanged. Canonical pair-level registry, addenda/archive and other issuance-path expiry controls remain pending.
- 52 backend tests passed including 16 contract PostgreSQL and archive PostgreSQL cases; UI/client tests and browser/deployment verification recorded below.
- Deployed `b9764c68a5fb`. Production VIST71 review offers exact Lyceum4 project and explicit term choices, no default selection, no alerts/JS errors. Local browser fixture saved same original with fixed project conditions. 251 assets matched, data hashes unchanged; backend/DB/browser gates passed. Stage/backup removed after receipt.
- Follow-up: current reviewed original can populate a new review draft without upload, including legacy versions with unknown conditions. Current profile requisites remain for comparison; explicit confirmation creates a new snapshot. 17 contract PostgreSQL tests and 21 panel/client tests passed.
- Deployed follow-up `99f2644b1496`. Production VIST71 original362 restored file/number/date without upload; legacy conditions remained empty, fixed term required end date, save disabled. Mobile390 no overflow, screenshot checked; form closed without saving. Zero JS errors, 251 assets matched, business hashes unchanged, backend/DB passed. Four release gates recorded and stage/backup removed. Combined changed suites: 53 backend cases (including local PostgreSQL), 33 UI/client cases. Pair-level registry/addenda are still pending.

## 2026-09-29 — D3 shared contract registry
- Migration0064 adds exact party identity and company-constrained immutable-version membership; no inferred backfill or original copies. New/reused/explicitly revised reviews attach atomically; legacy source joins only after explicit confirmation.
- Latest registry version controls reuse. Stale source rejected; repeated number alone creates no relationship. Existing invoice/version links unchanged. Archive “Все версии договора” groups known members and supports invoice subview/back.
- 55 focused backend cases plus34 recognition/provenance cases passed on isolated PostgreSQL; migration upgrade/downgrade and populated-history guard covered. UI/browser/deployment checks follow.
- Deployed `fdf58db29f77`, Alembic0064. 33 production cases passed (isolated archive PG skipped), 251 assets matched, existing source/financial/stock hashes unchanged; new registry remains empty until explicit user confirmation. Production archive362 and VIST71 retained-original review verified, no save/alerts/JS errors. Local browser fixture: two versions -> invoices -> same history -> archive. 35 UI/client cases passed, including revised-source response mismatch. Four gates recorded; stage/backup removed and receipt retained. Archiving/addenda/publication remain pending.

## 2026-09-29 — D3 contract archive and restore
- Migration0065 adds registry availability and company-scoped decision history. Leadership only, effective company role, optimistic state version and company advisory lock shared with contract review. No deletion or snapshot/payment/stock mutation.
- Archived registries are excluded from reusable originals; stale reuse and revision commands roll back. Current original shows a restore explanation. Restoring preserves original term/project eligibility checks.
- Archive shows status and explicit archive/restore confirmation for registered contracts, across all versions. Unknown command outcome refreshes state and prevents blind retry. Legacy ungrouped contracts remain unchanged until explicit review creates membership.
- 91 focused backend cases passed including isolated PostgreSQL, effective-role/cross-company denial, stale command, restore, migration rollback guards, recognition/provenance regression. 37 UI/client tests passed. Browser/deployment evidence follows.
- Deployed `429b42f3cf26`, Alembic0065. Production 33 tests passed (1 isolated PostgreSQL case skipped); 251 published files matched. Financial/stock/document hashes and original registry columns unchanged; no real archival action submitted. Authenticated browser: contract362 -> invoices/back, VIST71 retained original -> close without save; zero JS errors. Local actual-component browser: both versions archived/restored, 390px no overflow, screenshot checked. All four release gates recorded; stage/backup removed, receipt retained, health/DB OK. Next: addenda and remaining publication/issuance-policy work.

## 2026-09-29 — D3 reviewed additional agreements
- Optional typed addendum creates a new reviewed version with a separate authorized original; main number/date/file stay unchanged. Previous addenda carry forward into explicit revisions and reuse, with active-file/company/project checks and retained originals in the same transaction.
- No schema rewrite or legacy backfill. Existing immutable versions and issued invoice bindings stay unchanged; current conditions require human review. Addenda are not claimed digitally signed or auto-recognized.
- Review has a separate file/number/date section after selecting the saved original. Archive exposes named main/addendum files through its existing file access checks. Client verifies returned addendum identity before releasing pending command.
- 93 focused backend cases passed including isolated PostgreSQL and recognition/provenance. 40 UI/client cases passed. Local actual-component browser submitted main file9 plus addendum10 against source version3, preserving payment terms. Production verification follows.
- Deployed `c0d4c593ef74` and backend-only follow-up `64b1b2933a94` preserving existing payment schedules in addenda chains (94 backend cases total, 40 UI/client cases). Production form VIST71 add/remove section verified, original number/file locked; no upload/save. Archive362 checked again after final restart, zero JS errors. 251 assets matched; financial/stock/document/registry/event hashes unchanged. Mobile390 screenshot checked. Four gates recorded, stage/backup removed, health/DB OK. Addressed cabinet publication and remaining issuance-policy checks are still separate work.

## 2026-09-29 — D4a addressed supplier contract publication
- Migration0066 records explicit publication of an immutable contract version to its existing offer supplier, with actor/time/hash, no inferred backfill. Archive confirmation names recipient and version; repeat is idempotent.
- Supplier contract listing and original/addendum download require publication or exact historical invoice binding, plus current addressed-offer/team assignment policy. Unpublished later versions remain private. Supplier invoice creation checks visibility server-side; known version IDs cannot bypass sharing.
- Latest/private/archived/unavailable versions, company mismatch, recipient self-publication, manager revocation and foreign supplier covered with real isolated PostgreSQL. Earlier invoice-bound versions retain access without silently publishing new ones.
- 75 contract/provenance/binding cases and 22 archive cases passed; 24 targeted UI cases passed. Local actual-component browser confirmed explicit recipient/version and published readback. Release evidence follows. D4 customer publication and a consolidated supplier Documents view remain separate increments.
- Dependency audit run: 39 existing production-tree findings (10 low,10 moderate,19 high,0 critical); package manifests/lock unchanged. Dependency remediation is not claimed complete by this release.
- Deployed `46fb58f9f1dd`/Alembic0066 and backend identity-defense follow-up `ae0539bd39ce`. PostgreSQL FK already prevents supplier reassignment; additional read predicate rejects deliberately corrupted temporary fixture links too. 143 focused local backend cases total and 24 UI cases passed; production 87 passed/1 isolated-only skipped. Buyer archive362 confirmation names ООО ВИСТ; opened/cancelled, no publication. Authenticated archive refreshed after final runtime, zero JS errors, mobile screenshot checked. 251 assets and unchanged business/registry hashes; publications empty. Four gates recorded; backup/staging removed and health/DB OK. Supplier consolidated Documents view and customer addressed publication remain pending, not claimed completed.

### 29.09.2026 — исправление лишних действий с договором

Удалён шаг «Передать поставщику» из архива. Проверенная версия доступна точному
поставщику КП сразу после сохранения; менеджер ограничен действующим назначением.
Текущий проверенный договор счёта выбирается автоматически без галочки.
PG: 30 сценариев; UI: 22. Продакшен-проверка ещё предстоит.
Автоматическое повторное использование между разными КП и вход из карточки
поставщика этим изменением не завершены; не выдавать за готовые.

Выпуск bf4d0ab6 установлен и проверен: 101 локальный backend-тест (включая 30
PostgreSQL), 22 UI; на сервере 70 успешно, 1 тест только для изолированной БД
пропущен. 251 файл сборки совпадает; контрольные суммы рабочих данных неизменны.
В авторизованном браузере оригинал362 доступен, кнопки передачи нет; автоподстановка
проверена реальным React-компонентом в локальном браузере на тестовых данных.
Резерв и staging удалены после всех четырёх проверок.

### Автоподстановка договора при утверждении нового КП

Добавлена в транзакцию утверждения КП: один подходящий договор, совпадающие
известные реквизиты, сохранение оригиналов и допсоглашений, без нового OCR/проверки.
Не затрагивает существующие договоры сделки, счета и отгрузки. Не выбирает
неоднозначный, архивный, просроченный договор или договор с неизвестной областью
действия. Сохраняет первоначального проверяющего и ссылку на исходную версию.
Проверка выпуска предстоит.
