# Jev GitHub Issue command bridge — QA-only v1

## What is implemented

Create an issue in `marikol444707-ux/stroyka-app`, authored by `marikol444707-ux`:

- Exact title: `[JEV] QA smoke`
- Exact body: `JEV_QA_SMOKE_V1`

After the QA-host timer is installed and enabled, it polls GitHub Issues every five minutes. For each authorized command it calls **only** the existing HMAC-scoped `/watcher/smoke` API on the loopback Jev worker, waits for deterministic QA verification, and posts a sanitized `PASSED`/`FAILED` comment to the issue. It then closes the issue. GitHub never receives screenshots, tokens, raw DOM or browser prompts. An interrupted job is not replayed.

This version supports **one fixed read-only scenario**, not arbitrary prompts, clicks, shell commands, deployments, production URLs or file access. The worker's `/watcher/smoke` target is `/app` and checks `Склад`; its own restrictions still apply. GitHub Issues are not an authentication boundary by themselves: the bridge verifies the exact issue author and command.

## One-time QA-host activation (requires administrator authorization)

The GitHub connector alone **cannot** access the private VPS or enable the systemd timer. A trusted administrator must provision `/etc/stroyka-jev-issue-bridge.env` with `root:stroyka` ownership and mode `0640`:

```
JEV_WATCHER_TOKEN=<64-character HMAC-derived watcher credential>
JEV_CONTROL_GITHUB_TOKEN=<fine-grained GitHub PAT, Issues read/write for this repo only>
JEV_WATCH_PORT=18084
JEV_CONTROL_MIN_ISSUE_NUMBER=<latest issue number before activation>
```

Never put these values in GitHub Issues, terminal history or chat. The watcher token is the **scoped** credential derived as `HMAC_SHA256(DEV_CONTROL_API_TOKEN, "stroyka-jev-watch-read-only-v2")`, **not** the full Jev API token. An existing `/etc/stroyka-jev-watch.env` may already contain this scoped token; verify without displaying it. The GitHub PAT is only required on the QA host.

If the existing watcher already has both scoped `JEV_WATCHER_TOKEN` and `JEV_WATCH_GITHUB_TOKEN` in `/etc/stroyka-jev-watch.env`, the optional `scripts/bootstrap_jev_issue_bridge.sh` can create the bridge environment without exposing tokens. It refuses to proceed if either token is missing. Review and set `JEV_CONTROL_MIN_ISSUE_NUMBER` to the latest issue number before enabling the timer.

From a reviewed checkout:

```bash
sudo bash scripts/install_jev_issue_bridge.sh
sudo systemctl enable --now stroyka-jev-issue-bridge.timer
systemctl status stroyka-jev-issue-bridge.timer --no-pager
```

Before enabling, ensure the actual worker on port `18084` has signed `/watcher/*` endpoints, a valid QA-only identity and no pending jobs. The installer **does not** start the timer automatically. Verify a real issue is processed and receives a result. To stop: `sudo systemctl disable --now stroyka-jev-issue-bridge.timer`.

## Durability and safety

State is stored in `/var/lib/stroyka-jev-issue-bridge/tasks.db` (SQLite, systemd StateDirectory). A durable `claimed` record is written **before** submitting the job. On a crash, the command is reported as interrupted instead of executed twice. If posting the comment fails, reporting is retried without rerunning Jev. If closing the issue fails, only the close is retried.

The bridge needs no Docker socket, root privileges, production credentials or Timeweb keys. Only a scoped watcher token and a narrowly scoped GitHub Issues token are available to the service. GitHub API redirects are rejected. All paths and the single accepted command are hardcoded.

## Verification

```bash
python3 -m unittest scripts.test_jev_issue_bridge -v
```

Offline tests simulate GitHub and the worker and verify allowlisting, redaction, at-most-once execution, interrupted runs and reporting retries. **They do not prove the bridge is installed on the user's VPS.** A real end-to-end run is required before calling the remote integration live.
