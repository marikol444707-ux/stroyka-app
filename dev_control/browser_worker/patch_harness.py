"""Build-time compatibility patch for browser-harness 0.1.13 (issue #275).

Only the isolated worker image is modified. No daemon is started and no runtime
secrets are read. Unexpected versions or routing code fail the image build.
"""
from __future__ import annotations

import ast
import hashlib
from importlib.metadata import distribution
from pathlib import Path

EXPECTED_VERSION = "0.1.13"
# Full-file pins, not values derived from untrusted installed metadata or env.
# Provenance and verification are documented in CDP_COMPATIBILITY.md.
EXPECTED_ORIGINAL_SHA256 = "7f05f904e62af8c07153c34a1fd3d334acf5c5aded8d0ddab974596bb50a8c97"
EXPECTED_PATCHED_SHA256 = "c91b78c5bf6bd8858721bc6f834104666f0191965ae2946b01c832af004aca46"
OLD_ROUTE = 'sid = None if method.startswith("Target.") else (req.get("session_id") or self.session)'
NEW_ROUTE = ('sid = (req.get("session_id") if method == "Target.setAutoAttach" '
             'else None) if method.startswith("Target.") '
             'else (req.get("session_id") or self.session)')


def patched_source(source: str, version: str) -> str:
    if version != EXPECTED_VERSION:
        raise ValueError("Unsupported browser-harness version; review compatibility first")
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
    if digest == EXPECTED_PATCHED_SHA256:
        return source  # Accept only the exact previously verified output.
    if digest != EXPECTED_ORIGINAL_SHA256:
        raise ValueError("Unrecognized daemon.py SHA256; no patch applied")
    tree = ast.parse(source)
    classes = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "Daemon"]
    if len(classes) != 1:
        raise ValueError("Expected exactly one Daemon class")
    handlers = [node for node in classes[0].body
                if isinstance(node, ast.AsyncFunctionDef) and node.name == "handle"]
    if len(handlers) != 1:
        raise ValueError("Expected exactly one async Daemon.handle")
    routes = [node for node in ast.walk(handlers[0])
              if isinstance(node, ast.Assign) and len(node.targets) == 1
              and isinstance(node.targets[0], ast.Name) and node.targets[0].id == "sid"]
    if len(routes) != 1:
        raise ValueError("Unexpected Daemon.handle session assignment")
    route = ast.get_source_segment(source, routes[0])
    if route == NEW_ROUTE and source.count(NEW_ROUTE) == 1 and OLD_ROUTE not in source:
        return source
    if route != OLD_ROUTE or source.count(OLD_ROUTE) != 1 or NEW_ROUTE in source:
        raise ValueError("Unexpected routing source; no patch applied")
    result = source.replace(OLD_ROUTE, NEW_ROUTE, 1)
    result = result.replace(
        "# Browser-level Target.* calls must not use a session (stale or otherwise).",
        "# Target.setAutoAttach keeps its explicit target session; other Target.* calls stay browser-level.",
        1,
    )
    ast.parse(result)
    if hashlib.sha256(result.encode("utf-8")).hexdigest() != EXPECTED_PATCHED_SHA256:
        raise ValueError("Unexpected patched daemon.py SHA256; no write performed")
    return result


def patch_file(path: Path, version: str) -> None:
    # Do not normalize line endings before checking the full-file fingerprint.
    original = path.read_bytes().decode("utf-8")
    changed = patched_source(original, version)
    if changed != original:
        path.write_bytes(changed.encode("utf-8"))


def main() -> None:
    installed = distribution("browser-harness")
    files = [item for item in (installed.files or ()) if str(item) == "browser_harness/daemon.py"]
    if len(files) != 1:
        raise RuntimeError("Installed daemon.py could not be located unambiguously")
    patch_file(Path(installed.locate_file(files[0])), installed.version)
    print("BROWSER_HARNESS_SESSION_ROUTE_READY")


if __name__ == "__main__":
    main()
