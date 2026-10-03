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
patched routing in a minimal Daemon fixture and the actual NetworkBoundary
methods with a fake CDP transport. They cover registered-session duplicates,
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
