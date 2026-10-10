# CDP session compatibility (#275)

This is a narrow follow-up to frozen PR #244, not permission to deploy or to
run authenticated Stroyka QA. PR #244 and the owner's existing image are not
modified by committing this change.

## Two changes

1. The worker Docker build pins `browser-harness==0.1.13` and runs
   `patch_harness.py` against that image's installed `Daemon.handle`.
   Only `Target.setAutoAttach` retains its explicitly supplied session ID.
   Other `Target.*` methods remain browser-level. `Page.*`, `Fetch.*` and
   `Runtime.*` keep their existing routing. Unsupported versions, ambiguous
   source or an unexpected assignment fail the build instead of guessing.
2. `NetworkBoundary` ignores announcements for sessions already in its own
   registered set, before recording a target as a child. This prevents the
   existing root session from being reconfigured/resumed or closed as a child.
   New sessions still go through the original guard before resume. There is
   no global registered-session cache shared between jobs.

No timeout increase, Fetch disable, sandbox disable, new credentials, worker
service/API changes, production changes or migrations are included.
The dependency patch is build-time only; runtime does not rewrite packages.

## Regression tests

From the repository root, without Chrome or API credentials:

```bash
python -m unittest backend.test_dev_control_cdp_sessions -v
```

The existing backend discovery runs this file in full CI. Tests execute the
patched routing in a minimal synthetic Daemon fixture and the actual
NetworkBoundary methods with a fake CDP transport. Hash tests use one fixed
synthetic trust reference scoped to the test; production pins are asserted
separately and cannot be configured through CLI or environment variables.
Tests do not download dependencies. They cover registered-session duplicates,
new page/iframe/worker sessions, guard-before-resume ordering, failed setup,
per-instance registration and allowed/blocked paused requests. These are
behavioral unit tests, not proof of real popup or worker network isolation.

## Evidence and remaining acceptance

Issue #275 records the owner's runtime evidence using temporary versions of
these two changes on `stroyka-jev:5beafb6`:

- Local page opened, programmatic click verified, intentional out-of-origin
  request blocked before reaching a second loopback server.
- One real `jev-latest` decision through Timeweb selected CLICK; the verifier
  confirmed one click, changed marker and the same page.
- Both probes reported `delegated_new_sessions=0`. They do NOT cover newly
  created popup/iframe/worker targets.

The new image still requires a successful build and runtime tests without the
probe's temporary patches, plus full CI and review on the final commit. This
change alone does not complete Agent.run, Work Control integration, authenticated
QA, or the outstanding isolation/credential work in #271. No automatic merge,
production deploy, production migrations or repeat paid smoke-test is authorized.

## Full-file integrity gate (PR #278 review)

The patcher checks raw UTF-8 bytes of the entire installed `daemon.py`, before
examining or replacing the routing assignment. The only accepted SHA256 values
are pinned in source, never read from installed metadata, input files or env:

- Original: `7f05f904e62af8c07153c34a1fd3d334acf5c5aded8d0ddab974596bb50a8c97`
- Exact patched output: `c91b78c5bf6bd8858721bc6f834104666f0191965ae2946b01c832af004aca46`

The original matches both the owner's saved installed-file SHA256 and the
upstream `src/browser_harness/daemon.py` Git blob
`0a376c59cf4e7abc5de1f4559cdf3a530696941c` at commit
`afbcc381b963040c19627d788e40c7e7663171ee` of
https://github.com/browser-use/browser-harness . The bytes retrieved through
the GitHub connector were checked against that Git blob and SHA256 locally.
A PyPI wheel was not downloaded in this verification; this is a match to the
owner's installed file and the upstream Git source, not wheel attestation.

The patched digest was calculated from that verified original using the exact
routing and comment replacement in this PR. Its digest is checked before any
file write. Reapplication accepts only the exact known output, not an arbitrary
file already containing the new route. Line-ending changes, a BOM, truncation,
extra code before/after the route and changes outside `handle` are rejected.
Refusal leaves the file unchanged and must not print the readiness marker.

The full upstream file was also checked locally, without importing or starting
the daemon: the real pinned original transforms into the real pinned output and
reapplication is byte-for-byte stable. Four altered full-file variants accepted
by the old validator are rejected by the new one. This separate source-level
check is not a wheel install, Docker build or live browser test. Ordinary backend
CI uses the synthetic fixture described above and makes no external downloads.
Any dependency update requires explicit review and new pins, not an automatic
hash refresh.

This verifies compatibility of this one file, not integrity of every dependency
or proof of network isolation. Existing runtime/review gates above still apply.
