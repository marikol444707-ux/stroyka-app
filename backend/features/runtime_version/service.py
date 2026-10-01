"""Resolve a Git release SHA without invoking Git or assuming loose refs."""

from pathlib import Path


def _read(path):
    try:
        return path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        return ""


def _git_dir(root):
    marker = Path(root) / ".git"
    if marker.is_dir():
        return marker
    raw = _read(marker)
    if raw.startswith("gitdir:"):
        value = raw.split(":", 1)[1].strip()
        return (marker.parent / value).resolve() if not Path(value).is_absolute() else Path(value)
    return None


def _common_dir(git_dir):
    raw = _read(git_dir / "commondir")
    if not raw:
        return git_dir
    value = Path(raw)
    return value.resolve() if value.is_absolute() else (git_dir / value).resolve()


def _safe_ref(value):
    if not value.startswith("refs/") or "\\" in value:
        return ""
    parts = value.split("/")
    return value if all(part not in ("", ".", "..") for part in parts) else ""


def _packed_ref(path, ref):
    for line in _read(path).splitlines():
        if not line or line[0] in "#^" or " " not in line:
            continue
        sha, name = line.split(" ", 1)
        if name.strip() == ref:
            return sha.strip()
    return ""


def app_version(root, environ):
    configured = str(environ.get("APP_VERSION") or environ.get("GIT_COMMIT") or "").strip()
    if configured:
        return configured[:12]
    git_dir = _git_dir(root)
    if not git_dir:
        return "unknown"
    head = _read(git_dir / "HEAD")
    if not head.startswith("ref:"):
        return head[:12] if head else "unknown"
    ref = _safe_ref(head.split(":", 1)[1].strip())
    if not ref:
        return "unknown"
    common = _common_dir(git_dir)
    for base in dict.fromkeys((git_dir, common)):
        sha = _read(base / ref) or _packed_ref(base / "packed-refs", ref)
        if sha:
            return sha[:12]
    return "unknown"
