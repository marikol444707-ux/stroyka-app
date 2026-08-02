#!/usr/bin/env python3
"""Protected production smoke for tenant-scoped tools and inventory."""

import importlib.util
import json
import time
import uuid
from pathlib import Path

import psycopg2
import psycopg2.extras


BASE_PATH = Path(__file__).with_name("smoke-main-warehouse-receipt.py")
SPEC = importlib.util.spec_from_file_location("main_warehouse_receipt_smoke", BASE_PATH)
BASE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BASE)
api_json = BASE.api_json
db_config = BASE.db_config
env_value = BASE.env_value
login = BASE.login

RUN_ID = uuid.uuid4().hex[:10]
TOOL_NAME = f"CODEX QA inventory tool {RUN_ID}"
MATERIAL_NAME = f"CODEX QA inventory material {RUN_ID}"


def select_company(token):
    context = api_json("GET", "/users/company-context", token=token)
    requested = int(env_value("SMOKE_COMPANY_ID", "0") or 0)
    candidates = [
        row for row in context.get("companies") or []
        if row.get("role") in {"директор", "зам_директора"}
    ]
    selected = next(
        (row for row in candidates if int(row.get("companyId") or 0) == requested),
        candidates[0] if candidates and not requested else None,
    )
    if not selected:
        raise RuntimeError("У smoke-пользователя нет роли директора или заместителя в выбранной компании")
    return int(selected["companyId"])


def cleanup():
    conn = None
    try:
        conn = psycopg2.connect(**db_config())
        cur = conn.cursor()
        cur.execute("SELECT id FROM tools WHERE name=%s", (TOOL_NAME,))
        tool_ids = [row[0] for row in cur.fetchall()]
        if tool_ids:
            cur.execute("DELETE FROM tool_history WHERE tool_id=ANY(%s)", (tool_ids,))
            cur.execute("DELETE FROM tools WHERE id=ANY(%s)", (tool_ids,))
        cur.execute("SELECT id FROM inventory WHERE notes=%s", (MATERIAL_NAME,))
        inventory_ids = [row[0] for row in cur.fetchall()]
        if inventory_ids:
            cur.execute("DELETE FROM inventory_items WHERE inventory_id=ANY(%s)", (inventory_ids,))
            cur.execute("DELETE FROM inventory WHERE id=ANY(%s)", (inventory_ids,))
        conn.commit()
        cur.close()
        print("cleanup: removed inventory ownership smoke rows")
    except Exception as exc:
        if conn:
            conn.rollback()
        print(f"cleanup warning: {exc}")
    finally:
        if conn:
            conn.close()


def stored_owner(table, row_id):
    conn = psycopg2.connect(**db_config())
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute(
            "SELECT owner_scope,company_id,project_id FROM " + table + " WHERE id=%s",
            (row_id,),
        )
        row = cur.fetchone()
        return dict(row or {})
    finally:
        cur.close()
        conn.close()


def main():
    email, password = env_value("SMOKE_EMAIL"), env_value("SMOKE_PASSWORD")
    if not email or not password:
        raise SystemExit("Нужно задать SMOKE_EMAIL и SMOKE_PASSWORD в окружении или backend/.env")
    token = login(email, password)
    company_id = select_company(token)
    headers = {"X-Company-Mode": "company", "X-Company-Id": str(company_id)}
    try:
        projects = api_json("GET", "/projects", token=token, headers=headers)
        project = next((row for row in projects if row.get("name")), None)
        if not project:
            raise RuntimeError("Для smoke нужен хотя бы один объект выбранной компании")

        tool = api_json("POST", "/tools", token=token, headers=headers, data={"name": TOOL_NAME})
        tool_id = int(tool.get("id") or 0)
        tool_owner = stored_owner("tools", tool_id)
        expected_company_tool = {"owner_scope": "company", "company_id": company_id, "project_id": None}
        if tool_owner != expected_company_tool:
            raise RuntimeError(f"Инструмент сохранил неверного владельца: {tool_owner}")
        history = api_json(
            "POST", "/tool-history", token=token, headers=headers,
            data={"toolId": tool_id, "toolName": TOOL_NAME, "action": "Проверка", "date": time.strftime("%Y-%m-%d")},
        )
        history_owner = stored_owner("tool_history", int(history.get("id") or 0))
        if history_owner != expected_company_tool:
            raise RuntimeError(f"История инструмента не унаследовала владельца: {history_owner}")
        visible_tools = api_json("GET", "/tools", token=token, headers=headers)
        if not any(int(row.get("id") or 0) == tool_id for row in visible_tools):
            raise RuntimeError("Инструмент не вернулся в выбранной компании")

        inventory = api_json(
            "POST", "/inventory", token=token, headers=headers,
            data={"project": project["name"], "date": time.strftime("%Y-%m-%d"), "createdBy": "CODEX QA", "notes": MATERIAL_NAME},
        )
        inventory_id = int(inventory.get("id") or 0)
        inventory_owner = stored_owner("inventory", inventory_id)
        expected_project_owner = {"owner_scope": "project", "company_id": company_id, "project_id": int(project["id"])}
        if inventory_owner != expected_project_owner:
            raise RuntimeError(f"Инвентаризация сохранила неверного владельца: {inventory_owner}")
        item = api_json(
            "POST", f"/inventory/{inventory_id}/items", token=token, headers=headers,
            data={"materialName": MATERIAL_NAME, "unit": "шт", "expected": 1, "actual": 1, "difference": 0},
        )
        item_owner = stored_owner("inventory_items", int(item.get("id") or 0))
        if item_owner != expected_project_owner:
            raise RuntimeError(f"Позиция инвентаризации не унаследовала владельца: {item_owner}")
        api_json(
            "POST", "/tools", token=token, expected=400,
            headers={"X-Company-Mode": "all_companies"}, data={"name": TOOL_NAME + " blocked"},
        )
        print(json.dumps({
            "ok": True, "companyId": company_id, "toolId": tool_id, "inventoryId": inventory_id,
            "checked": [
                "company-wide tool stores selected company owner",
                "tool history inherits exact tool owner",
                "selected company reads own tool",
                "project inventory stores selected company and exact project owner",
                "inventory item inherits exact inventory owner",
                "all-companies write is rejected",
            ],
        }, ensure_ascii=False, indent=2))
    finally:
        cleanup()


if __name__ == "__main__":
    main()
