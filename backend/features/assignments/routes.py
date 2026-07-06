import json
from typing import Optional

import psycopg2.extras
from fastapi import Depends, HTTPException

from .schema import ensure_assignments_schema


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
    require_roles = deps["require_roles"]
    require_project_access = deps["require_project_access"]
    visible_project_names = deps["visible_project_names"]
    leadership_roles = deps.get("leadership_roles") or ()
    finance_roles = deps.get("finance_roles") or ()
    assignment_roles = tuple(dict.fromkeys(deps.get("assignment_roles") or ()))

    ensure_assignments_schema(get_db)

    def assignment_access():
        return require_roles(*assignment_roles)

    def is_leadership_user(user: dict):
        return (user.get("role") or "") in leadership_roles

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

    def load_task(cur, task_id: int, user: dict):
        cur.execute(ASSIGNMENT_TASK_SELECT + " WHERE id=%s", (task_id,))
        task = cur.fetchone()
        if not task:
            raise HTTPException(status_code=404, detail="Поручение не найдено")
        project_name = task.get("projectName") or ""
        require_project_access(user, project_name)
        if task.get("systemGenerated") and not is_leadership_user(user):
            raise HTTPException(status_code=403, detail="ИИ-поручение доступно только в контуре ИИ-контроля")
        if not can_access_task(user, task):
            raise HTTPException(status_code=403, detail="Поручение назначено другой роли или исполнителю")
        return task

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
        current_user: dict = Depends(assignment_access()),
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            include_system = bool(include_system and is_leadership_user(current_user))
            where = []
            params = []
            if project_name:
                require_project_access(current_user, project_name)
                where.append("project_name=%s")
                params.append(project_name)
            else:
                allowed_projects = visible_project_names(current_user)
                if allowed_projects is not None:
                    if not allowed_projects:
                        return []
                    where.append("project_name=ANY(%s)")
                    params.append(allowed_projects)
            if status:
                where.append("status=%s")
                params.append(status)
            if not include_system:
                where.append("NOT " + ASSIGNMENT_SYSTEM_CONDITION)
            if assigned_only or not is_leadership_user(current_user):
                append_user_task_scope(where, params, current_user)
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
    def list_task_reports(task_id: int, current_user: dict = Depends(assignment_access())):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            load_task(cur, task_id, current_user)
            reports_by_task = load_reports(cur, [task_id])
            return reports_by_task.get(task_id, [])
        finally:
            cur.close()
            conn.close()

    @app.post("/ai-tasks/{task_id}/accept")
    def accept_task(task_id: int, data: dict = None, current_user: dict = Depends(assignment_access())):
        data = data or {}
        next_status = _text(data.get("status") or "В работе", 100)
        if next_status not in ("Принято к исполнению", "В работе"):
            raise HTTPException(status_code=400, detail="Поручение можно принять только в работу")
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            load_task(cur, task_id, current_user)
            cur.execute(
                """
                UPDATE ai_tasks
                   SET status=%s,
                       accepted_by=%s,
                       accepted_at=COALESCE(accepted_at,NOW()),
                       updated_at=NOW()
                 WHERE id=%s
                """,
                (next_status, current_user.get("name") or current_user.get("email") or "", task_id),
            )
            conn.commit()
            cur.execute(ASSIGNMENT_TASK_SELECT + " WHERE id=%s", (task_id,))
            return dict(cur.fetchone())
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()

    @app.post("/ai-tasks/{task_id}/reports")
    def create_task_report(task_id: int, data: dict, current_user: dict = Depends(assignment_access())):
        data = data or {}
        text = _text(data.get("text") or data.get("reportText") or data.get("comment"), 10000)
        attachments = _attachment_rows(data)
        if not text and not attachments:
            raise HTTPException(status_code=400, detail="Нужен текст отчета или вложение")
        report_status = _text(data.get("reportStatus") or data.get("status") or "Отчет отправлен", 100)
        next_task_status = _text(data.get("taskStatus") or data.get("nextStatus") or "На проверке", 100)
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            task = load_task(cur, task_id, current_user)
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
                    current_user.get("id"),
                    current_user.get("name") or current_user.get("email") or "",
                    current_user.get("role") or "",
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
                     WHERE id=%s
                    """,
                    (next_task_status, current_user.get("name") or current_user.get("email") or "", task_id),
                )
            conn.commit()
            reports_by_task = load_reports(cur, [task_id])
            cur.execute(ASSIGNMENT_TASK_SELECT + " WHERE id=%s", (task_id,))
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
    def close_task(task_id: int, data: dict = None, current_user: dict = Depends(assignment_access())):
        data = data or {}
        next_status = _text(data.get("status") or "Закрыто", 100)
        if next_status not in ("Закрыто", "Отклонено", "Исправлено"):
            raise HTTPException(status_code=400, detail="Недопустимый статус закрытия поручения")
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            load_task(cur, task_id, current_user)
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
                        current_user.get("id"),
                        current_user.get("name") or current_user.get("email") or "",
                        current_user.get("role") or "",
                    ),
                )
            cur.execute(
                """
                UPDATE ai_tasks
                   SET status=%s,
                       closed_by=%s,
                       closed_at=NOW(),
                       updated_at=NOW()
                 WHERE id=%s
                """,
                (next_status, current_user.get("name") or current_user.get("email") or "", task_id),
            )
            conn.commit()
            reports_by_task = load_reports(cur, [task_id])
            cur.execute(ASSIGNMENT_TASK_SELECT + " WHERE id=%s", (task_id,))
            return {"ok": True, "task": _task_dict(cur.fetchone(), reports_by_task.get(task_id, []))}
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()
