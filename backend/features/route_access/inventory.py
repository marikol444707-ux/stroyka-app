"""Describe FastAPI routes registered by importing the backend.

Importing ``backend.main`` runs startup DDL. This loader stubs the database
connection for that import and then restores ``psycopg2.connect``. Feature
flags that add routes only when enabled are forced off, so the inventory is
the default server route set.
"""

import json
import os
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
INVENTORY_PATH = ROOT / "docs" / "route-access-inventory.json"
MAIN_PATH = ROOT / "backend" / "main.py"

# These flags register extra routes at import time. The inventory is the
# default server, with every one of them off.
REGISTRATION_FLAGS = (
    "WAREHOUSE_ANOMALY_PREVIEW_HTTP_ENABLED",
    "ASSIGNMENT_DAILY_DRAFT_HTTP_ENABLED",
    "ACCOUNTING_EXCEPTION_CHECKS_HTTP_ENABLED",
    "HUMAN_APPROVED_ACTIONS_HTTP_ENABLED",
    "SUPPLY_TECHNICAL_COMPARISON_HTTP_ENABLED",
    "SUPPLIER_MATERIAL_CAPABILITY_RUNTIME_ENABLED",
    "SUPPLIER_DEAL_PARTIES_ENABLED",
    "SUPPLIER_CONTRACT_SNAPSHOTS_ENABLED",
    "SUPPLIER_DOCUMENT_CONTRACT_BINDINGS_ENABLED",
    "SUPPLIER_LEGACY_CONTRACT_BINDING_ENABLED",
    "SUPPLIER_LEGACY_LINE_REVIEW_ENABLED",
    "SUPPLIER_CONTRACT_RECOGNITION_ENABLED",
    "PUBLIC_UPLOADS_MOUNT_ENABLED",
)

# Flag-gated registrations stay out of the default inventory. The source
# check keeps those call sites from disappearing during a split.
GATED_REGISTRATIONS = (
    ("WAREHOUSE_ANOMALY_PREVIEW_HTTP_ENABLED", "register_warehouse_anomaly_preview_routes"),
    ("ASSIGNMENT_DAILY_DRAFT_HTTP_ENABLED", "register_assignment_daily_draft_preview_routes"),
    ("ACCOUNTING_EXCEPTION_CHECKS_HTTP_ENABLED", "register_accounting_exception_check_routes"),
    ("HUMAN_APPROVED_ACTIONS_HTTP_ENABLED", "register_human_approved_action_routes"),
    ("SUPPLY_TECHNICAL_COMPARISON_HTTP_ENABLED", "register_supply_technical_comparison_routes"),
    ("SUPPLIER_MATERIAL_CAPABILITY_RUNTIME_ENABLED", "register_material_capability_runtime_module"),
    ("SUPPLIER_DEAL_PARTIES_ENABLED", "register_supplier_deal_parties_module"),
    ("SUPPLIER_CONTRACT_SNAPSHOTS_ENABLED", "register_supplier_contracts_module"),
    ("SUPPLIER_DOCUMENT_CONTRACT_BINDINGS_ENABLED", "register_document_contract_routes"),
    ("SUPPLIER_LEGACY_CONTRACT_BINDING_ENABLED", "register_legacy_binding_routes"),
    ("SUPPLIER_LEGACY_LINE_REVIEW_ENABLED", "register_legacy_line_review_routes"),
    ("SUPPLIER_CONTRACT_RECOGNITION_ENABLED", "register_contract_recognition"),
    ("PUBLIC_UPLOADS_MOUNT_ENABLED", 'app.mount("/uploads"'),
)


class _Cursor:
    def __init__(self):
        self.rowcount = 0

    def execute(self, *_args, **_kwargs):
        return None

    def fetchone(self):
        return None

    def fetchall(self):
        return []

    def close(self):
        return None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class _Connection:
    def __init__(self):
        self.autocommit = True

    def cursor(self, *_args, **_kwargs):
        return _Cursor()

    def commit(self):
        return None

    def rollback(self):
        return None

    def close(self):
        return None

    def set_session(self, *_args, **_kwargs):
        return None


def _role_set(call):
    found = []
    for cell in getattr(call, "__closure__", None) or ():
        try:
            value = cell.cell_contents
        except ValueError:
            continue
        if isinstance(value, (set, frozenset)) and all(isinstance(item, str) for item in value):
            found.append(sorted(value))
    if not found:
        return None
    if len(found) == 1:
        return found[0]
    return found


def _walk_dependencies(dependant):
    described = []
    for child in dependant.dependencies:
        call = child.call
        described.append({
            "callable": getattr(call, "__name__", type(call).__name__),
            "parameter": child.name,
            "roles": _role_set(call),
        })
        described.extend(_walk_dependencies(child))
    return described


def describe_route(route):
    methods = sorted(route.methods or [])
    dependant = getattr(route, "dependant", None)
    return {
        "path": route.path,
        "methods": methods,
        "dependencies": _walk_dependencies(dependant) if dependant is not None else [],
    }


def collect_routes(app):
    described = [describe_route(route) for route in app.routes if getattr(route, "path", None)]
    described.sort(key=lambda item: (
        item["path"],
        ",".join(item["methods"]),
        json.dumps(item["dependencies"], ensure_ascii=False, sort_keys=True),
    ))
    return described


def load_app():
    """Import the FastAPI app once, with startup SQL pointed at a fake connection."""
    if "backend.main" in sys.modules:
        raise RuntimeError(
            "backend.main was imported before the route inventory loader; "
            "the inventory compares the default flag-off app"
        )

    import psycopg2

    saved_connect = psycopg2.connect
    saved_cwd = os.getcwd()
    saved_env = {name: os.environ.get(name) for name in REGISTRATION_FLAGS}
    workspace = tempfile.TemporaryDirectory()

    def fake_connect(*_args, **_kwargs):
        return _Connection()

    psycopg2.connect = fake_connect
    os.chdir(workspace.name)
    for name in REGISTRATION_FLAGS:
        os.environ.pop(name, None)
    try:
        from backend.main import app
    finally:
        psycopg2.connect = saved_connect
        os.chdir(saved_cwd)
        for name, value in saved_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        workspace.cleanup()
    return app


def load_inventory():
    return json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))


def dump_inventory(routes):
    payload = {
        "version": 1,
        "note": (
            "Default server routes with feature-flag registration turned off. "
            "Each entry is path, methods and dependency callables with role sets."
        ),
        "routes": routes,
    }
    INVENTORY_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return payload


if __name__ == "__main__":
    dump_inventory(collect_routes(load_app()))
