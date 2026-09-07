# Supply comparison: company 1 activation

## Scope

This runbook enables the existing A8.5.3/A8.5.4 comparison on production commit
`20cf455afd2690d99b560cf02257faf0a82744fc`. It does not update the application
checkout, run migrations, change stored requests, select suppliers or call a
model. It rebuilds and publishes the interface, adds Nginx protection, and
restarts `stroyka` with the company-1 backend flags.

Production evidence provided on 2026-09-06 confirmed both services active and
the HTTPS site's warehouse-preview include preceding the broad API regex.
The dedicated comparison include must precede that broad regex: Nginx uses the
first matching regular-expression location. See the
[official location documentation](https://nginx.org/en/docs/http/ngx_http_core_module.html#location).

## Run

Use `scripts/enable_supply_comparison.py` from the reviewed ops commit without
pulling that commit into the application checkout. Save the script to a private
file under `/root`, then run it as root:

```text
python3 /root/<saved-script>.py          # configuration preflight only
python3 /root/<saved-script>.py --apply  # build, back up, enable, verify
```

Use a separate `bash` block when invoking it from the server console; do not set
`set -e` on the interactive login shell. The script takes the existing deploy
lock. Preflight changes no application/configuration data; opening the lock file
may create it. It rejects changed HEAD, tracked checkout changes, unexpected
Nginx layout and existing canary files. Do not bypass a rejection.

The five configured files are:

- The resolved target of `/etc/nginx/sites-enabled/stroyka` (one include added).
- `/etc/nginx/conf.d/supply-technical-comparison-rate-limits.conf`.
- `/etc/nginx/snippets/supply-technical-comparison.conf`.
- `/etc/systemd/system/stroyka.service.d/96-supply-technical-comparison.conf`.
- `/var/www/stroyka-app/.env.production.local` (only the two supply build flags).

Frontend and backend company allowlists are both exactly `1`. Persisting the
frontend settings in the gitignored CRA production-local environment keeps the
button enabled on later ordinary builds. Existing A10 build settings are
resolved with the deployment's existing helper and retained.

Before live changes, the script saves original configurations, metadata and the
old frontend under `/root/stroyka-supply-comparison-*`, then builds into a separate
directory. It validates Nginx before reload, verifies process flags and health
after restart, checks the exact unauthenticated API boundary locally and
publicly, and only then publishes with the existing atomic frontend publisher.
Smoke checks validate assets, and the public manifest must equal the new build's
manifest. The checkout remains on `20cf455a`; a health version change is an error.

The successful marker is `SUPPLY_COMPARISON_COMPANY_1_ENABLED EVIDENCE=...`.
Temporary build and evidence paths are retained for troubleshooting. Backups may
contain environment values: do not paste their contents into chats or public logs.

## Verification still required after activation

The automated `401` check proves only that the intended route is reached and
rejects anonymous access. It is not a successful authenticated comparison.

In company 1, as director, deputy director or supply employee, open an existing
request's offer with a protected PDF and click **Проверить характеристики**.
The request must have one unambiguous project in this company, and the offer
must use `/tenant-files/{fileId}/content`. Other companies and unsupported
sources must not get the button. Check the displayed comparison against the
document. No supplier selection, payment or automatic approval should occur.

## Failure and rollback

A caught error after configuration changes restores the original configuration;
after publication it also restores the old frontend. Newly created configuration
files are moved into the evidence directory, not deleted. Build failures occur
before live changes. SIGKILL, machine failure or a failed rollback require manual
recovery; `SUPPLY_ROLLBACK_INCOMPLETE` is not a success marker.

While the checkout is still the pinned deployment, manual rollback is:

```text
python3 /root/<saved-script>.py --rollback /root/stroyka-supply-comparison-<suffix>
```

Use the exact script and evidence paths printed during activation. Do not use
this rollback after subsequent configuration edits or a different deployment
without reviewing the snapshot against current configuration. Financial and
business records are untouched; no database restore is part of this operation.

## Local verification

- Configuration planner: include ordering, drift rejection, exact company-1
  flags and preservation of unrelated build settings.
- Temporary-files lifecycle tests: preflight, success, manual rollback, build,
  Nginx, API, smoke and stale-public-manifest failure recovery.
- HTTP probe tests: exact `401`, required company headers, no anonymous success,
  no acceptance of a different route's error or an old frontend manifest.
- Existing deployment and atomic publisher regressions, comparison UI tests,
  and a production frontend build with both comparison flags enabled.

External services are faked in the lifecycle tests; they do not substitute for
the server checks and the authenticated real-document verification above.
