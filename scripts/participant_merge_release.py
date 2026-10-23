"""Read-only frontend release checks for the participant merge installer."""
import hashlib
import json
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit


def asset_path(value):
    if not isinstance(value, str) or not value:
        raise ValueError("Empty/non-string asset path")
    parsed = urlsplit(value)
    if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
        raise ValueError("Assets must be local paths without query/fragment")
    path = unquote(parsed.path)
    if "\\" in path or "%" in path or any(ord(char) < 32 for char in path) or path.startswith("//"):
        raise ValueError("Unsafe asset path")
    rel = Path(path.lstrip("/"))
    if not rel.parts or any(part in (".", "..") for part in path.lstrip("/").split("/")):
        raise ValueError("Unsafe asset path")
    return rel


def regular_asset(root, rel):
    root = Path(root)
    if root.is_symlink():
        raise ValueError("Symlink asset root")
    current = root
    for part in rel.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError("Symlink in asset path")
    if not current.is_file():
        raise ValueError(f"Missing asset: {rel}")
    return current


def manifest_paths(manifest):
    files = manifest.get("files")
    entrypoints = manifest.get("entrypoints")
    if not isinstance(files, dict) or not files or not isinstance(entrypoints, list) or not entrypoints:
        raise ValueError("Incomplete frontend manifest")
    return {asset_path(value) for value in [*files.values(), *entrypoints]}


def verify_assets(root, manifest, fetch, base):
    """Verify every named file, including lazy chunks, before claiming frontend OK."""
    paths = manifest_paths(manifest)
    for rel in sorted(paths):
        local = regular_asset(root, rel)
        remote_path = "/app" if rel.as_posix() == "index.html" else "/" + quote(rel.as_posix(), safe="/")
        if hashlib.sha256(fetch(base + remote_path)).digest() != hashlib.sha256(local.read_bytes()).digest():
            raise ValueError(f"Published asset mismatch: {rel}")
    return len(paths)


def write_pending(backup, head, asset_count):
    # Not a completion/cleanup marker. Browser acceptance is deliberately pending.
    data = {"head": head, "status": "installed_pending_browser_acceptance",
            "checkedAssetCount": asset_count,
            "checks": {"backend": True, "database": True, "frontend": True, "browser": False}}
    (Path(backup) / "installed-pending.json").write_text(json.dumps(data) + "\n")
