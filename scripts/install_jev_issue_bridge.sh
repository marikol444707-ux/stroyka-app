#!/usr/bin/env bash
# Install only after one-time scoped token and GitHub token provisioning.
set -euo pipefail
[[ "$(id -u)" == 0 ]] || { echo 'STOP: RUN_AS_ROOT'; exit 1; }
id stroyka >/dev/null || { echo 'STOP: USER_MISSING'; exit 1; }
BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV=/etc/stroyka-jev-issue-bridge.env
[[ -f "$ENV" && ! -L "$ENV" ]] || { echo 'STOP: CONFIG_MISSING'; exit 1; }
[[ "$(stat -c '%U:%G:%a' "$ENV")" == 'root:stroyka:640' ]] || { echo 'STOP: CONFIG_PERMISSIONS'; exit 1; }
grep -Eq '^JEV_WATCHER_TOKEN=[0-9a-fA-F]{64}$' "$ENV" || { echo 'STOP: WATCHER_TOKEN_MISSING'; exit 1; }
grep -Eq '^JEV_CONTROL_GITHUB_TOKEN=[A-Za-z0-9_-]{20,255}$' "$ENV" || { echo 'STOP: GITHUB_TOKEN_MISSING'; exit 1; }
grep -Eq '^JEV_WATCH_PORT=18084$' "$ENV" || { echo 'STOP: QA_PORT_NOT_APPROVED'; exit 1; }
python3 -m py_compile "$BASE/scripts/jev_issue_bridge.py" "$BASE/scripts/jev_qa_watch.py"
install -d -o root -g root -m 0755 /usr/local/libexec/stroyka-jev-issue-bridge/scripts
install -o root -g root -m 0644 "$BASE/scripts/jev_issue_bridge.py" /usr/local/libexec/stroyka-jev-issue-bridge/scripts/jev_issue_bridge.py
install -o root -g root -m 0644 "$BASE/scripts/jev_qa_watch.py" /usr/local/libexec/stroyka-jev-issue-bridge/scripts/jev_qa_watch.py
install -o root -g root -m 0644 "$BASE/ops/systemd/stroyka-jev-issue-bridge.service" /etc/systemd/system/stroyka-jev-issue-bridge.service
install -o root -g root -m 0644 "$BASE/ops/systemd/stroyka-jev-issue-bridge.timer" /etc/systemd/system/stroyka-jev-issue-bridge.timer
systemctl daemon-reload
echo 'JEV_BRIDGE_INSTALLED=YES'
echo 'JEV_BRIDGE_TIMER_ENABLED=NO (explicit approval required)'
