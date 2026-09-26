ЗАКРЫТО
- Верификация отсутствия внешних пробелов в секретах: тест `backend/test_auth_secret_configuration.py::test_short_or_whitespace_wrapped_secret_is_rejected` подтверждает поведение. (см. `backend/test_auth_secret_configuration.py`).

ОБЯЗАТЕЛЬНО ДО BETA
- Исправить случаи неканоничных snapshot-хэшей (пробелы/регистр): тест `backend/features/brigade_lineage/test_readiness_report.py::test_snapshot_hash_must_be_canonical_lowercase_without_whitespace` указывает на риск несовместимости хэшей. (см. `backend/features/brigade_lineage/test_readiness_report.py`).
- Обработать legacy имена проектов с завершающими пробелами: `backend/features/ai_ownership/test_ownership_report.py::test_exact_legacy_project_name_with_trailing_space_is_verified` и `backend/features/ai_ownership/test_ownership_report.py::test_whitespace_only_near_match_does_not_cross_link_projects` демонстрируют случаи, которые должны пройти валидацию. (см. `backend/features/ai_ownership/test_ownership_report.py`).
- Runtime trimming project names в supply workflow: `backend/features/supplier_access/test_supply_request_workflow_smoke.py::test_runtime_project_names_trim_legacy_whitespace` показывает где фронтенд/бэкенд должны согласовать поведение. (см. `backend/features/supplier_access/test_supply_request_workflow_smoke.py`).
- Whitespace-sensitive deparser for material capability schemas: контракт описан в `backend/features/supply_recommendation_preview/material_capability_schema_contract.py` — внешние пробелы должны быть лишь обрезаны, не менять внутреннее представление. (см. `backend/features/supply_recommendation_preview/material_capability_schema_contract.py`).

МОЖНО ПОСЛЕ BETA
- CI/ops скрипты, отвергающие корневые симлинки с завершающим слэшем — тесты в `scripts/test-publish-frontend.py` (`test_rejects_source_root_symlink_with_trailing_slash`, `test_rejects_target_root_symlink_with_trailing_slash`) можно рассмотреть позже. (см. `scripts/test-publish-frontend.py`).
- Документы и канарии по проверкам вводимых значений (leading-zero, whitespace) — примеры в `docs/accounting-exception-checks-canary.md` и `docs/human-approved-actions-canary.md` можно сделать менее приоритетными. (см. `docs/accounting-exception-checks-canary.md`, `docs/human-approved-actions-canary.md`).

НУЖНО РЕШЕНИЕ ВЛАДЕЛЬЦА
- Поведение при встрече legacy строк, принадлежащих разным компаниям: нужно строгое правило владельца по тому, как тримить/сопоставлять имена (risk: кросс-tenant linkage). Evidence: `docs/supply-request-workflow-e2e-smoke-a8-5-2.md` и тесты ownership в `backend/features/ai_ownership`. (см. `docs/supply-request-workflow-e2e-smoke-a8-5-2.md`, `backend/features/ai_ownership/test_ownership_report.py`).
- Приоритет canonicalization vs. user-visible names: нужно решение — автоматически canonicalize (низкий регистр + trim) или показывать оригинал владельцу при расхождении. Evidence: `docs/decisions/0001-brigade-assignment-lineage.md` и `backend/features/brigade_lineage/test_readiness_report.py`. (см. `docs/decisions/0001-brigade-assignment-lineage.md`, `backend/features/brigade_lineage/test_readiness_report.py`).
