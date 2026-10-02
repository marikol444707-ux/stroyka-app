ЗАКРЫТО
- Базовый CI-контур уже есть: backend compile/tests, frontend tests и frontend build входят в обязательную проверку. Evidence: `.github/workflows/ci.yml`, `tasks/plan.md` Task 15.
- Изоляция журнала работ закрывалась отдельными срезами `M6.5a–M6.5d`; в плане записаны production runtime/post-audit evidence для create/read/update/delete. Evidence: `tasks/plan.md`.
- Read-only post-audit по `supplier_invoices` и `supply_deliveries` повторно проверен 02.10.2026: `51/51` текущих строк без review rows. Evidence: `tasks/plan.md`.
- `M6.2d`: переход на защищённую выдачу файлов закрыт. Production-аудиты подтвердили владельца у `268/268` файлов, приватный ACL у `167/167` S3-объектов, отсутствие публичных и незарегистрированных объектов и отключённый публичный `/uploads`; живая загрузка, чтение и удаление прошли. Evidence: `tasks/plan.md`, `tasks/todo.md`.

ОБЯЗАТЕЛЬНО ДО BETA
- `M4.12`: исправление выпущено и включено в runtime `8083f792b325`, schema `0083`. Передача выбирает точную исходную партию, создаёт внутреннюю приходную накладную и новую партию получателя; nginx отдаёт backend JSON. Zero-row production audit, frontend hashes, public browser smoke, full CI и disposable PostgreSQL lifecycle passed. Evidence: `tasks/plan.md`, `tasks/todo.md`.
- `M6.6f1–M6.6f2`: public smoke зафиксирован, но combined protected single/batch/event и negative cross-company smoke остаётся deferred. Evidence: `tasks/plan.md`.

МОЖНО ПОСЛЕ BETA
- `Task 14` (перенос одного low-risk `init_db()` schema slice в Alembic) можно делать после ограниченной Beta, если он не нужен конкретному Beta-fix. Evidence: `tasks/plan.md`.
- `Task A14` прямо предполагает оценку local model только после quality/load/cost measurements; это не prerequisite первой Beta. Evidence: `tasks/plan.md`.

НУЖНО РЕШЕНИЕ ВЛАДЕЛЬЦА
- Отдельного продуктового решения сейчас не требуется: сначала закрываются технические пункты выше. Правило проекта уже требует не закрывать задачу без focused/full tests, manual checks, tenant/role isolation и production smoke. Evidence: финальное правило в `tasks/plan.md`.
