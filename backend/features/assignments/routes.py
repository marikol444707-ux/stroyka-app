import json
from typing import Optional

import psycopg2.extras
from fastapi import Depends, Header, HTTPException

from .schema import ensure_assignments_schema

try:
    from backend.features.ai_findings.service import resolve_project_owner
    from backend.features.ai_tasks.service import task_owner_filter
except ModuleNotFoundError:
    from features.ai_findings.service import resolve_project_owner
    from features.ai_tasks.service import task_owner_filter


ASSIGNMENT_SYSTEM_CONDITION = """
(
    finding_id IS NOT NULL
    OR LOWER(COALESCE(created_by,'')) IN ('ии-контроль','system','система','ai-control')
    OR POSITION('ROOM_CONTROL:' IN UPPER(COALESCE(dedupe_key,''))) = 1
    OR POSITION('WORK_ROOM_LINK:' IN UPPER(COALESCE(dedupe_key,''))) = 1
    OR POSITION('MATERIAL_RULE:' IN UPPER(COALESCE(dedupe_key,''))) = 1
    OR POSITION('ESTIMATE_RULE:' IN UPPER(COALESCE(dedupe_key,''))) = 1
    OR POSITION('MATERIAL_CONTROL:' IN UPPER(COALESCE(dedupe_key,''))) = 1
    OR POSITION('ESTIMATE_NORM_REVIEW:' IN UPPER(COALESCE(dedupe_key,''))) = 1
    OR POSITION('ESTIMATE_DIFF_REVIEW:' IN UPPER(COALESCE(dedupe_key,''))) = 1
    OR POSITION('ESTIMATE_CHANGE_RECONCILE:' IN UPPER(COALESCE(dedupe_key,''))) = 1
    OR POSITION('MATERIAL_NORM_COVERAGE:' IN UPPER(COALESCE(dedupe_key,''))) = 1
    OR POSITION('system_rules' IN LOWER(COALESCE(action_payload,''))) > 0
    OR POSITION('room_measurement_review' IN LOWER(COALESCE(action_payload,''))) > 0
    OR POSITION('work_room_link_review' IN LOWER(COALESCE(action_payload,''))) > 0
    OR POSITION('material_outside_estimate_review' IN LOWER(COALESCE(action_payload,''))) > 0
    OR POSITION('material_transfer_sign_review' IN LOWER(COALESCE(action_payload,''))) > 0
    OR POSITION('estimate_quality_review' IN LOWER(COALESCE(action_payload,''))) > 0
    OR POSITION('estimate_norm_review' IN LOWER(COALESCE(action_payload,''))) > 0
    OR POSITION('material_norm_coverage' IN LOWER(COALESCE(action_payload,''))) > 0
    OR POSITION('estimate_diff_review' IN LOWER(COALESCE(action_payload,''))) > 0
    OR POSITION('estimate_change_reconcile' IN LOWER(COALESCE(action_payload,''))) > 0
)
"""


ASSIGNMENT_TASK_SELECT = f"""
SELECT id,
       owner_scope as "ownerScope",
       company_id as "companyId",
       project_id as "projectId",
       finding_id as "findingId",
       project_name as "projectName",
       title,
       description,
       assigned_role as "assignedRole",
       assigned_to as "assignedTo",
       status,
       due_date as "dueDate",
       accepted_by as "acceptedBy",
       accepted_at as "acceptedAt",
       closed_by as "closedBy",
       closed_at as "closedAt",
       action_label as "actionLabel",
       action_payload as "actionPayload",
       dedupe_key as "dedupeKey",
       created_by as "createdBy",
       created_by_id as "createdById",
       {ASSIGNMENT_SYSTEM_CONDITION} as "systemGenerated",
       created_at as "createdAt",
       updated_at as "updatedAt"
FROM ai_tasks
"""


def _text(value, limit=2000):
    return str(value or "").strip()[:limit]


def _json_list(value):
    if isinstance(value, list):
        return value
    if not value:
        return []
    try:
        parsed = json.loads(value) if isinstance(value, str) else value
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return []


def _attachment_rows(data: dict):
    rows = []
    attachments = data.get("attachments") or []
    if not isinstance(attachments, list):
        attachments = []
    for item in attachments:
        if isinstance(item, str):
            rows.append({"url": item, "type": "file", "name": "", "source": "manual"})
        elif isinstance(item, dict):
            rows.append({
                "url": item.get("url") or item.get("fileUrl") or item.get("photoUrl") or "",
                "type": item.get("type") or item.get("fileType") or "file",
                "name": item.get("name") or item.get("fileName") or "",
                "source": item.get("source") or "manual",
            })
    for url in _json_list(data.get("photos") or data.get("photoUrls") or data.get("photo_urls")):
        rows.append({"url": url, "type": "photo", "name": "", "source": "photo"})
    for url in _json_list(data.get("files") or data.get("fileUrls") or data.get("file_urls")):
        rows.append({"url": url, "type": "file", "name": "", "source": "file"})
    for key, file_type in (("photoUrl", "photo"), ("fileUrl", "file")):
        value = _text(data.get(key), 1000)
        if value:
            rows.append({"url": value, "type": file_type, "name": "", "source": key})

    seen = set()
    clean = []
    for row in rows:
        url = _text(row.get("url"), 2000)
        if not url or url in seen:
            continue
        seen.add(url)
        clean.append({
            "url": url,
            "type": _text(row.get("type") or "file", 100),
            "name": _text(row.get("name"), 255),
            "source": _text(row.get("source") or "manual", 100),
        })
    return clean


def _task_dict(row, reports=None):
    data = dict(row or {})
    data["reports"] = reports or []
    data["reportsCount"] = len(data["reports"])
    data["latestReport"] = data["reports"][0] if data["reports"] else None
    return data


def _report_dict(row, attachments=None):
    return {
        "id": row.get("id"),
        "taskId": row.get("task_id"),
        "text": row.get("report_text") or "",
        "status": row.get("status") or "",
        "authorId": row.get("author_id"),
        "authorName": row.get("author_name") or "",
        "authorRole": row.get("author_role") or "",
        "createdAt": str(row.get("created_at")) if row.get("created_at") else "",
        "attachments": attachments or [],
    }


def register_assignments_module(app, deps):
    get_db = deps["get_db"]
    get_current_user = deps["get_current_user"]
    resolve_work_company_context = deps["resolve_work_company_context"]
    effective_company_actors = deps["effective_company_actors"]
    leadership_roles = deps.get("leadership_roles") or ()
    full_view_roles = set(deps.get("full_view_roles") or leadership_roles)
    platform_task_roles = set(deps.get("platform_task_roles") or leadership_roles)
    assignment_roles = tuple(dict.fromkeys(deps.get("assignment_roles") or ()))
    assignment_role_set = set(assignment_roles)

    ensure_assignments_schema(get_db)

    def is_leadership_user(user: dict):
        return (user.get("role") or "") in set(leadership_roles) | platform_task_roles

    def selected_actor(cur, current_user, action_mode, x_company_id, x_company_mode):
        context = resolve_work_company_context(
            cur, current_user, None, action_mode,
            x_company_id=x_company_id, x_company_mode=x_company_mode,
        )
        if context.get("mode") == "all_companies":
            raise HTTPException(status_code=409, detail="Для поручений выберите одну конкретную компанию")
        actors = [
            dict(actor or {}) for actor in effective_company_actors(current_user, context)
            if str((actor or {}).get("role") or "").strip() in assignment_role_set
        ]
        if not actors:
            raise HTTPException(status_code=403, detail="Роль в выбранной компании не позволяет работать с поручениями")
        if len(actors) != 1:
            raise HTTPException(status_code=409, detail="Для поручений выберите одну конкретную компанию")
        actor = actors[0]
        try:
            company_id = int(actor.get("companyId") or actor.get("company_id"))
        except (TypeError, ValueError):
            company_id = 0
        if company_id <= 0:
            raise HTTPException(status_code=409, detail="Компания поручения не определена")
        actor["companyId"] = company_id
        actor["company_id"] = company_id
        return actor

    def assigned_projects(actor):
        values = _json_list(actor.get("assignedProjects", actor.get("assigned_projects", [])))
        result = {str(value).strip() for value in values if str(value or "").strip()}
        legacy = str(actor.get("projectName") or actor.get("project_name") or "").strip()
        if legacy:
            result.add(legacy)
        return result

    def require_actor_project(cur, actor, project_name, project_id=None, for_update=False):
        project = resolve_project_owner(
            cur, project_name, company_id=actor["companyId"], project_id=project_id, for_update=for_update,
        )
        if str(actor.get("role") or "").strip() not in full_view_roles:
            if project["name"].strip() not in assigned_projects(actor):
                raise HTTPException(status_code=403, detail="Нет доступа к объекту")
        return project

    def assigned_project_ids(cur, actor):
        assigned = sorted(assigned_projects(actor))
        if not assigned:
            return []
        cur.execute(
            "SELECT id,company_id,name FROM projects WHERE company_id=%s AND BTRIM(name)=ANY(%s) ORDER BY id",
            (actor["companyId"], assigned),
        )
        rows = cur.fetchall() or []
        by_name = {}
        for row in rows:
            name = str(row.get("name") or "").strip()
            by_name.setdefault(name, []).append(int(row.get("id") or 0))
        if any(name not in by_name or len(by_name[name]) != 1 or by_name[name][0] <= 0 for name in assigned):
            raise HTTPException(status_code=409, detail="Назначение по названию объекта неоднозначно")
        return [by_name[name][0] for name in assigned]

    def identity_values(user: dict):
        return [str(value).strip().lower() for value in (
            user.get("name"),
            user.get("email"),
            user.get("id"),
        ) if str(value or "").strip()]

    def can_access_task(user: dict, task: dict):
        if is_leadership_user(user):
            return True
        role = (user.get("role") or "").strip()
        identities = set(identity_values(user))
        assigned_to = str(task.get("assignedTo") or "").strip().lower()
        assigned_role = str(task.get("assignedRole") or "").strip()
        created_by = str(task.get("createdBy") or "").strip().lower()
        if assigned_to and assigned_to in identities:
            return True
        if not assigned_to and assigned_role and assigned_role == role:
            return True
        if created_by and created_by in identities:
            return True
        return False

    def append_user_task_scope(where: list[str], params: list, user: dict):
        identities = identity_values(user) or ["__no_identity__"]
        where.append(
            """
            (
                LOWER(COALESCE(assigned_to,'')) = ANY(%s)
                OR (
                    COALESCE(assigned_to,'') = ''
                    AND COALESCE(assigned_role,'') <> ''
                    AND assigned_role = %s
                )
                OR LOWER(COALESCE(created_by,'')) = ANY(%s)
            )
            """
        )
        params.extend([identities, user.get("role") or "", identities])

    def load_task(cur, task_id: int, actor: dict, *, for_update=False):
        include_platform = str(actor.get("role") or "").strip() in platform_task_roles
        if include_platform:
            cur.execute(
                ASSIGNMENT_TASK_SELECT + " WHERE id=%s AND owner_scope='platform' AND company_id IS NULL AND project_id IS NULL",
                (task_id,),
            )
        else:
            cur.execute(
                ASSIGNMENT_TASK_SELECT + " WHERE id=%s AND owner_scope='company' AND company_id=%s",
                (task_id, actor["companyId"]),
            )
        task = cur.fetchone()
        if not task:
            raise HTTPException(status_code=404, detail="Поручение не найдено")
        if task.get("ownerScope") == "platform":
            owner = {"scope": "platform", "companyId": None, "projectId": None}
        else:
            project = require_actor_project(
                cur, actor, task.get("projectName") or "", project_id=task.get("projectId"), for_update=for_update,
            )
            owner = {"scope": "company", "companyId": actor["companyId"], "projectId": project["id"]}
        if task.get("systemGenerated") and not is_leadership_user(actor):
            raise HTTPException(status_code=403, detail="ИИ-поручение доступно только в контуре ИИ-контроля")
        if not can_access_task(actor, task):
            raise HTTPException(status_code=403, detail="Поручение назначено другой роли или исполнителю")
        if for_update:
            owner_sql, owner_params = task_owner_filter(owner)
            cur.execute(ASSIGNMENT_TASK_SELECT + " WHERE " + owner_sql + " AND id=%s FOR UPDATE", (*owner_params, task_id))
            task = cur.fetchone()
            if not task:
                raise HTTPException(status_code=404, detail="Поручение не найдено")
        return task, owner

    def load_reports(cur, task_ids):
        if not task_ids:
            return {}
        cur.execute(
            """
            SELECT *
              FROM ai_task_reports
             WHERE task_id=ANY(%s)
             ORDER BY created_at DESC, id DESC
            """,
            (list(task_ids),),
        )
        report_rows = cur.fetchall()
        report_ids = [row.get("id") for row in report_rows]
        attachments_by_report = {}
        if report_ids:
            cur.execute(
                """
                SELECT *
                  FROM ai_task_attachments
                 WHERE report_id=ANY(%s)
                 ORDER BY id
                """,
                (report_ids,),
            )
            for att in cur.fetchall():
                attachments_by_report.setdefault(att.get("report_id"), []).append({
                    "id": att.get("id"),
                    "taskId": att.get("task_id"),
                    "url": att.get("file_url") or "",
                    "type": att.get("file_type") or "",
                    "name": att.get("file_name") or "",
                    "source": att.get("source") or "",
                    "createdAt": str(att.get("created_at")) if att.get("created_at") else "",
                })
        reports_by_task = {}
        for row in report_rows:
            reports_by_task.setdefault(row.get("task_id"), []).append(_report_dict(row, attachments_by_report.get(row.get("id"), [])))
        return reports_by_task

    @app.get("/assignments")
    def list_assignments(
        project_name: Optional[str] = None,
        status: Optional[str] = None,
        assigned_only: bool = False,
        include_system: bool = False,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            where = []
            params = []
            if project_name == "Система":
                if str(current_user.get("role") or "").strip() not in platform_task_roles:
                    raise HTTPException(status_code=403, detail="Нет доступа к системным поручениям")
                actor = dict(current_user)
                include_system = bool(include_system)
                where.append("owner_scope='platform' AND company_id IS NULL AND project_id IS NULL")
            else:
                actor = selected_actor(cur, current_user, "read", x_company_id, x_company_mode)
                include_system = bool(include_system and is_leadership_user(actor))
            if project_name and project_name != "Система":
                project = require_actor_project(cur, actor, project_name)
                where.append("owner_scope='company' AND company_id=%s AND project_id=%s")
                params.extend([actor["companyId"], project["id"]])
            elif not project_name:
                company_where = "(owner_scope='company' AND company_id=%s"
                params.append(actor["companyId"])
                if str(actor.get("role") or "").strip() not in full_view_roles:
                    project_ids = assigned_project_ids(cur, actor)
                    if not project_ids:
                        return []
                    company_where += " AND project_id=ANY(%s)"
                    params.append(project_ids)
                company_where += ")"
                where.append(company_where)
            if status:
                where.append("status=%s")
                params.append(status)
            if not include_system:
                where.append("NOT " + ASSIGNMENT_SYSTEM_CONDITION)
            if assigned_only or not is_leadership_user(actor):
                append_user_task_scope(where, params, actor)
            sql = ASSIGNMENT_TASK_SELECT
            if where:
                sql += " WHERE " + " AND ".join(where)
            sql += " ORDER BY updated_at DESC, id DESC LIMIT 500"
            cur.execute(sql, params)
            tasks = cur.fetchall()
            reports_by_task = load_reports(cur, [task.get("id") for task in tasks])
            return [_task_dict(task, reports_by_task.get(task.get("id"), [])) for task in tasks]
        finally:
            cur.close()
            conn.close()

    @app.get("/ai-tasks/{task_id}/reports")
    def list_task_reports(
        task_id: int,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            actor = dict(current_user) if str(current_user.get("role") or "").strip() in platform_task_roles else selected_actor(
                cur, current_user, "read", x_company_id, x_company_mode,
            )
            load_task(cur, task_id, actor)
            reports_by_task = load_reports(cur, [task_id])
            return reports_by_task.get(task_id, [])
        finally:
            cur.close()
            conn.close()

    @app.post("/ai-tasks/{task_id}/accept")
    def accept_task(
        task_id: int,
        data: dict = None,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        data = data or {}
        next_status = _text(data.get("status") or "В работе", 100)
        if next_status not in ("Принято к исполнению", "В работе"):
            raise HTTPException(status_code=400, detail="Поручение можно принять только в работу")
        conn = get_db()
        conn.autocommit = False
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            actor = dict(current_user) if str(current_user.get("role") or "").strip() in platform_task_roles else selected_actor(
                cur, current_user, "update", x_company_id, x_company_mode,
            )
            _task, owner = load_task(cur, task_id, actor, for_update=True)
            owner_sql, owner_params = task_owner_filter(owner)
            cur.execute(
                """
                UPDATE ai_tasks
                   SET status=%s,
                       accepted_by=%s,
                       accepted_at=COALESCE(accepted_at,NOW()),
                       updated_at=NOW()
                 WHERE """ + owner_sql + " AND id=%s",
                (next_status, actor.get("name") or actor.get("email") or "", *owner_params, task_id),
            )
            conn.commit()
            cur.execute(ASSIGNMENT_TASK_SELECT + " WHERE " + owner_sql + " AND id=%s", (*owner_params, task_id))
            return dict(cur.fetchone())
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()

    @app.post("/ai-tasks/{task_id}/reports")
    def create_task_report(
        task_id: int,
        data: dict,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        data = data or {}
        text = _text(data.get("text") or data.get("reportText") or data.get("comment"), 10000)
        attachments = _attachment_rows(data)
        if not text and not attachments:
            raise HTTPException(status_code=400, detail="Нужен текст отчета или вложение")
        report_status = _text(data.get("reportStatus") or data.get("status") or "Отчет отправлен", 100)
        next_task_status = _text(data.get("taskStatus") or data.get("nextStatus") or "На проверке", 100)
        conn = get_db()
        conn.autocommit = False
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            actor = dict(current_user) if str(current_user.get("role") or "").strip() in platform_task_roles else selected_actor(
                cur, current_user, "update", x_company_id, x_company_mode,
            )
            task, owner = load_task(cur, task_id, actor, for_update=True)
            owner_sql, owner_params = task_owner_filter(owner)
            cur.execute(
                """
                INSERT INTO ai_task_reports
                    (task_id,report_text,status,author_id,author_name,author_role)
                VALUES (%s,%s,%s,%s,%s,%s)
                RETURNING *
                """,
                (
                    task_id,
                    text,
                    report_status,
                    actor.get("id"),
                    actor.get("name") or actor.get("email") or "",
                    actor.get("role") or "",
                ),
            )
            report = cur.fetchone()
            for attachment in attachments:
                cur.execute(
                    """
                    INSERT INTO ai_task_attachments
                        (report_id,task_id,file_url,file_type,file_name,source)
                    VALUES (%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        report.get("id"),
                        task_id,
                        attachment["url"],
                        attachment["type"],
                        attachment["name"],
                        attachment["source"],
                    ),
                )
            if next_task_status and task.get("status") not in ("Закрыто", "Отклонено"):
                cur.execute(
                    """
                    UPDATE ai_tasks
                       SET status=%s,
                           accepted_by=COALESCE(NULLIF(accepted_by,''),%s),
                           accepted_at=COALESCE(accepted_at,NOW()),
                           updated_at=NOW()
                     WHERE """ + owner_sql + " AND id=%s",
                    (next_task_status, actor.get("name") or actor.get("email") or "", *owner_params, task_id),
                )
            conn.commit()
            reports_by_task = load_reports(cur, [task_id])
            cur.execute(ASSIGNMENT_TASK_SELECT + " WHERE " + owner_sql + " AND id=%s", (*owner_params, task_id))
            updated_task = cur.fetchone()
            return {
                "ok": True,
                "task": _task_dict(updated_task, reports_by_task.get(task_id, [])),
                "report": reports_by_task.get(task_id, [])[0] if reports_by_task.get(task_id) else _report_dict(report, []),
            }
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()

    @app.post("/ai-tasks/{task_id}/close")
    def close_task(
        task_id: int,
        data: dict = None,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        data = data or {}
        next_status = _text(data.get("status") or "Закрыто", 100)
        if next_status not in ("Закрыто", "Отклонено", "Исправлено"):
            raise HTTPException(status_code=400, detail="Недопустимый статус закрытия поручения")
        conn = get_db()
        conn.autocommit = False
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            actor = dict(current_user) if str(current_user.get("role") or "").strip() in platform_task_roles else selected_actor(
                cur, current_user, "update", x_company_id, x_company_mode,
            )
            _task, owner = load_task(cur, task_id, actor, for_update=True)
            owner_sql, owner_params = task_owner_filter(owner)
            comment = _text(data.get("text") or data.get("comment"), 10000)
            if comment:
                cur.execute(
                    """
                    INSERT INTO ai_task_reports
                        (task_id,report_text,status,author_id,author_name,author_role)
                    VALUES (%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        task_id,
                        comment,
                        "Закрытие",
                        actor.get("id"),
                        actor.get("name") or actor.get("email") or "",
                        actor.get("role") or "",
                    ),
                )
            cur.execute(
                """
                UPDATE ai_tasks
                   SET status=%s,
                       closed_by=%s,
                       closed_at=NOW(),
                       updated_at=NOW()
                 WHERE """ + owner_sql + " AND id=%s",
                (next_status, actor.get("name") or actor.get("email") or "", *owner_params, task_id),
            )
            conn.commit()
            reports_by_task = load_reports(cur, [task_id])
            cur.execute(ASSIGNMENT_TASK_SELECT + " WHERE " + owner_sql + " AND id=%s", (*owner_params, task_id))
            return {"ok": True, "task": _task_dict(cur.fetchone(), reports_by_task.get(task_id, []))}
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()
