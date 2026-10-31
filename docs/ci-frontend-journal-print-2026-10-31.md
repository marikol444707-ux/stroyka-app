# Frontend journal print CI correction — 2026-10-31

Base commit: d81bda6c645297ce1476af101bc9c7e5c8ff8325.
Existing evidence: CI41196763187, job124524384434:
https://github.com/marikol444707-ux/stroyka-app/actions/runs/41196763187/job/124524384434

## Diagnosis

The existing CI frontend result was 313 suites passed / 1 failed; 1955 tests
passed / 1 failed / 0 skipped. Failure: ProjectQualityJournalScope.test.jsx,
"inspection tab and print keep exact project identity". The accessible-name
query /Печать журнала/ did not match "🖨 Печать полного журнала". The cable
variant passed. The repeated failure block in the summary is the same failure,
not a second failed test.

Commit 57fa769e deliberately added the pending inspection filter, retained all
owned journal rows for printing, and clarified the button label. The old shared
test selector had not been updated. Source inspection confirms printing still
passes allRows selected by exact project/company identity, not the visible
pending subset. This is a test-selector incompatibility, not evidence that
printing or ownership filtering failed.

## Correction

Only the test and this report change. Each tab uses its exact accessible print
label; the original owned-row/project argument assertions remain. An additional
component regression verifies that pending mode hides the closed own row on
screen but includes it in full-journal preview, while excluding a foreign
company row and another project with the same name. The preview callback is
also checked. No product code or expectations permitting foreign rows changed;
no tests disabled.

## Local commands

    CI=true npm test -- --watchAll=false --runInBand --runTestsByPath src/features/projects/ProjectQualityJournalScope.test.jsx
    CI=true npm test -- --watchAll=false --runInBand
    BUILD_PATH=/tmp/stroyka-print-ci-build-20261031 npm run build
    git diff --check

Targeted result: 1 suite, 4 passed / 0 failed / 0 skipped.
Build: exit 0, Compiled successfully. Non-fatal notices: Node fs.F_OK deprecation
and old caniuse-lite Browserslist data. Dependencies were not changed to silence
these notices.

Full result: 314 suites passed / 0 failed / 0 skipped; 1957 tests passed /
0 failed / 0 skipped, 101.7 seconds, exit 0. Targeted and full runs overlap
and are not added together as additional coverage. git diff --check passed.

## Scope and cleanup

Only ordinary local frontend Jest/component checks and build were executed.
No PostgreSQL, application server/HTTP, real multi-role browser acceptance,
security/full-remainder suite, manual CI rerun, push, merge, deployment or
production operation. Existing CI server successes were read, not reproduced.
Current CI backend historical count is 6186 counted: 3857 passed, 2329 skipped.

The generated /tmp/stroyka-print-ci-build-20261031 directory was removed after
the successful build; the pre-existing repository build directory was untouched.
No databases, containers or checkouts were created. Logs and cleanup receipt
remain in /workspace/stroyka-fixes-2026-10-31 (frontend-print-*.log and
FRONTEND_PRINT_CLEANUP.json). Real browser printing, cross-role functional
acceptance and a future CI run on this local commit remain unverified.
