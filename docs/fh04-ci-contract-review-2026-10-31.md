# FH04 CI contract review

CI 41235043064 / job 124636905442, published SHA
52441e172edbff84728f05c67f83a97d8747a180: failure.
Backend: 6215 total, 3879 passed, 7 failed, 2329 skipped.
Later PostgreSQL, frontend and build steps were skipped; they are not PASS.

Four failures in test_supplier_link_route_contract searched only the old route
body. The owner/role/link-pair/automatic-repair checks now live in the shared
_update_supplier_invoice_in_transaction worker. Audit remains in the wrapper.
Updated static tests inspect the correct worker, and an additional assertion
checks exact cursor/id/payload/header/user forwarding and company/actor/linkChanged
result propagation. No assertions removed and no product guards changed.

Three failures froze SHA256 of all main.py in warehouse recommendation preview
tests. Compared AST of main.py at 01b15db9 with 52441e17: after excluding only
update_supplier_invoice and the two new FH04 functions, all top-level AST nodes
are identical, including preview parser/imports/registration. All other protected
file hashes remain unchanged. Only the reviewed main.py digest was updated:
0aa9ad5b5ecf2cb0757526fca5413ddec4d068b10e1f1ec7ac9d0c8ebe6a69c2.

Executed only the 5 link-contract static tests and the 3 named failing static
hash/import/registration tests: 8 passed, 0 failed, 0 skipped. No HTTP/SQL/DB,
role/security suite, complete CI, migration or frontend run was executed.
No product changes, no push or workflow rerun. git diff --check clean.
Logs: /workspace/stroyka-fixes-2026-10-31/fh04-ci-contract-tests.log and
fh04-ci-hash-tests.log. PostgreSQL/migration/browser acceptance remains open.
