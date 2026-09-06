# Supply-chain release: 2026-09-07

## Scope and evidence

Status: prepared for operator execution; production deployment is **not yet confirmed**.

- Live baseline: `20cf455afd2690d99b560cf02257faf0a82744fc`, Alembic `0006_user_company_staff_links`.
- Release: `65ce327917253d3c565d729dc288a0937f16ec29` (merged PR #7).
- [Merged-main CI run 34064031567](https://github.com/marikol444707-ux/stroyka-app/actions/runs/34064031567): completed, successful; exact release SHA, `push` on `main`, `.github/workflows/ci.yml`.
- Operator rehearsal: `/root/stroyka-supply-rehearsal-0W76EnqI`; candidate `4b935a5163ac602eee590adec02defba4222ef27`.
- Rehearsal upgraded an access-restricted database clone to `0007_warehouse_vat_labels`. All 53 warehouse invoice rows and the existing TEXT VAT schema were unchanged; row digest `5a1478de6c19603b3611153e86bc9607e6a9a7e084d2b37ddb130f60f58802c6`.
- Rehearsed candidate and final release differ only in test-fixture naming, related tests and documentation, not runtime, frontend or migrations. The deployment helper additionally checks the migration blob and migration-tree equality itself.

The release fixes supply request presentation/submission and supplier workflow handling. It does not repair, delete or resend historical requests, generate offers, record payments, or send a test purchase to real suppliers.

## One-release helper

`scripts/deploy-supply-chain-release.sh` is deliberately pinned to this host, baseline, target, CI run and rehearsal. It is not a general-purpose deployment entry point. Publish it on the separate `ops/supply-chain-release` branch and execute a reviewed, exact commit's copy; do not merge this helper into the application merely to deploy it.

Before any checkout or service restart it requires:

- root, the existing deployment lock, exact baseline on `main`, and a clean tracked worktree/index;
- fetched `main` at the exact release, successful pinned CI, and matching rehearsal evidence;
- only the reviewed `0007` migration added; unchanged dependency manifests and existing `deploy.sh`;
- healthy application/nginx, the expected live VAT schema and revision;
- the Alembic `DB_*` configuration resolving to the same local `stroyka:5432` database that is backed up, consistent with explicitly configured database values in the running service;
- a fresh private database dump with a checksum and readable archive catalogue, plus old code, frontend and environment backups.

The application database values are saved privately and supplied to the actual migration child. Inherited PostgreSQL redirect variables are removed. Alembic is passed the exact application config via `-c`, and inherited `ALEMBIC_CONFIG` is replaced: otherwise it could select a different migration environment despite the frozen database values. Credentials are never printed. Preserve the root-only backup directory: it contains secrets and business data.

The helper renders the unchanged, existing deployment workflow into the backup directory. It removes its moving `git reset`/`git pull` operations and replaces `alembic upgrade head` with the exact reviewed revision. Each replacement must match exactly once. Build, frontend environment flags, publishing and smoke checks stay in the existing workflow. Production smoke is explicitly business-read-only.

Success requires the exact checkout, `0007`, local and public health at the target version, public frontend manifest equal to the installed build, nginx, and the previously running agent worker. Expect `SUPPLY_CHAIN_DEPLOYED 65ce32791725 BACKUP=...`.

Offline helper verification: 19 safety tests pass, including executing the rendered-script transformation and launch environment logic with local fakes, CI/rehearsal mismatch rejection, and the hostile `ALEMBIC_CONFIG` regression. All six embedded Python blocks parse, and `bash -n` passes. The existing application-only deployment runner's nine fake-host tests and eleven frontend publisher tests also pass. These checks do not execute this new release helper against production; operator output remains required.

## Failure handling

Preflight or backup failure stops without restarting production. After checkout begins, errors or HUP/INT/TERM stop and reap the deployment process group before application rollback, preventing a still-running build from publishing after rollback.

Rollback restores the previous checkout and frontend and restarts services. It leaves a detached checkout and clearly reports its health. Do not immediately rerun ordinary `deploy.sh` after rollback; inspect the reported failure and current revision first.

There is **no automatic database restore or downgrade**: restoring a pre-deploy dump could discard concurrent business writes. On the verified existing TEXT VAT schema, `0007` leaves invoice data/schema intact and only advances the migration revision; the baseline application remains compatible. Backup recovery, if ever required, needs a separate reviewed procedure.

The PostgreSQL warning about `/dev/null` not being a plain password file is from the explicit `PGPASSFILE` setting; successful local socket/peer operations in the rehearsal do not depend on that file. Do not change database authentication in response to this warning alone.

## Remaining verification

After the operator posts deployment output, check service errors and one **authorized real** supply chain: request, approvals, supplier offer request, supplier visibility/notification, offer and receipt. Automated/local workflow tests do not prove delivery to a real supplier's mailbox or MAX account. Do not mass-resend old QA requests to obtain that proof.

## Existing dependency debt

Read-only lockfile audit on 2026-09-07 reports 37 findings: 19 high, 8 moderate, 10 low, zero critical. This is not a clean dependency audit, and no dependency fixes are included here.

All 19 high package names resolve under existing `react-scripts@5.0.1`. No imports were found in application `src`, `public` or backend. Inspection of 63 production JavaScript sourcemaps (586 sources, including 452 local sources matching the current tree) found none of these high packages in the browser bundle. Workbox has no application service-worker entry; the separate `public/sw.js` does not use it. Dependency manifests are unchanged from the live baseline.

Therefore no new supplier/client browser-runtime exposure was identified for this narrow release. Build-tool risk remains: vulnerable tooling is installed and partly runs in the existing root-level server build. Do not treat this as proof of zero risk or run unreviewed source/configuration through that environment.

Follow-up owner: project maintainer; review by **2026-09-14**. Plan compatible toolchain upgrades and move production builds to an isolated, non-root build environment. Re-audit exact advisory/version reachability before accepting any longer deferral; do not apply a blind force-upgrade to Create React App.
