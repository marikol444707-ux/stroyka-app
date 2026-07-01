import json

import psycopg2.extras
from fastapi import HTTPException


DRAFT_STATUSES = {"draft", "reviewed", "applied", "rejected"}


def text(value, limit=500):
    return str(value or "").strip()[:limit]


def as_json(value, fallback):
    if value is None or value == "":
        return fallback
    if isinstance(value, (dict, list)):
        return value
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, type(fallback)) else fallback
    except Exception:
        return fallback


def json_param(value, fallback):
    return psycopg2.extras.Json(as_json(value, fallback))


def normalized_status(value, fallback="draft"):
    raw = text(value, 40) or fallback
    if raw not in DRAFT_STATUSES:
        raise HTTPException(status_code=400, detail="Недопустимый статус черновика запуска")
    return raw


def row_to_draft(row):
    item = dict(row or {})
    for key, fallback in (
        ("extracted_json", {}),
        ("project_patch_json", {}),
        ("counterparty_json", {}),
        ("contract_terms_json", {}),
        ("estimate_draft_json", {}),
        ("findings_json", []),
        ("tasks_json", []),
        ("warnings_json", []),
    ):
        item[key] = as_json(item.get(key), fallback)
    item["projectId"] = item.pop("project_id", None)
    item["projectName"] = item.pop("project_name", "") or ""
    item["companyId"] = item.pop("company_id", None)
    item["sourceDocumentId"] = item.pop("source_document_id", None)
    item["sourceFileUrl"] = item.pop("source_file_url", "") or ""
    item["sourceFileName"] = item.pop("source_file_name", "") or ""
    item["sourceFileType"] = item.pop("source_file_type", "") or ""
    item["extracted"] = item.pop("extracted_json", {})
    item["projectPatch"] = item.pop("project_patch_json", {})
    item["counterparty"] = item.pop("counterparty_json", {})
    item["contractTerms"] = item.pop("contract_terms_json", {})
    item["estimateDraft"] = item.pop("estimate_draft_json", {})
    item["findings"] = item.pop("findings_json", [])
    item["tasks"] = item.pop("tasks_json", [])
    item["warnings"] = item.pop("warnings_json", [])
    item["createdBy"] = item.pop("created_by", "") or ""
    item["createdById"] = item.pop("created_by_id", None)
    item["createdAt"] = str(item.pop("created_at", "") or "")
    item["reviewedBy"] = item.pop("reviewed_by", "") or ""
    item["reviewedAt"] = str(item.pop("reviewed_at", "") or "")
    item["appliedAt"] = str(item.pop("applied_at", "") or "")
    if item.get("confidence") is not None:
        item["confidence"] = float(item.get("confidence") or 0)
    return item


def fetch_project(cur, project_name):
    name = text(project_name, 500)
    if not name:
        raise HTTPException(status_code=400, detail="Не указан объект")
    cur.execute("SELECT id, name, company_id, client, budget, deadline FROM projects WHERE name=%s", (name,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Объект не найден")
    return dict(row)


def fetch_draft(cur, draft_id):
    cur.execute("SELECT * FROM project_launch_drafts WHERE id=%s", (draft_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Черновик запуска не найден")
    return dict(row)


def document_belongs_to_project(cur, document_id, project_name):
    if not document_id:
        return
    cur.execute("SELECT project_name FROM project_documents WHERE id=%s", (document_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Документ объекта не найден")
    document_project = row.get("project_name") if isinstance(row, dict) else row[0]
    if (document_project or "") != (project_name or ""):
        raise HTTPException(status_code=400, detail="Документ относится к другому объекту")
