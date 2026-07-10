#!/usr/bin/env python3
import json
import re
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "docs" / "m6-tenant-registry.json"
SOURCE_PATHS = [
    ROOT / "backend" / "main.py",
    *sorted((ROOT / "backend" / "features").glob("*/*.py")),
]
REQUIRED_FIELDS = {
    "domain", "resource", "kind", "parent", "companyState",
    "ownerSource", "routePrefixes", "stage", "priority",
}
REQUIRED_DOMAINS = {
    "projects", "documents", "staff", "estimates", "execution",
    "acts", "ai", "messenger", "audit",
}
ALLOWED_STATES = {"missing", "legacy_default", "stored", "public_surface"}
ALLOWED_PRIORITIES = {"critical", "high", "medium", "low"}


def fail(message, failures):
    failures.append(message)


def main():
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    entries = registry.get("entries") or []
    failures = []
    sources = "\n".join(path.read_text(encoding="utf-8") for path in SOURCE_PATHS if path.exists())
    resources = set()

    if not entries:
        fail("registry has no entries", failures)

    for index, entry in enumerate(entries, 1):
        missing = sorted(REQUIRED_FIELDS - set(entry))
        if missing:
            fail(f"entry {index} misses fields: {', '.join(missing)}", failures)
            continue
        resource = str(entry["resource"]).strip()
        if not resource:
            fail(f"entry {index} has empty resource", failures)
        elif resource in resources:
            fail(f"duplicate resource: {resource}", failures)
        resources.add(resource)
        if entry["kind"] not in {"table", "surface"}:
            fail(f"{resource}: unsupported kind {entry['kind']}", failures)
        if entry["companyState"] not in ALLOWED_STATES:
            fail(f"{resource}: unsupported companyState {entry['companyState']}", failures)
        if entry["priority"] not in ALLOWED_PRIORITIES:
            fail(f"{resource}: unsupported priority {entry['priority']}", failures)
        if not re.fullmatch(r"M6\.[0-8]", str(entry["stage"])):
            fail(f"{resource}: invalid stage {entry['stage']}", failures)
        if entry["kind"] == "table" and not re.search(
            rf"\b(?:CREATE TABLE IF NOT EXISTS|ALTER TABLE|FROM|INTO|UPDATE)\s+{re.escape(resource)}\b",
            sources,
            re.IGNORECASE,
        ):
            fail(f"{resource}: table is not referenced by backend sources", failures)
        route_prefixes = entry.get("routePrefixes") or []
        if not route_prefixes:
            fail(f"{resource}: routePrefixes is empty", failures)
        for prefix in route_prefixes:
            if prefix not in sources:
                fail(f"{resource}: route prefix not found in backend sources: {prefix}", failures)

    missing_domains = sorted(REQUIRED_DOMAINS - {entry.get("domain") for entry in entries})
    if missing_domains:
        fail("required domains missing: " + ", ".join(missing_domains), failures)

    by_stage = Counter(entry.get("stage") for entry in entries)
    by_state = Counter(entry.get("companyState") for entry in entries)
    by_priority = Counter(entry.get("priority") for entry in entries)
    result = {
        "ok": not failures,
        "registry": str(REGISTRY_PATH.relative_to(ROOT)),
        "entries": len(entries),
        "byStage": dict(sorted(by_stage.items())),
        "byCompanyState": dict(sorted(by_state.items())),
        "byPriority": dict(sorted(by_priority.items())),
        "failures": failures,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
