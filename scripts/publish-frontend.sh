#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="${1:-}"
TARGET_DIR="${2:-}"
RSYNC_BIN="${RSYNC_BIN:-rsync}"

fail() {
  echo "Frontend publish failed: $*" >&2
  exit 1
}

[[ -n "$SOURCE_DIR" ]] || fail "source directory is required"
[[ -n "$TARGET_DIR" ]] || fail "target directory is required"
[[ -d "$SOURCE_DIR" ]] || fail "source directory does not exist: $SOURCE_DIR"
[[ -f "$SOURCE_DIR/index.html" ]] || fail "source index.html is missing"
[[ -f "$SOURCE_DIR/asset-manifest.json" ]] || fail "source asset-manifest.json is missing"
[[ -d "$SOURCE_DIR/static" ]] || fail "source static directory is missing"
command -v "$RSYNC_BIN" >/dev/null 2>&1 || fail "rsync is not available: $RSYNC_BIN"

SOURCE_DIR="$(cd "$SOURCE_DIR" && pwd -P)"
mkdir -p "$TARGET_DIR"
TARGET_DIR="$(cd "$TARGET_DIR" && pwd -P)"
[[ "$SOURCE_DIR" != "$TARGET_DIR" ]] || fail "source and target directories must differ"
[[ "$TARGET_DIR" != "/" ]] || fail "refusing to publish into the filesystem root"
if [[ ! -f "$TARGET_DIR/index.html" ]]; then
  shopt -s nullglob dotglob
  TARGET_ENTRIES=("$TARGET_DIR"/*)
  shopt -u nullglob dotglob
  ((${#TARGET_ENTRIES[@]} == 0)) || fail "nonempty target is not a frontend build: $TARGET_DIR"
fi
chmod 0755 "$TARGET_DIR"

# Keep older hashes so tabs opened before the deploy can finish loading.
mkdir -p "$TARGET_DIR/static"
"$RSYNC_BIN" -a --no-perms --no-owner --no-group \
  "$SOURCE_DIR/static/" "$TARGET_DIR/static/"

# Publish manifests and public files only after every referenced asset exists.
"$RSYNC_BIN" -a --no-perms --no-owner --no-group --delete-after \
  --exclude='/index.html' \
  --exclude='/static/' \
  "$SOURCE_DIR/" "$TARGET_DIR/"

INDEX_TEMP="$(mktemp "$TARGET_DIR/.index.html.XXXXXX")"
cleanup_index_temp() {
  rm -f -- "$INDEX_TEMP"
}
trap cleanup_index_temp EXIT

install -m 0644 "$SOURCE_DIR/index.html" "$INDEX_TEMP"
mv -f -- "$INDEX_TEMP" "$TARGET_DIR/index.html"
trap - EXIT

echo "Frontend published atomically: $TARGET_DIR"
