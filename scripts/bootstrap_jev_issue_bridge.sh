#!/usr/bin/env bash
# One-time bridge bootstrap from an EXISTING, scoped Jev watcher configuration.
# No Docker/QA mutation. Refuses to run if the existing GitHub token is absent.
set -euo pipefail
[[ "$(id -u)" == 0 ]] || { echo 'STOP: RUN_AS_ROOT'; exit 1; }
SOURCE=/etc/stroyka-jev-watch.env
TARGET=/etc/stroyka-jev-issue-bridge.env
[[ -f "$SOURCE" && ! -L "$SOURCE" ]] || { echo 'STOP: WATCHER_ENV_MISSING'; exit 1; }
[[ ! -e "$TARGET" ]] || { echo 'STOP: BRIDGE_ALREADY_CONFIGURED'; exit 1; }
TOKEN="$(grep -m1 -E '^JEV_WATCHER_TOKEN=[0-9a-fA-F]{64}$' "$SOURCE" || true)"
GITHUB="$(grep -m1 -E '^JEV_WATCH_GITHUB_TOKEN=[A-Za-z0-9_-]{20,255}$' "$SOURCE" || true)"
[[ -n "$TOKEN" ]] || { echo 'STOP: SCOPED_WATCHER_TOKEN_MISSING'; exit 1; }
[[ -n "$GITHUB" ]] || { echo 'STOP: GITHUB_ISSUES_TOKEN_MISSING'; exit 1; }
id stroyka >/dev/null || { echo 'STOP: USER_MISSING'; exit 1; }
# Create-only, private; never print credentials.
umask 077
{
  printf '%s\n' "$TOKEN"
  printf 'JEV_CONTROL_GITHUB_TOKEN=%s\n' "${GITHUB#JEV_WATCH_GITHUB_TOKEN=}"
  printf '%s\n' 'JEV_WATCH_PORT=18084'
  printf '%s\n' 'JEV_CONTROL_MIN_ISSUE_NUMBER=0'
} > "$TARGET"
chown root:stroyka "$TARGET"
chmod 0640 "$TARGET"
unset TOKEN GITHUB
echo 'JEV_BRIDGE_CONFIG_READY=YES'
echo 'WARNING: set MIN_ISSUE_NUMBER to the latest pre-activation issue before enabling'
