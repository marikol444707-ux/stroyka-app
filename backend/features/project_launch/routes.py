import psycopg2.extras
from fastapi import Body, Depends, HTTPException

from .schema import ensure_project_launch_schema
from .service import (
    as_json,
    document_belongs_to_project,
    fetch_draft,
    fetch_project,
    json_param,
    normalized_status,
    row_to_draft,
    text,
)


def register_project_launch_module(app, deps):
    get_db = deps["get_db"]
    require_roles = deps["require_roles"]
    require_project_access = deps["require_project_access"]
    log_audit = deps.get("log_audit")
    read_roles = deps.get("read_roles") or ()
    write_roles = deps.get("write_roles") or read_roles

    ensure_project_launch_schema(get_db)

    read_access = require_roles(*read_roles)
    write_access = require_roles(*write_roles)

    def audit(user, action, entity_id=None, description="", project_name=""):
        if not log_audit:
            return
        log_audit(
            user.get("name") or "",
            user.get("role") or "",
            action,
            "project_launch_draft",
            entity_id,
            description,
            project_name,
        )

    @app.get("/project-launch/drafts")
    def list_project_launch_drafts(
        project_name: str,
        status: str = "",
        limit: int = 50,
        current_user: dict = Depends(read_access),
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        project = fetch_project(cur, project_name)
        require_project_access(current_user, project["name"])
        params = [project["name"]]
        where = "WHERE project_name=%s"
        if status:
            where += " AND status=%s"
            params.append(text(status, 40))
        safe_limit = max(1, min(int(limit or 50), 200))
        params.append(safe_limit)
        cur.execute(
            "SELECT * FROM project_launch_drafts "
            + where
            + " ORDER BY id DESC LIMIT %s",
            params,
        )
        rows = [row_to_draft(row) for row in cur.fetchall()]
        cur.close()
        conn.close()
        return {"ok": True, "items": rows}

    @app.get("/project-launch/drafts/{draft_id}")
    def get_project_launch_draft(draft_id: int, current_user: dict = Depends(read_access)):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        draft = fetch_draft(cur, draft_id)
        require_project_access(current_user, draft.get("project_name") or "")
        result = row_to_draft(draft)
        cur.close()
        conn.close()
        return {"ok": True, "draft": result}

    @app.post("/project-launch/drafts")
    def create_project_launch_draft(data: dict, current_user: dict = Depends(write_access)):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        project = fetch_project(cur, data.get("projectName") or data.get("project_name"))
        require_project_access(current_user, project["name"])
        source_document_id = data.get("sourceDocumentId") or data.get("source_document_id")
        source_document_id = int(source_document_id) if source_document_id not in (None, "") else None
        document_belongs_to_project(cur, source_document_id, project["name"])
        status = normalized_status(data.get("status"), "draft")
        cur.execute(
            """
            INSERT INTO project_launch_drafts (
                project_id, project_name, company_id, source_document_id,
                source_file_url, source_file_name, source_file_type, status,
                extracted_json, project_patch_json, counterparty_json, contract_terms_json,
                estimate_draft_json, findings_json, tasks_json, confidence, warnings_json,
                created_by, created_by_id
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING *
            """,
            (
                project.get("id"),
                project.get("name"),
                project.get("company_id") or current_user.get("companyId") or current_user.get("company_id") or 1,
                source_document_id,
                text(data.get("sourceFileUrl") or data.get("source_file_url"), 2000),
                text(data.get("sourceFileName") or data.get("source_file_name"), 500),
                text(data.get("sourceFileType") or data.get("source_file_type"), 120),
                status,
                json_param(data.get("extracted"), {}),
                json_param(data.get("projectPatch"), {}),
                json_param(data.get("counterparty"), {}),
                json_param(data.get("contractTerms"), {}),
                json_param(data.get("estimateDraft"), {}),
                json_param(data.get("findings"), []),
                json_param(data.get("tasks"), []),
                float(data.get("confidence") or 0),
                json_param(data.get("warnings"), []),
                current_user.get("name") or "",
                current_user.get("id"),
            ),
        )
        draft = row_to_draft(cur.fetchone())
        conn.commit()
        cur.close()
        conn.close()
        audit(current_user, "create_project_launch_draft", draft.get("id"), "Создан черновик запуска объекта", project.get("name"))
        return {"ok": True, "draft": draft}

    @app.patch("/project-launch/drafts/{draft_id}")
    def update_project_launch_draft(draft_id: int, data: dict, current_user: dict = Depends(write_access)):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        draft = fetch_draft(cur, draft_id)
        require_project_access(current_user, draft.get("project_name") or "")
        if draft.get("status") == "applied":
            raise HTTPException(status_code=409, detail="Примененный черновик нельзя редактировать")
        status = normalized_status(data.get("status"), draft.get("status") or "draft") if "status" in data else draft.get("status")
        updates = []
        values = []
        mapping = (
            ("sourceFileUrl", "source_file_url", None),
            ("sourceFileName", "source_file_name", None),
            ("sourceFileType", "source_file_type", None),
            ("extracted", "extracted_json", {}),
            ("projectPatch", "project_patch_json", {}),
            ("counterparty", "counterparty_json", {}),
            ("contractTerms", "contract_terms_json", {}),
            ("estimateDraft", "estimate_draft_json", {}),
            ("findings", "findings_json", []),
            ("tasks", "tasks_json", []),
            ("warnings", "warnings_json", []),
        )
        for api_key, db_key, fallback in mapping:
            if api_key not in data:
                continue
            updates.append(db_key + "=%s")
            if fallback is None:
                values.append(text(data.get(api_key), 2000))
            else:
                values.append(json_param(data.get(api_key), fallback))
        if "confidence" in data:
            updates.append("confidence=%s")
            values.append(float(data.get("confidence") or 0))
        if "status" in data:
            updates.append("status=%s")
            values.append(status)
            if status == "reviewed":
                updates.append("reviewed_by=%s")
                updates.append("reviewed_at=NOW()")
                values.append(current_user.get("name") or "")
        if not updates:
            cur.close()
            conn.close()
            return {"ok": True, "draft": row_to_draft(draft)}
        values.append(draft_id)
        cur.execute(
            "UPDATE project_launch_drafts SET " + ", ".join(updates) + " WHERE id=%s RETURNING *",
            values,
        )
        updated = row_to_draft(cur.fetchone())
        conn.commit()
        cur.close()
        conn.close()
        audit(current_user, "update_project_launch_draft", draft_id, "Обновлен черновик запуска объекта", updated.get("projectName"))
        return {"ok": True, "draft": updated}

    @app.post("/project-launch/drafts/{draft_id}/reject")
    def reject_project_launch_draft(
        draft_id: int,
        data: dict = Body(default=None),
        current_user: dict = Depends(write_access),
    ):
        data = data or {}
        reason = text(data.get("reason"), 1000)
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        draft = fetch_draft(cur, draft_id)
        require_project_access(current_user, draft.get("project_name") or "")
        warnings = as_json(draft.get("warnings_json"), [])
        if reason:
            warnings.append({"type": "rejected", "message": reason})
        cur.execute(
            """
            UPDATE project_launch_drafts
            SET status='rejected', reviewed_by=%s, reviewed_at=NOW(), warnings_json=%s
            WHERE id=%s
            RETURNING *
            """,
            (current_user.get("name") or "", json_param(warnings, []), draft_id),
        )
        updated = row_to_draft(cur.fetchone())
        conn.commit()
        cur.close()
        conn.close()
        audit(current_user, "reject_project_launch_draft", draft_id, reason or "Черновик запуска отклонен", updated.get("projectName"))
        return {"ok": True, "draft": updated}

    @app.get("/project-launch/readiness")
    def get_project_launch_readiness(project_name: str, current_user: dict = Depends(read_access)):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        project = fetch_project(cur, project_name)
        require_project_access(current_user, project["name"])
        cur.execute(
            """
            SELECT
                COALESCE(SUM(CASE WHEN LOWER(COALESCE(doc_type,'')) LIKE '%%договор%%' THEN 1 ELSE 0 END),0) AS contracts,
                COUNT(*) AS documents
            FROM project_documents
            WHERE project_name=%s
            """,
            (project["name"],),
        )
        docs = cur.fetchone() or {}
        cur.execute("SELECT COUNT(*) AS count FROM estimates WHERE project_name=%s", (project["name"],))
        estimates = cur.fetchone() or {}
        cur.execute(
            """
            SELECT
                COUNT(*) AS count,
                COALESCE(SUM(CASE WHEN status='draft' THEN 1 ELSE 0 END),0) AS drafts,
                COALESCE(SUM(CASE WHEN status='rejected' THEN 1 ELSE 0 END),0) AS rejected
            FROM project_launch_drafts
            WHERE project_name=%s
            """,
            (project["name"],),
        )
        launch = cur.fetchone() or {}
        checks = [
            {"key": "client", "label": "Заказчик", "ok": bool(text(project.get("client")))},
            {"key": "budget", "label": "Стоимость договора/бюджет", "ok": float(project.get("budget") or 0) > 0},
            {"key": "deadline", "label": "Срок объекта", "ok": bool(project.get("deadline"))},
            {"key": "contract", "label": "Договор", "ok": int(docs.get("contracts") or 0) > 0},
            {"key": "estimate", "label": "Смета", "ok": int(estimates.get("count") or 0) > 0},
            {"key": "launchDraft", "label": "AI-черновик запуска", "ok": int(launch.get("count") or 0) > 0},
        ]
        missing = [item for item in checks if not item["ok"]]
        result = {
            "projectName": project["name"],
            "ready": not missing,
            "checks": checks,
            "missing": missing,
            "documentsCount": int(docs.get("documents") or 0),
            "estimatesCount": int(estimates.get("count") or 0),
            "launchDraftsCount": int(launch.get("count") or 0),
            "rejectedDraftsCount": int(launch.get("rejected") or 0),
        }
        cur.close()
        conn.close()
        return {"ok": True, "readiness": result}
