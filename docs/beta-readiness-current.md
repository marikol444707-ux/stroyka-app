ЗАКРЫТО
- Базовый CI-контур уже есть: backend compile/tests, frontend tests и frontend build входят в обязательную проверку. Evidence: `.github/workflows/ci.yml`, `tasks/plan.md` Task 15.
- Изоляция журнала работ закрывалась отдельными срезами `M6.5a–M6.5d`; в плане записаны production runtime/post-audit evidence для create/read/update/delete. Evidence: `tasks/plan.md`.
- Read-only post-audit по `supplier_invoices` и `supply_deliveries` в `M7j` проверил `53/53` строк без review rows. Evidence: `tasks/plan.md`.

ОБЯЗАТЕЛЬНО ДО BETA
- `M4.2–M4.9`: warehouse company isolation в текущем плане всё ещё помечена `implemented locally; release pending`. До release/verification эти пункты нельзя считать закрытыми. Evidence: `tasks/plan.md`.
- `M6.6f1–M6.6f2`: public smoke зафиксирован, но combined protected single/batch/event и negative cross-company smoke остаётся deferred. Evidence: `tasks/plan.md`.
- `M6.2d`: parent protected-file migration остаётся открытым до полного usage audit и безопасного private-storage cutover для новых S3 objects. Evidence: `tasks/plan.md`.

МОЖНО ПОСЛЕ BETA
- `Task 14` (перенос одного low-risk `init_db()` schema slice в Alembic) можно делать после ограниченной Beta, если он не нужен конкретному Beta-fix. Evidence: `tasks/plan.md`.
- `Task A14` прямо предполагает оценку local model только после quality/load/cost measurements; это не prerequisite первой Beta. Evidence: `tasks/plan.md`.

НУЖНО РЕШЕНИЕ ВЛАДЕЛЬЦА
- Отдельного продуктового решения сейчас не требуется: сначала закрываются технические пункты выше. Правило проекта уже требует не закрывать задачу без focused/full tests, manual checks, tenant/role isolation и production smoke. Evidence: финальное правило в `tasks/plan.md`.
