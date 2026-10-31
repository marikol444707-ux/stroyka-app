# Локальная интеграция серверной линии и аудита

Ветка: integration/server-audit-20261101. Первый родитель — серверный
57023611c6090c1bdf63a107a28eefadd1afb492, второй — пакет
a398d3874208038dd7dec3b2d9cf56ab66aa9487. Старые ветки сохранены.
Никаких push/PR/merge main/deploy, изменений production или применения миграций.

## Статус: код объединён, выпуск ЗАБЛОКИРОВАН

История серверной БД неизвестна. Исходные миграционные файлы обеих линий
сохранены без изменения содержимого; серверные переименования 0101/0102
сохранены. У аудиторской 0103_room_owner_identity остался отсутствующий parent
0102_platform_company_features. Статически видны две вершины:
0104_jev_search_run_history и 0109_legacy_payment_requests. Это НЕ допустимый
граф для upgrade. Никакого stamp, повторного создания таблиц, переименования
применённых revisions или автоматической привязки legacy-записей не сделано.
Строгий graph test не отключён и не объявлен прошедшим. Ожидание аудиторской
цепочки сохранено как незавершённый контракт; тест с импортом PG fixture не
запускался. AST-диагностика отдельно фиксирует missing parent.

Следующее необходимое действие — получить фактические применённые revisions
и подтверждение, где применялись обе истории, затем отдельно согласовать
совместимый граф. До этого нельзя запускать установщик или миграции данной ветки.

## Разрешение конфликтов и сохранение поведения

Автоматическое объединение дало четыре конфликтных тестовых файла: ожидание
вершины схемы и три main.py hash assertions. Продуктовый код объединился без
текстовых конфликтов. Не использовалась замена целых файлов ours/theirs.

AST сверка подтверждает сохранение всех 6 изменённых серверных определений
main.py и 19 аудиторских; пересекающихся изменённых определений нет. Все 192
непересекающихся немиграционных файла совпадают со своим родителем.
JEV routes полностью совпадает с серверным AST после исключения ровно семи
добавленных conn.autocommit=False: история/поиск и аудиторские транзакционные
границы сохранены вместе. Общий upsert key не продублирован.

Сохранены: typed contractor/staff/contract/manual selection, журнал ручных
бригад и recovery UI; supplier team lifecycle и merge preview; Yandex OCR;
JEV filters/history/proxy; server CI/release tooling; аудиторские owners/guards,
навигация/материальные суммы, FH01–03 и FH04 с R1–R3, legacy payment gates.
Существующий release tooling сохранён, но не адаптирован к неизвестному графу.

Для обновления трёх hashes сначала сравнены AST всех top-level узлов,
содержащих warehouse_anomaly, с обоими родителями: равны. Также db.py,
preview __init__.py и runtime_routes.py побайтно сохранены. Обновлён только
проверенный main.py digest:
d10f49d3e781788394b2dd65bd145ea7e4b1d043259f43f95eef908f9a430d86.
Другие assertions/guards не ослаблялись. Новый source-only test хранит
воспроизводимые проверки сохранения; миграционный граф он не сертифицирует.

## Фактические проверки

- Frontend: CI=true npm test -- --watchAll=false --runInBand — 320 suites,
  2052 passed, 0 failed, 0 skipped.
- Backend: .venv/bin/python -m unittest с модулями
  legacy_supplier_payments.test_command, contractor_identity.test_manual,
  contractor_identity.test_selection, contractor_identity.test_report,
  job_candidates.test_service, job_candidates.test_routes,
  model_gateway.test_yandex_adapter — 84 passed, 0 failed, 0 skipped.
  Это fake cursors/clients и mocks, не SQL/HTTP/AI вызовы.
- python3 -m unittest scripts.test_server_audit_integration_static —
  6 passed, 0 failed, 0 skipped. Проверки исходников через AST/Git.
- CI=true BUILD_PATH=/tmp/stroyka-integration-build-20261101
  GENERATE_SOURCEMAP=false npm run build — success; устаревшая Browserslist
  база/Node deprecation warning, без изменения зависимостей.
- git diff --check — clean.
- Первый backend-запуск системным python3: 57 результатов, 36 pass и 21 error
  из-за отсутствующих psycopg2/openai (включая ошибки загрузки модулей).
  Это не 57 реальных выполненных test cases: import failures заменяют suites.
  После выбора уже существующего .venv весь выбранный набор содержит 84 теста.
  Повторы не суммируются с финальным результатом.
- Migration graph: BLOCKED по статическому missing-parent контролю, не PASS.
- NOT RUN: PostgreSQL/HTTP/browser/mobile/внешние сервисы, полный security-аудит,
  реальная FH04/0109 concurrency/recovery и upgrade/rollback.

## Дубли веток

Read-only git ls-remote вернул 192 ветки и 192 разных HEAD. Точных дублей HEAD
нет. Для 61 вершины локально доступны объекты: 60 входят в серверную историю,
одна — в историю аудита. 131 вершина не загружалась; их патчи не проверены.
git cherry относительно server/audit не нашёл эквивалентных уникальных commits
среди доступных вершин. Это не попарное доказательство уникальности всех веток.

Найдена пара одинаковых конечных деревьев при разных commits:
codex/jev-platform-feature-next и main, tree
b65c80da83fca26d794942a6c5751a603d050718. Их содержимое совпадает,
но история различается; разрешения на удаление нет, ничего не удалено.
Одинаковые тела job_candidates/platform_company_features миграций под разными
revision IDs — отдельное частичное совпадение, не разрешение применять их дважды.

## Оставшиеся ограничения

Это локальная подготовка кода, не готовый выпуск, не полный аудит и не приёмка
изоляции. Для согласования схемы требуется фактическая история БД; проверки
runtime остаются в ранее установленных границах. Не создавать новый стенд
как способ повторить запрещённый запуск. Production не менялся.
Временная frontend-сборка удаляется после сохранения логов. Checkout, ветки,
patch, отчёты и доказательства сохраняются.
