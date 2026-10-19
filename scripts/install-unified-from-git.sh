#!/usr/bin/env bash
# Delivery helper for the already reviewed release. No application changes here.
set -Eeuo pipefail
umask 077

APP_ROOT="${STROYKA_APP_ROOT:-/var/www/stroyka-app}"
PYTHON_BIN="${STROYKA_RELEASE_PYTHON:-python3}"
WORK_PARENT="${STROYKA_DELIVERY_WORK_PARENT:-/root}"
TARGET="eb67d1323654a087d52af323e9251a0c3801ab29"
BASE="c30b5c7a6b641bc59860ea5eed6e743f67f1318d"

cd "$APP_ROOT"
BEFORE="$(git rev-parse HEAD)"
git diff --quiet
git diff --cached --quiet
git fetch --no-tags origin codex/unified-production-release
git cat-file -e "$TARGET^{commit}"

DELIVERY_DIR="$(mktemp -d "$WORK_PARENT/stroyka-delivery-XXXXXXXX")"
cleanup_delivery() {
  local delivery_status=$?
  if [[ -e "$DELIVERY_DIR/source/.git" ]]; then
    if ! git -C "$APP_ROOT" worktree remove "$DELIVERY_DIR/source"; then
      echo "Temporary worktree retained for inspection: $DELIVERY_DIR" >&2
      return "$delivery_status"
    fi
  fi
  # Only transfer material lives here. Application/DB rollback backups are kept
  # separately by install.py, including on failure or pending browser acceptance.
  rm -rf -- "$DELIVERY_DIR"
  return "$delivery_status"
}
trap cleanup_delivery EXIT

echo "Preparing pinned release ${TARGET:0:12} from fetched Git objects..."
git worktree add --detach "$DELIVERY_DIR/source" "$TARGET"
"$PYTHON_BIN" "$DELIVERY_DIR/source/scripts/unified_release.py" pack \
  --app-root "$DELIVERY_DIR/source" --base "$BASE" \
  --output "$DELIVERY_DIR/release.tar.gz"
tar --no-same-owner -xzf "$DELIVERY_DIR/release.tar.gz" -C "$DELIVERY_DIR"
"$PYTHON_BIN" "$DELIVERY_DIR/stroyka-unified-${TARGET:0:12}/install.py" apply \
  --app-root "$APP_ROOT" --public-url https://stroyka26.pro --expect-current "$BEFORE"
