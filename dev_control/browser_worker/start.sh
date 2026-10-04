#!/usr/bin/env bash
set -euo pipefail

readonly expected_cdp_url="http://127.0.0.1:9222"
if [[ -n "${BU_CDP_WS:-}" ]]; then
  echo "Refusing BU_CDP_WS; Jev QA must use dedicated loopback Chrome only" >&2
  exit 2
fi
unset BU_CDP_WS
if [[ -n "${BU_CDP_URL:-}" && "${BU_CDP_URL}" != "${expected_cdp_url}" ]]; then
  echo "Refusing external BU_CDP_URL; Jev QA must use dedicated loopback Chrome only" >&2
  exit 2
fi
export BU_CDP_URL="${expected_cdp_url}"
export BH_HOME="${BH_HOME:-/tmp/browser-harness}"

profile="${CHROME_USER_DATA_DIR:-/tmp/stroyka-dev-chrome}"
mkdir -p "$profile" "$BH_HOME" "${QA_EVIDENCE_DIR:-/tmp/stroyka-qa-evidence}"

chrome_args=(
  --headless=new
  --remote-debugging-address=127.0.0.1
  --remote-debugging-port=9222
  --user-data-dir="$profile"
  --disable-dev-shm-usage
  --no-first-run
  --no-default-browser-check
  about:blank
)

# Chrome sandbox stays enabled by default. Opt-out must be explicit.
if [[ "${CHROME_NO_SANDBOX:-0}" == "1" ]]; then
  chrome_args=(--no-sandbox "${chrome_args[@]}")
fi

google-chrome-stable "${chrome_args[@]}" >/tmp/stroyka-dev-chrome.log 2>&1 &
chrome_pid=$!
trap 'kill "$chrome_pid" 2>/dev/null || true' EXIT

for _ in $(seq 1 60); do
  if python - <<'PY'
import json, urllib.request
try:
    json.load(urllib.request.urlopen("http://127.0.0.1:9222/json/version", timeout=0.5))
except Exception:
    raise SystemExit(1)
PY
  then
    exec uvicorn dev_control.browser_worker.service:app --host 0.0.0.0 --port "${PORT:-8080}" --workers 1
  fi
  sleep 0.25
done

echo "Dedicated QA Chrome did not expose CDP on 127.0.0.1:9222" >&2
tail -n 40 /tmp/stroyka-dev-chrome.log >&2 || true
exit 3
