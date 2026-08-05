"""Reusable tenant-scoped read tools for the director assistant and jobs."""

import json
import re
from types import MappingProxyType

from psycopg2.extras import RealDictCursor

from backend.db import get_db
from backend.features.director_agent.policy import DIRECTOR_AGENT_READ_TOOLS


def _number(value):
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def _json_value(value, fallback=None):
    try:
        if value is None:
            return fallback
        if isinstance(value, (dict, list)):
            return value
        return json.loads(value)
    except Exception:
        return fallback


def _company_ids(values):
    company_ids = set()
    for value in values or []:
        try:
            company_id = int(value)
        except (TypeError, ValueError):
            continue
        if company_id > 0:
            company_ids.add(company_id)
    return sorted(company_ids)


def _positive_int_or_none(value):
    if isinstance(value, bool):
        return None
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        return None
    return normalized if normalized > 0 else None


def validate_director_agent_read_sql(sql):
    statement = str(sql or "").strip()
    if not re.match(r"^SELECT\b", statement, flags=re.IGNORECASE) or ";" in statement:
        raise ValueError("director agent tools allow one SELECT statement only")
    return statement


def execute_director_agent_read_query(sql, params=(), *, connection_factory=get_db):
    statement = validate_director_agent_read_sql(sql)
    connection = connection_factory()
    try:
        connection.set_session(readonly=True, autocommit=True)
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(statement, params)
            return [dict(row) for row in cursor.fetchall()]
    finally:
        connection.close()


class _DirectorAgentReadToolset:
    def __init__(self, query):
        if not callable(query):
            raise ValueError("query must be callable")
        self.query = query

    def projects(self, args, company_ids=None):
        company_ids = _company_ids(company_ids)
        if not company_ids:
            return []
        search = str((args or {}).get("search") or "").strip()
        params = [company_ids]
        where = ["company_id = ANY(%s)"]
        if search:
            where.append("(name ILIKE %s OR client ILIKE %s)")
            params.extend(["%" + search + "%", "%" + search + "%"])
        rows = self.query(
            f"""SELECT name, client, status, budget, progress, deadline
                FROM projects WHERE {' AND '.join(where)}
                ORDER BY archived ASC NULLS FIRST, id DESC
                LIMIT 40""",
            tuple(params),
        )
        return [
            {
                "name": row.get("name") or "",
                "client": row.get("client") or "",
                "status": row.get("status") or "",
                "budget": round(_number(row.get("budget")), 2),
                "progress": int(_number(row.get("progress"))),
                "deadline": row.get("deadline") or "",
            }
            for row in rows
        ]

    def warehouse(self, args, company_ids=None):
        company_ids = _company_ids(company_ids)
        if not company_ids:
            return {"mainWarehouse": [], "objectMaterials": []}
        search = str((args or {}).get("search") or "").strip()
        params = [company_ids]
        where = ["company_id = ANY(%s)"]
        if search:
            where.append("name ILIKE %s")
            params.append("%" + search + "%")
        main_rows = self.query(
            f"""SELECT name, quantity, unit, price, min_quantity, category
                FROM warehouse_main WHERE {' AND '.join(where)}
                ORDER BY COALESCE(quantity,0) ASC, name
                LIMIT 40""",
            tuple(params),
        )
        object_rows = self.query(
            f"""SELECT name, quantity, unit, price, project, category
                FROM materials WHERE {' AND '.join(where)}
                ORDER BY project, name
                LIMIT 60""",
            tuple(params),
        )
        return {
            "mainWarehouse": [
                {
                    "name": row.get("name") or "",
                    "qty": round(_number(row.get("quantity")), 3),
                    "unit": row.get("unit") or "",
                    "minQty": round(_number(row.get("min_quantity")), 3),
                    "category": row.get("category") or "",
                }
                for row in main_rows
            ],
            "objectMaterials": [
                {
                    "project": row.get("project") or "",
                    "name": row.get("name") or "",
                    "qty": round(_number(row.get("quantity")), 3),
                    "unit": row.get("unit") or "",
                    "category": row.get("category") or "",
                }
                for row in object_rows
            ],
        }

    def supply(self, args, company_ids=None):
        del args
        company_ids = _company_ids(company_ids)
        if not company_ids:
            return {
                "requestStatusCounts": {},
                "recentRequests": [],
                "recentDeliveries": [],
                "openClaims": [],
            }
        request_rows = self.query(
            """SELECT id, project, material_name, quantity, unit, status, urgency,
                      created_by, created_at, items_json
               FROM supply_requests
               WHERE company_id = ANY(%s)
               ORDER BY id DESC LIMIT 60""",
            (company_ids,),
        )
        delivery_rows = self.query(
            """SELECT id, project, material_name, planned_quantity, shipped_quantity,
                      received_quantity, unit, supplier_name, status, quality_status, created_at
               FROM supply_deliveries
               WHERE company_id = ANY(%s)
               ORDER BY id DESC LIMIT 50""",
            (company_ids,),
        )
        claim_rows = self.query(
            """SELECT c.id, c.project, c.material_name, c.claim_type, c.status,
                      c.shortage_quantity, c.created_at
               FROM supply_claims c
               WHERE EXISTS (
                       SELECT 1 FROM supply_requests r
                       WHERE r.id=c.request_id AND r.company_id = ANY(%s)
                   )
                  OR EXISTS (
                       SELECT 1 FROM supply_deliveries d
                       WHERE d.id=c.delivery_id AND d.company_id = ANY(%s)
                   )
               ORDER BY c.id DESC LIMIT 30""",
            (company_ids, company_ids),
        )
        status_counts = {}
        for row in request_rows:
            status = row.get("status") or "Без статуса"
            status_counts[status] = status_counts.get(status, 0) + 1
        requests = []
        for row in request_rows[:25]:
            items = _json_value(row.get("items_json"), []) or []
            material_name = row.get("material_name") or ""
            quantity = _number(row.get("quantity"))
            unit = row.get("unit") or ""
            if items:
                first = items[0] or {}
                material_name = material_name or first.get("materialName") or ""
                quantity = quantity or _number(first.get("quantity"))
                unit = unit or first.get("unit") or ""
            requests.append({
                "id": row.get("id"),
                "project": row.get("project") or "",
                "material": material_name,
                "qty": round(quantity, 3),
                "unit": unit,
                "status": row.get("status") or "",
                "urgency": row.get("urgency") or "",
                "createdBy": row.get("created_by") or "",
            })
        return {
            "requestStatusCounts": status_counts,
            "recentRequests": requests,
            "recentDeliveries": [
                {
                    "project": row.get("project") or "",
                    "material": row.get("material_name") or "",
                    "planned": round(_number(row.get("planned_quantity")), 3),
                    "shipped": round(_number(row.get("shipped_quantity")), 3),
                    "received": round(_number(row.get("received_quantity")), 3),
                    "unit": row.get("unit") or "",
                    "supplier": row.get("supplier_name") or "",
                    "status": row.get("status") or "",
                    "quality": row.get("quality_status") or "",
                }
                for row in delivery_rows[:25]
            ],
            "openClaims": [
                {
                    "project": row.get("project") or "",
                    "material": row.get("material_name") or "",
                    "type": row.get("claim_type") or "",
                    "status": row.get("status") or "",
                    "shortage": round(_number(row.get("shortage_quantity")), 3),
                }
                for row in claim_rows
                if (row.get("status") or "") != "Закрыта"
            ][:20],
        }

    def estimates(self, args, company_ids=None):
        del args
        company_ids = _company_ids(company_ids)
        if not company_ids:
            return []
        rows = self.query(
            """SELECT id, name, project_name, version, status, smeta_type, work_package, sections_json, created_at
               FROM estimates
               WHERE company_id = ANY(%s)
                 AND COALESCE(is_template,FALSE)=FALSE
               ORDER BY id DESC LIMIT 30""",
            (company_ids,),
        )
        result = []
        for row in rows:
            sections = _json_value(row.get("sections_json"), []) or []
            total = 0.0
            item_count = 0
            material_count = 0
            work_count = 0
            for section in sections:
                for item in (section or {}).get("items", []):
                    item_count += 1
                    item_type = str(item.get("itemType") or item.get("type") or "").lower()
                    if item_type == "material":
                        material_count += 1
                    else:
                        work_count += 1
                    quantity = _number(item.get("quantity"))
                    work = _number(item.get("priceWork"))
                    material = _number(item.get("priceMaterial"))
                    if item.get("isImported"):
                        total_work = _number(item.get("totalWork") or item.get("workTotal") or item.get("workSum"))
                        total_material = _number(item.get("totalMaterial") or item.get("materialTotal") or item.get("materialSum"))
                        line_total = _number(item.get("lineTotal") or item.get("currentTotal") or item.get("total") or item.get("sum") or item.get("amount") or item.get("totalSum"))
                        total += (total_work + total_material) or line_total or (quantity * (work + material))
                    else:
                        total += quantity * (work + material)
            result.append({
                "id": row.get("id"),
                "name": row.get("name") or "",
                "project": row.get("project_name") or "",
                "version": row.get("version") or "",
                "status": row.get("status") or "",
                "type": row.get("smeta_type") or "",
                "package": row.get("work_package") or "",
                "items": item_count,
                "workItems": work_count,
                "materialItems": material_count,
                "total": round(total, 2),
            })
        return result

    def finances(self, args, company_ids=None):
        company_ids = _company_ids(company_ids)
        if not company_ids:
            return []
        project = str((args or {}).get("project") or "").strip()
        where = ["company_id = ANY(%s)"]
        params = [company_ids]
        if project:
            where.append("name=%s")
            params.append(project)
        projects = self.query(
            f"""SELECT company_id, name, budget, status
                FROM projects
                WHERE {' AND '.join(where)}
                ORDER BY id DESC LIMIT 40""",
            tuple(params),
        )
        names = [row.get("name") for row in projects if row.get("name")]
        if not names:
            return []
        payments = self.query(
            """SELECT company_id, project_name, COALESCE(SUM(amount),0) AS total
               FROM project_payments
               WHERE company_id = ANY(%s) AND project_name = ANY(%s)
               GROUP BY company_id, project_name""",
            (company_ids, names),
        )
        payments_by_project = {
            (_positive_int_or_none(row.get("company_id")), row.get("project_name")): _number(row.get("total"))
            for row in payments
        }
        return [
            {
                "companyId": row.get("company_id"),
                "project": row.get("name") or "",
                "status": row.get("status") or "",
                "budget": round(_number(row.get("budget")), 2),
                "paymentsNet": round(payments_by_project.get(
                    (_positive_int_or_none(row.get("company_id")), row.get("name")),
                    0,
                ), 2),
                "manualExpenses": None,
                "manualExpensesScoped": False,
            }
            for row in projects
        ]

    def staff(self, args, company_ids=None):
        del args
        company_ids = _company_ids(company_ids)
        if not company_ids:
            return {"roleCounts": [], "staff": []}
        staff_rows = self.query(
            """SELECT name, role, project, specialization
               FROM staff
               WHERE company_id = ANY(%s)
               ORDER BY project, role, name LIMIT 80""",
            (company_ids,),
        )
        user_rows = self.query(
            """SELECT m.role, COUNT(DISTINCT m.user_id) AS cnt
               FROM user_company_roles m
               JOIN users u ON u.id=m.user_id
               WHERE m.company_id = ANY(%s)
                 AND COALESCE(m.active, TRUE)=TRUE
                 AND COALESCE(u.active, TRUE)=TRUE
               GROUP BY m.role
               ORDER BY m.role""",
            (company_ids,),
        )
        return {
            "roleCounts": [
                {"role": row.get("role") or "", "count": int(row.get("cnt") or 0)}
                for row in user_rows
            ],
            "staff": [
                {
                    "name": row.get("name") or "",
                    "role": row.get("role") or "",
                    "project": row.get("project") or "",
                    "specialization": row.get("specialization") or "",
                }
                for row in staff_rows
            ],
        }

    def ai_tasks(self, args, company_ids=None):
        del args
        company_ids = _company_ids(company_ids)
        if not company_ids:
            return {"openStatusCounts": {}, "tasks": []}
        rows = self.query(
            """SELECT project_name, title, assigned_role, assigned_to, status, due_date, updated_at
               FROM ai_tasks
               WHERE owner_scope='company'
                 AND company_id=ANY(%s)
                 AND COALESCE(status,'') NOT IN ('Закрыто','Отклонено')
               ORDER BY updated_at DESC, id DESC LIMIT 80""",
            (company_ids,),
        )
        counts = {}
        for row in rows:
            status = row.get("status") or "Без статуса"
            counts[status] = counts.get(status, 0) + 1
        return {
            "openStatusCounts": counts,
            "tasks": [
                {
                    "project": row.get("project_name") or "",
                    "title": row.get("title") or "",
                    "assignedRole": row.get("assigned_role") or "",
                    "assignedTo": row.get("assigned_to") or "",
                    "status": row.get("status") or "",
                    "dueDate": str(row.get("due_date")) if row.get("due_date") else "",
                }
                for row in rows[:30]
            ],
        }


_TOOL_DESCRIPTIONS = {
    "projects": "Объекты: статус, бюджет, прогресс, сроки. args: {search?: текст}",
    "warehouse": "Склад и материалы на объектах. args: {search?: материал}",
    "supply": "Снабжение: заявки, поставки, претензии. args: {}",
    "estimates": "Сметы: редакции, типы строк, сумма, объект. args: {}",
    "finances": "Финансовая сводка по объектам. args: {project?: название объекта}",
    "staff": "Персонал и активные роли. args: {}",
    "ai_tasks": "Открытые задачи ИИ-контроля. args: {}",
}


def build_director_agent_tools(query):
    toolset = _DirectorAgentReadToolset(query)
    handlers = {
        "projects": toolset.projects,
        "warehouse": toolset.warehouse,
        "supply": toolset.supply,
        "estimates": toolset.estimates,
        "finances": toolset.finances,
        "staff": toolset.staff,
        "ai_tasks": toolset.ai_tasks,
    }
    if tuple(handlers) != DIRECTOR_AGENT_READ_TOOLS:
        raise RuntimeError("director agent read-tool registry does not match its policy")
    return MappingProxyType({
        name: MappingProxyType({
            "fn": handlers[name],
            "desc": _TOOL_DESCRIPTIONS[name],
        })
        for name in DIRECTOR_AGENT_READ_TOOLS
    })


DIRECTOR_AGENT_TOOLS = build_director_agent_tools(execute_director_agent_read_query)


def read_director_agent_tool_results(*, company_id, connection_factory=get_db):
    """Read all allowlisted tools in one rolled-back read-only transaction."""
    if type(company_id) is not int or company_id <= 0:
        raise ValueError("company_id must be one positive integer")
    connection = connection_factory()
    try:
        connection.set_session(readonly=True, autocommit=False)
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            def query(sql, params=()):
                statement = validate_director_agent_read_sql(sql)
                cursor.execute(statement, params)
                return [dict(row) for row in cursor.fetchall()]

            tools = build_director_agent_tools(query)
            results = {
                tool_name: tools[tool_name]["fn"]({}, [company_id])
                for tool_name in DIRECTOR_AGENT_READ_TOOLS
            }
        connection.rollback()
        return results
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()
