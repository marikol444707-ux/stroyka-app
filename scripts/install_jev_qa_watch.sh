#!/usr/bin/env bash
# One-time QA-only install; does not touch production or replace Docker images.
set -euo pipefail

if [[ "$(id -u)" != "0" ]]; then
  echo "Run with sudo/root from a reviewed checkout." >&2
  exit 1
fi
if ! id stroyka >/dev/null 2>&1; then
  echo "Missing unprivileged user: stroyka" >&2
  exit 1
fi
if [[ ! -f /etc/stroyka-jev-qa.env ]]; then
  echo "Missing /etc/stroyka-jev-qa.env" >&2
  exit 1
fi
TOKEN_LINE="$(grep -m1 -E '^DEV_CONTROL_API_TOKEN=[0-9a-fA-F]{64}$' /etc/stroyka-jev-qa.env || true)"
if [[ -z "$TOKEN_LINE" ]]; then
  echo "QA worker token is missing or not the expected 64-char hex value." >&2
  exit 1
fi

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
install -d -m 0755 -o root -g root /usr/local/libexec/stroyka-jev-watch
install -m 0644 -o root -g root \
  "$BASE_DIR/scripts/jev_qa_watch.py" \
  /usr/local/libexec/stroyka-jev-watch/runner.py
install -m 0644 -o root -g root \
  "$BASE_DIR/ops/systemd/stroyka-jev-watch.service" \
  /etc/systemd/system/stroyka-jev-watch.service
install -m 0644 -o root -g root \
  "$BASE_DIR/ops/systemd/stroyka-jev-watch.timer" \
  /etc/systemd/system/stroyka-jev-watch.timer

# Copy only the limited worker API token, never TIMEWEB_AI_API_KEY or QA session.
# Preserve an optional previously configured GitHub reporting token.
GITHUB_LINE=""
if [[ -f /etc/stroyka-jev-watch.env ]]; then
  GITHUB_LINE="$(grep -m1 -E '^JEV_WATCH_GITHUB_TOKEN=[a-zA-Z0-9_]+$' /etc/stroyka-jev-watch.env || true)"
fi
umask 077
{
  printf '%s\n' "$TOKEN_LINE"
  printf '%s\n' 'JEV_WATCH_PORT=18088'
  if [[ -n "$GITHUB_LINE" ]]; then
    printf '%s\n' "$GITHUB_LINE"
  fi
} > /etc/stroyka-jev-watch.env
chown root:stroyka /etc/stroyka-jev-watch.env
chmod 0640 /etc/stroyka-jev-watch.env

systemctl daemon-reload
systemctl enable --now stroyka-jev-watch.timer
echo "JEVA QA timer installed (daily at 08:00 server local time +/- 15m)."
echo "No GitHub notification is sent until JEV_WATCH_GITHUB_TOKEN is configured."
echo "Check: systemctl list-timers stroyka-jev-watch.timer"
echo "Manual one-time smoke: systemctl start stroyka-jev-watch.service"
echo "Report: /var/lib/stroyka-jev-watch/last.json"
