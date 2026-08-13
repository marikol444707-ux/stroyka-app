#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="${1:-}"
TARGET_DIR="${2:-}"
RSYNC_BIN="${RSYNC_BIN:-rsync}"

fail() {
  echo "Frontend publish failed: $*" >&2
  exit 1
}

require_regular_tree() {
  local tree="$1"
  local label="$2"
  local unsupported
  unsupported="$(find "$tree" ! -type d ! -type f -print -quit)" \
    || fail "$label tree could not be inspected"
  [[ -z "$unsupported" ]] \
    || fail "$label tree contains a symlink or unsupported filesystem entry"
}

require_no_symlink_path() {
  local path="$1"
  local label="$2"
  python3 - "$path" "$label" <<'PY' || exit 1
import os
import sys

raw_path, label = sys.argv[1:]
absolute = os.path.abspath(raw_path)
drive, tail = os.path.splitdrive(absolute)
current = drive + os.sep
for component in (part for part in tail.split(os.sep) if part):
    current = os.path.join(current, component)
    if os.path.islink(current):
        print(
            f"Frontend publish failed: {label} path contains a symlink component",
            file=sys.stderr,
        )
        raise SystemExit(1)
PY
}

[[ -n "$SOURCE_DIR" ]] || fail "source directory is required"
[[ -n "$TARGET_DIR" ]] || fail "target directory is required"
command -v python3 >/dev/null 2>&1 || fail "python3 is required to validate publish paths"
require_no_symlink_path "$SOURCE_DIR" "source"
require_no_symlink_path "$TARGET_DIR" "target"
[[ -d "$SOURCE_DIR" ]] || fail "source directory does not exist: $SOURCE_DIR"
require_regular_tree "$SOURCE_DIR" "source"
[[ -f "$SOURCE_DIR/index.html" ]] || fail "source index.html is missing"
[[ -f "$SOURCE_DIR/asset-manifest.json" ]] || fail "source asset-manifest.json is missing"
[[ -d "$SOURCE_DIR/static" ]] || fail "source static directory is missing"
command -v "$RSYNC_BIN" >/dev/null 2>&1 || fail "rsync is not available: $RSYNC_BIN"

SOURCE_DIR="$(cd "$SOURCE_DIR" && pwd -P)"
TARGET_DIR="$(python3 -c 'import os,sys; print(os.path.abspath(sys.argv[1]))' "$TARGET_DIR")" \
  || fail "target directory could not be resolved"
[[ "$SOURCE_DIR" != "$TARGET_DIR" ]] || fail "source and target directories must differ"
[[ "$TARGET_DIR" != "/" ]] || fail "refusing to publish into the filesystem root"
case "$TARGET_DIR/" in
  "$SOURCE_DIR/"*) fail "target directory must not be inside the source directory" ;;
esac
case "$SOURCE_DIR/" in
  "$TARGET_DIR/"*) fail "source directory must not be inside the target directory" ;;
esac
if [[ -e "$TARGET_DIR" ]]; then
  [[ -d "$TARGET_DIR" ]] || fail "target path is not a directory: $TARGET_DIR"
  require_regular_tree "$TARGET_DIR" "target"
else
  mkdir -p "$TARGET_DIR"
fi
if [[ ! -f "$TARGET_DIR/index.html" ]]; then
  shopt -s nullglob dotglob
  TARGET_ENTRIES=("$TARGET_DIR"/*)
  shopt -u nullglob dotglob
  ((${#TARGET_ENTRIES[@]} == 0)) || fail "nonempty target is not a frontend build: $TARGET_DIR"
fi
chmod 0755 "$TARGET_DIR"

# Keep older hashes so tabs opened before the deploy can finish loading.
mkdir -p "$TARGET_DIR/static"
"$RSYNC_BIN" -a --no-owner --no-group \
  --chmod=Du=rwx,Dgo=rx,Fu=rw,Fgo=r \
  "$SOURCE_DIR/static/" "$TARGET_DIR/static/"

# Publish manifests and public files only after every referenced asset exists.
"$RSYNC_BIN" -a --no-owner --no-group \
  --chmod=Du=rwx,Dgo=rx,Fu=rw,Fgo=r --delete-after \
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
