# Splitting `backend/main.py`

`backend/main.py` is the FastAPI application entry point (`uvicorn backend.main:app`). On the commit this plan was measured from it was **28,176 lines** and still defined **116 HTTP handlers** inline. Many domains already live in `backend/features/<name>/` and are attached with `register_*_module(app, deps)`. Some of those modules build an `APIRouter` and call `app.include_router`. New slices should follow that shape: the handler moves verbatim, `main.py` only imports and registers it, and shared helpers stay injectable through the `deps` dict.

Line ranges below are the pre-move map. Each later pull request shifts the lines under the code it deletes. Sizes are the handler bodies, not the blank lines and already-extracted registrations that sit between them.

This pull request is step 1. It moves `GET /companies` and `GET /material-price-history`.

## What must not change

Paths, methods, dependency callables, role sets, status codes, response fields and company scoping stay as they are. A moved handler must not import `backend.main` (that import cycle is how a split breaks startup). Helpers that other handlers still call stay in `main.py` and are passed in `deps`. Move a helper to something like `backend/core` only when the new module needs to import it, and re-export it from `main.py` so existing imports and tests keep working.

`scripts/check-m6-tenant-registry.py` searches `backend/main.py` and `backend/features/*/*.py` for every `routePrefixes` string. A prefix moved into a nested file such as `features/<name>/extra/routes.py` disappears from that check. Keep the path string in `routes.py` at the package root.

## Blockers

**Circular imports.** `main.py` imports feature modules while the process is starting. A feature module that imports `backend.main` does not finish loading. Pass `get_db`, `require_roles`, `get_current_user` and domain helpers in through `deps`.

**Module-level globals.** Role tuples (`LEADERSHIP_ROLES`, `WAREHOUSE_ROLES`, `SUPPLY_ROLES`, and the rest around lines 764–798), SQL fragments (`SUPPLY_SELECT`, `DELIVERY_SELECT`, `PROJECT_PUBLIC_SELECT`) and upload settings are defined while `main.py` loads. Handlers close over them today. A moved handler receives the same objects via `deps`.

**Startup DDL in `main.py`.** `init_db()` (lines 3377–5981) runs at import, immediately followed by `ensure_agent_jobs_schema(get_db)`. It contains **111** `CREATE TABLE` statements plus column backfills and seed rows. Importing the app always opens a database connection. The route-inventory test stubs `psycopg2.connect` for that import and restores it afterwards. Moving `init_db` is its own late change: the SQL text stays byte-for-byte the same, and the call remains at import time until a later, separate decision.

**Flag-gated routes.** Several routers are registered only when an environment flag is true (`WAREHOUSE_ANOMALY_PREVIEW_HTTP_ENABLED`, `ASSIGNMENT_DAILY_DRAFT_HTTP_ENABLED`, `ACCOUNTING_EXCEPTION_CHECKS_HTTP_ENABLED`, `HUMAN_APPROVED_ACTIONS_HTTP_ENABLED`, `SUPPLY_TECHNICAL_COMPARISON_HTTP_ENABLED`, `SUPPLIER_MATERIAL_CAPABILITY_RUNTIME_ENABLED`, and the supplier-deal flags around lines 26094 and 27870). The default process does not register them. The inventory covers the default set. `backend/features/route_access/test_inventory.py` also checks that each flag and its `register_*` call remain in `main.py`.

**`warehouse_recommendation_preview` SHA256 pins.** Three tests pin the SHA256 of the whole of `backend/main.py`:

- `backend/features/warehouse_recommendation_preview/test_runtime_routes.py`
- `backend/features/warehouse_recommendation_preview/test_runtime_contract.py`
- `backend/features/warehouse_recommendation_preview/test_runtime_preview.py`

Every split changes that hash even when the warehouse preview registration block is untouched. The pin was there to freeze the registration site. A better check is structural and would survive unrelated moves:

- `main.py` still calls `register_warehouse_anomaly_preview_routes` only inside `WAREHOUSE_ANOMALY_PREVIEW_HTTP_ENABLED == "true"`, and only after the company-id allowlist parses.
- The hashes of `runtime_routes.py`, `runtime_preview.py`, `runtime_contract.py` and the package `__init__.py` stay pinned, because those files are the preview implementation.

This pull request updates the three hashes and leaves the pin mechanism in place. Replacing it changes the review contract for that package, so it belongs in a pull request that touches the preview tests on purpose.

**Route order.** FastAPI keeps the first registered route for a path. Re-register a moved group at the same point in `main.py` where the handlers used to be defined.

## Guard

`docs/route-access-inventory.json` is the default route set: path, methods, dependency callable name, parameter name and role set (taken from the `require_roles` closure). `backend/features/route_access/test_inventory.py` imports the app with a fake database connection, forces the registration flags off, and compares `app.routes` to that file. A later split that drops a route, changes a method or changes a role set fails the test. Adding a route means updating the inventory in the same pull request.

## Inline handlers still in `main.py`

Shared names below are module-level helpers or constants the handlers use that other handlers or non-route functions also use. `get_db`, `require_roles` and `get_current_user` are omitted; almost every group needs them.

| Domain | Lines | Routes | Handler lines | Shared helpers beyond auth/db | Proposed module |
| --- | ---: | ---: | ---: | --- | --- |
| health | 3059–3078 | 1 | 20 | `_app_version`, `_utc_now_iso` | `features/health` |
| director-agent | 3130–3225 | 2 | 94 | `_resolve_work_company_context`, `log_audit`; exclusive Yandex helpers sit just above the routes | `features/director_agent` (package already has read tools) |
| login + 2FA | 6264–6392 | 3 | 125 | `public_user`, `log_audit`, `enrich_worker_project_links`; models `LoginModel`, `TwoFactor*` | `features/auth_session` (package exists) |
| csrf-token | 6395–6415 | 1 | 21 | `_current_user_from_session_cookie` | `features/auth_session` |
| logout | 6418–6438 | 1 | 21 | `require_csrf_for_cookie_mutation`, `log_audit` | `features/auth_session` |
| password reset request/confirm | 6609–6676 | 2 | 66 | token helpers are exclusive; `log_audit` is shared | `features/auth_session` |
| register | 6679–6814 | 1 | 136 | supplier match/alias helpers, `public_user`, `PLATFORM_STAFF_ROLES` | `features/auth_session` or `features/invite_codes` |
| warehouse-main | 6906–7033 | 4 | 122 | company-context resolver, warehouse role tuples, `can_see_warehouse_data`, `_norm_base_unit` | `features/warehouse_main` |
| warehouse-movements | 7036–7391 | 2 | 127 | movement applier, package access, project/warehouse access; span includes helpers between the two routes | `features/warehouse_movements` |
| warehouse-history | 7394–7532 | 3 | 135 | same warehouse access helpers | `features/warehouse_history` |
| pricelists CRUD + items + from-estimate | 7644–7745 and 26517–26624 | 7 | 192 | `PRICELIST_MANAGE_ROLES`; from-estimate also uses estimate helpers. The path group is not one contiguous block | `features/pricelists` |
| companies | 7786–7794 | 1 | 9 | none | **moved in this PR** to `features/companies` |
| supply-requests | 9233–10720 | 10 | 1365 | about 40 shared helpers (estimate control, company context, supplier notify, project company). Nine helpers are exclusive to the group | `features/supply_requests` in two or three slices |
| supply-deliveries | 12170–12590 | 3 | 148 | `DELIVERY_SELECT`, warehouse roles, package access; receive is a thin wrapper | `features/supply_deliveries` |
| work-journal | 12638–14719 | 5 | 623 | about 35 shared helpers; span is 2,082 because journal helpers sit between the routes | `features/work_journal` |
| estimates, including hidden-work detect and AI distribute | 14735–14851 and 16985–19083 and 19591–19667 | 9 | 818 | estimate access, package access, audit, company context | `features/estimates` in read and write slices |
| room-works | 15059–15156 | 3 | 94 | work-journal access helpers; `RoomWorkModel` and `_room_work_scope` are exclusive | `features/room_works` |
| upload-photo | 16303–16421 | 1 | 119 | `save_upload_file`, company context, brigade view roles | `features/uploads` |
| supplier offer file upload | 16425–16431 | 1 | 7 | calls `upload_photo` | move with `upload-photo` |
| ai-chat | 16438–16562 | 1 | 125 | company context, warehouse/finance roles, `visible_project_names` | `features/ai_chat` |
| estimates-summary | 17112–17122 | 1 | 11 | calls `get_estimates` | move with estimate reads |
| brigade-contracts | 19095–19584 | 5 | 410 | contract scope helpers, package access, project access | `features/brigade_contracts` |
| material-transfers | 19717–20278 | 5 | 554 | stock and package helpers, company context | `features/material_transfers` |
| material-price-history | 20298–20330 | 1 | 33 | `MATERIAL_PRICE_HISTORY_ROLES` only | **moved in this PR** to `features/material_price_history` |
| warehouse-invoices | 20488–22589 | 4 | 661 | invoice accounting helpers, company context, package access. Span includes the supplier-document routes | `features/warehouse_invoices` |
| supplier-document backfill and dedupe | 21527–21940 | 2 | 412 | finance roles, invoice link columns, company context | `features/supplier_documents` (package exists; these two handlers stayed behind) |
| workflow invoice preview | 22331–22434 | 1 | 104 | `require_workflow_token` is exclusive; totals/unit helpers are shared | `features/workflow_invoice` |
| material-norms | 22737–22915 | 8 | 165 | project access, `visible_project_names`, role tuples; four row-mapping helpers are exclusive | `features/material_norms` |
| material-norm-suggestions | 23850–24525 | 7 | 543 | norm generation helpers are mostly exclusive; supply estimate control and project access are shared | `features/material_norm_suggestions` |
| material-inspection | 24568–24581 | 3 | 8 | quality-journal reader/writer | `features/quality_journal` |
| cable-journal | 24585–24598 | 3 | 8 | same quality-journal helpers | `features/quality_journal` |
| tb-journal AI generate | 24623–24655 | 1 | 33 | `project_record_scope`, `PROJECT_DOCUMENT_ROLES` | `features/tb_journal` |
| supplier-invoices | 24718–25572 | 4 | 849 | supplier match, company context, invoice link columns, project access | `features/supplier_invoices` |
| vk-connect, vk-notify | 25904–25924 | 2 | 19 | `send_vk_notification` is exclusive to notify | `features/vk_notifications` |
| ai-generate-estimate | 26333–26523 | 1 | 191 | company context, package access, project access | `features/estimate_generation` |
| ai-generate-pricelist | 26627–26722 | 1 | 96 | `PRICELIST_MANAGE_ROLES` | `features/pricelists` |
| hidden-works-acts | 26725–27062 | 5 | 329 | journal roles, package filter, project record scope, audit | `features/hidden_works` (detection package exists) |
| scan-invoice | 27537–27648 | 1 | 112 | five scan helpers are exclusive; company context and the scan prompt helpers are shared | `features/invoice_scan` |

The hottest shared helpers, used across many of the groups above, should stay in `main.py` until a `backend/core` extraction has its own pull request: `_resolve_work_company_context`, `_positive_int_or_none`, `_row_get`, `_float_or_zero`, `_norm_base_unit`, `has_package_access`, `require_project_access`, `require_project_or_warehouse_access`, `log_audit`, `visible_project_names`.

## Order of pull requests

Each step stays under roughly 2–3k lines moved and registers at the old location. Lowest risk means read-only, few shared helpers, and no document or stock writes.

1. **This PR.** `GET /companies` and `GET /material-price-history`. Read-only. Companies depends only on `get_db` and `get_current_user`. Price history depends on `get_db` and `require_roles(*MATERIAL_PRICE_HISTORY_ROLES)`.
2. `GET /health`, then `GET /csrf-token`. Both are small. Health is the public probe, so it gets a pull request by itself.
3. `POST /vk-connect` and `POST /vk-notify`, with `send_vk_notification`. One write of `users.vk_id`, no stock or money.
4. Director-agent tools and ask, plus `_director_agent_extract_json` and `_director_agent_call_yandex`. Pass company context and `log_audit` through `deps`.
5. Pricelist list/create/update/delete/copy and `GET /pricelists/{id}/items`. Leave `POST /pricelists/from-estimate` until estimates move; it calls estimate helpers.
6. Material-norm CRUD (eight routes) with `MaterialNormModel`, `MaterialNormOverrideModel` and the four exclusive row helpers.
7. Material-inspection and cable-journal. The handlers are thin wrappers around the quality-journal helpers, which stay in `main.py` for this step.
8. `POST /tb-journal/ai-generate`.
9. `POST /upload-photo` and `POST /supplier-offers/{offer_id}/files`.
10. `POST /workflow/invoice/preview`.
11. `POST /scan-invoice` with its exclusive scan helpers.
12. Room-works. Small body, but it calls work-journal access helpers through `deps`.
13. Logout, password-reset request, password reset, then register. Login and the two 2FA routes last inside auth, because they issue sessions.
14. Warehouse-main, then warehouse-history, then warehouse-movements. Movements pull in `_apply_warehouse_movement`, which other code still calls, so that helper stays and is passed in.
15. Hidden-works acts.
16. Brigade contracts.
17. Supplier-document backfill and dedupe.
18. Supply deliveries.
19. `POST /ai-chat`, `POST /ai-generate-pricelist`, `POST /ai-generate-estimate`.
20. Material-norm suggestions (handler body about 540 lines; exclusive generation helpers included, still under the cap).
21. Material transfers.
22. Work-journal routes only. Helpers that sit between the routes and are used by estimates or room-works stay in `main.py`.
23. Warehouse invoices split into list/create/delete and the accounting update.
24. Supplier invoices. About 850 lines of handlers; stop before pulling shared supplier-match helpers out of `main.py`.
25. Estimate reads (`GET /estimates`, summary, detail), then writes and status/template/delete, then the two AI estimate routes.
26. Supply requests in three slices: reads (list, recipients, suggest, compare), stock-check, then create/update/delete and the KP send/retry routes. Exclusive recipient helpers move with the write slice.
27. `init_db` and the import-time `ensure_agent_jobs_schema(get_db)` call, into a startup module that `main.py` still invokes at import. SQL text unchanged. This is last because a mistake here runs on every process start.
28. After the handlers are gone, move the remaining shared helpers into `backend/core` (or the feature that owns them) and re-export them from `main.py`.

Already-extracted packages (prescriptions, pd-consents, pricelist items, projects, rooms, staff, crm, inventory, and the rest of the `register_*_module` calls) stay where they are. This plan covers the handlers that are still defined in `main.py`.
