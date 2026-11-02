# QA-only installer: local implementation, runtime acceptance outstanding

This document describes the current code, replacing the earlier e52/bee order.
No server deployment is authorized by this document. Production installer hold
is unchanged. No new database, container, role or permanent credentials.

## Manifest and dry-run

Only these fields are accepted: qa_only=true, database=stroyka_qa,
container=stroyka-qa-db, candidate_root=/opt/stroyka-jev-qa-7e89d73,
frontend_root=/var/lib/docker/volumes/stroyka-qa-frontend-work/_data,
source_sha/target_sha (full exact commits), discard_test_data=true,
maintenance_database=postgres. There is no other_writers_accounted_for flag.
Without --execute, command reads manifest and prints execution=false before
constructing LocalDriver. No Git/Docker/DB/config mutation or access occurs.
The top-level import chain is stdlib plus inert QA runtime/topology definitions.

## Preparation before action-time confirmation

1. Check QA hostname, existing candidate source/cleanliness and Git configuration.
   Reject filters/URL rewrites. Fetch exact target from the official GitHub repo,
   without force, submodules or checkout. A shallow candidate is unshallowed to
   validate the target ancestry to 012c9984. Objects/FETCH_HEAD/shallow metadata
   may change; worktree and branch HEAD must not change. Tooling HEAD must equal
   the target; modified tooling is rejected.
2. Check topology, pinned venv packages, DB target, routing, candidate version
   environment precedence and absence of unresolved dotenv configuration.
   A fixed APP_VERSION/GIT_COMMIT for another version blocks here. No container
   reconfiguration is attempted. Connect to existing postgres and stroyka_qa on
   the same confirmed PostgreSQL identity; SELECT-only preflight checks current
   superuser privileges, open QA gate, subscriptions/prepared transactions and
   schema/extension restrictions. Missing access fails before stopping anything.
3. Build only in a unique /tmp directory inside the existing RUNNING frontend
   container, plus a private /opt host staging directory. The common /app volume
   is not written. No automatic container start. Source archive rejects links,
   traversal and dotenv. Only the reviewed react-scripts build lifecycle and
   official npm registry lock entries are accepted. npm ci uses --ignore-scripts;
   builds needing additional install scripts fail before live changes.
   env -i excludes inherited secrets/proxies/API. Existing boolean REACT_APP flags
   are preserved, other values rejected. API '/api' uses the confirmed gateway prefix on the same
   origin and avoids src/api.js's localhost:8001 fallback. Existing dotenv files
   need explicit config review instead of silently losing their settings.
4. Validate/digest build outputs and repeat preflight before and after fresh
   confirmation. The phrase names the actual pause, DB gate/session termination,
   data replacement, candidate/frontend switch and QA routing changes.
   Preparation itself creates Git objects/temp files and downloads dependencies;
   it is not a zero-write preflight. A cancelled preparation removes only known
   owned temporary resources if their processes completed. An uncertain builder
   timeout retains its staging; no broad deletion. No live rollback is needed.

## Accepted maintenance and publication

Record durable private intent, original container states, target/config hashes and
frontend artifact hashes/paths. Stop the known QA backend/frontend/gateway set.
Use one existing postgres control connection and one stroyka_qa work connection.
Recheck identity/evidence and rights, serialize maintenance, record original gate,
disable new QA connections, wait for other QA client sessions to terminate. Reject
unexpected background workers. Reset public, apply full Alembic and check 0109 in
one READ COMMITTED transaction through that work connection. Target migrations
come from the verified tooling checkout; the live candidate is still unchanged.
Only afterwards switch the candidate to the already fetched target, copy and
verify prepared frontend assets into the existing volume, keep the previous build,
and start/check candidate. Back up and narrowly change existing Caddyfiles, then
validate/open routing. No npm/network build after DB replacement.

Normal rollback/success restores the original open gate. Pre-existing closed QA
is rejected. Uncertain commit/rollback leaves gate closed with recovery_required.
No reset retry. Restore failure propagates. SIGTERM/KeyboardInterrupt have cleanup;
SIGKILL, lost host or connections cannot be repaired by finally. Retain journals
and accepted staging. Recovery requires reconciling cluster/OID/worker/transaction
outcome before separately approving access restoration. No automatic old-backend
restart on unknown schema. No claim of full installation rollback.

## Remaining real acceptance

Mocks do not validate SQL/migration compatibility, PostgreSQL termination races,
actual permissions, restore after crash, npm build, Caddy, health or browser flows.
Another administrator actively reopening the gate is outside the exclusivity
claim. Third-party systemd services/timers are not modified. This is deployment
maintenance code, not permission to resume the previously blocked runtime audit.


## Confirmed dual-route QA topology (local adaptation, not applied)

The identity canary is an intentional separate route:
`handle /api/users/qa-readonly-context/identity` with `uri strip_prefix /api`
and `reverse_proxy stroyka-qa-backend-candidate:8001`. Preserve its entire text,
comments, whitespace and line endings. Never call this endpoint as part of the
installer or its tests.

The general route is `handle_path /api/*` with exactly one literal upstream
`stroyka-qa-backend:8001`. The fallback handle remains
`stroyka-qa-static:3000`. The bounded parser requires this exact topology,
rejects imports/snippets/named matchers, additional routing or multiple upstreams,
and changes only the one general-route upstream to candidate:8001. This is a
real change in API traffic destination, not a formatting correction. Dry-run
reports it and fresh confirmation names it explicitly. Candidate port mapping
must still agree with 8001 internally / 8002 on the host; drift fails closed.

Static root is retained if already /srv/app/build; only the previously allowed
/srv/app -> /srv/app/build change is supported. Header contents are neither
rewritten nor disclosed. The frontend build must use REACT_APP_API_URL=/api so
requests reach the same general API route; the previous '/.' assumption was
incorrect for this now-confirmed QA topology. Other external/unrecognized API
values are rejected before changes. No endpoint permission or role logic changes.
