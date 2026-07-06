import datetime as dt
import json
import urllib.parse

import psycopg2.extras
from fastapi import Depends, HTTPException, Query

from .schema import ensure_marketing_schema


PUBLIC_STATUSES = {"В очереди", "Опубликовано"}


def _text(value, limit=255):
    return str(value or "").strip()[:limit]


def _bool_value(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "да", "on")


def _int_or_none(value):
    try:
        number = int(value)
        return number if number > 0 else None
    except Exception:
        return None


def _json_dict(value):
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    try:
        parsed = json.loads(value) if isinstance(value, str) else value
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


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


def _channel_ids(value):
    result = []
    for raw in _json_list(value):
        number = _int_or_none(raw)
        if number and number not in result:
            result.append(number)
    return result[:50]


def _iso_value(value):
    if isinstance(value, (dt.datetime, dt.date)):
        return value.isoformat()
    return str(value) if value else ""


def _public_publication(row: dict) -> dict:
    row = row or {}
    return {
        "id": row.get("id"),
        "title": row.get("title") or "",
        "body": row.get("body") or "",
        "status": row.get("status") or "Черновик",
        "projectId": row.get("project_id"),
        "projectName": row.get("project_name") or "",
        "publicationUrl": row.get("publication_url") or "",
        "targetSite": bool(row.get("target_site")),
        "targetMax": bool(row.get("target_max")),
        "channelIds": _channel_ids(row.get("channel_ids")),
        "utmCampaign": row.get("utm_campaign") or "",
        "scheduledAt": _iso_value(row.get("scheduled_at")),
        "queuedAt": _iso_value(row.get("queued_at")),
        "publishedAt": _iso_value(row.get("published_at")),
        "createdBy": row.get("created_by") or "",
        "updatedBy": row.get("updated_by") or "",
        "metadata": _json_dict(row.get("metadata_json")),
        "createdAt": _iso_value(row.get("created_at")),
        "updatedAt": _iso_value(row.get("updated_at")),
    }


def _publication_payload(data: dict, existing: dict = None) -> dict:
    data = data or {}
    existing = existing or {}
    title = _text(data.get("title") if "title" in data else existing.get("title"), 255)
    if not title:
        raise HTTPException(status_code=400, detail="Укажите заголовок публикации")
    body = str(data.get("body") if "body" in data else existing.get("body") or "").strip()[:6000]
    status = _text(data.get("status") if "status" in data else existing.get("status") or "Черновик", 80)
    project_id = _int_or_none(data.get("projectId") if "projectId" in data else data.get("project_id") if "project_id" in data else existing.get("project_id"))
    return {
        "title": title,
        "body": body,
        "status": status or "Черновик",
        "projectId": project_id,
        "projectName": _text(
            data.get("projectName") if "projectName" in data else data.get("project_name") if "project_name" in data else existing.get("project_name"),
            500,
        ),
        "publicationUrl": _text(
            data.get("publicationUrl") if "publicationUrl" in data else data.get("publication_url") if "publication_url" in data else existing.get("publication_url"),
            1000,
        ),
        "targetSite": _bool_value(data.get("targetSite") if "targetSite" in data else data.get("target_site"), bool(existing.get("target_site", True))),
        "targetMax": _bool_value(data.get("targetMax") if "targetMax" in data else data.get("target_max"), bool(existing.get("target_max", False))),
        "channelIds": _channel_ids(data.get("channelIds") if "channelIds" in data else data.get("channel_ids") if "channel_ids" in data else existing.get("channel_ids")),
        "utmCampaign": _text(
            data.get("utmCampaign") if "utmCampaign" in data else data.get("utm_campaign") if "utm_campaign" in data else existing.get("utm_campaign"),
            160,
        ),
        "scheduledAt": data.get("scheduledAt") if "scheduledAt" in data else data.get("scheduled_at") if "scheduled_at" in data else existing.get("scheduled_at"),
        "metadata": _json_dict(
            data.get("metadata")
            if "metadata" in data
            else data.get("metadata_json")
            if "metadata_json" in data
            else existing.get("metadata_json")
        ),
    }


def _with_utm(url: str, campaign: str, source: str = "max", medium: str = "messenger") -> str:
    clean_url = _text(url, 1000) or "https://stroyka26.pro/"
    campaign = _text(campaign, 160)
    if not campaign:
        return clean_url
    parsed = urllib.parse.urlsplit(clean_url)
    query = dict(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))
    query.setdefault("utm_source", source)
    query.setdefault("utm_medium", medium)
    query.setdefault("utm_campaign", campaign)
    next_query = urllib.parse.urlencode(query)
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, next_query, parsed.fragment))


def register_marketing_module(app, deps):
    get_db = deps["get_db"]
    require_roles = deps["require_roles"]
    leadership_roles = deps["leadership_roles"]
    log_audit = deps.get("log_audit")
    app_public_url = (deps.get("app_public_url") or "https://stroyka26.pro").rstrip("/")

    ensure_marketing_schema(get_db)

    marketing_access = require_roles(*leadership_roles, "менеджер_crm")

    def default_publication_url(project_id: int = None) -> str:
        if project_id:
            return f"{app_public_url}/?project={project_id}#projects"
        return f"{app_public_url}/#request"

    def fetch_publication(cur, publication_id: int):
        cur.execute("SELECT * FROM marketing_publications WHERE id=%s", (publication_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Публикация не найдена")
        return row

    def resolve_project(cur, project_id: int, fallback_name: str = "") -> tuple[int | None, str]:
        if not project_id:
            return None, _text(fallback_name, 500)
        cur.execute("SELECT id,name FROM projects WHERE id=%s AND COALESCE(archived,FALSE)=FALSE", (project_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Объект для публикации не найден")
        return row.get("id"), row.get("name") or ""

    def fetch_marketing_channels(cur, ids: list[int]) -> list[dict]:
        if not ids:
            return []
        cur.execute(
            """
            SELECT *
              FROM messenger_channels
             WHERE provider='max'
               AND channel_type='marketing'
               AND COALESCE(enabled,TRUE)=TRUE
               AND id = ANY(%s)
             ORDER BY id
            """,
            (ids,),
        )
        rows = cur.fetchall()
        found = {int(row.get("id")) for row in rows}
        missing = [value for value in ids if value not in found]
        if missing:
            raise HTTPException(status_code=400, detail="Некоторые MAX-каналы не найдены или отключены")
        return rows

    @app.get("/site/publications")
    def list_site_publications(limit: int = Query(default=20, ge=1, le=100)):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            cur.execute(
                """
                SELECT *
                  FROM marketing_publications
                 WHERE target_site=TRUE
                   AND status = ANY(%s)
                 ORDER BY COALESCE(published_at, queued_at, updated_at, created_at) DESC, id DESC
                 LIMIT %s
                """,
                (list(PUBLIC_STATUSES), limit),
            )
            return [_public_publication(row) for row in cur.fetchall()]
        finally:
            cur.close()
            conn.close()

    @app.get("/marketing-publications")
    def list_marketing_publications(
        status: str = Query(default=""),
        limit: int = Query(default=100, ge=1, le=500),
        _current_user: dict = Depends(marketing_access),
    ):
        status = _text(status, 80)
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            if status:
                cur.execute(
                    """
                    SELECT *
                      FROM marketing_publications
                     WHERE status=%s
                     ORDER BY id DESC
                     LIMIT %s
                    """,
                    (status, limit),
                )
            else:
                cur.execute(
                    """
                    SELECT *
                      FROM marketing_publications
                     ORDER BY id DESC
                     LIMIT %s
                    """,
                    (limit,),
                )
            return {"ok": True, "items": [_public_publication(row) for row in cur.fetchall()]}
        finally:
            cur.close()
            conn.close()

    @app.post("/marketing-publications")
    def create_marketing_publication(data: dict, current_user: dict = Depends(marketing_access)):
        payload = _publication_payload(data or {})
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            project_id, project_name = resolve_project(cur, payload["projectId"], payload["projectName"])
            publication_url = payload["publicationUrl"] or default_publication_url(project_id)
            cur.execute(
                """
                INSERT INTO marketing_publications
                    (title,body,status,project_id,project_name,publication_url,target_site,target_max,
                     channel_ids,utm_campaign,scheduled_at,created_by,updated_by,metadata_json)
                VALUES
                    (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s::jsonb)
                RETURNING *
                """,
                (
                    payload["title"],
                    payload["body"],
                    payload["status"],
                    project_id,
                    project_name,
                    publication_url,
                    payload["targetSite"],
                    payload["targetMax"],
                    json.dumps(payload["channelIds"], ensure_ascii=False),
                    payload["utmCampaign"],
                    payload["scheduledAt"] or None,
                    current_user.get("name") or "",
                    current_user.get("name") or "",
                    json.dumps(payload["metadata"], ensure_ascii=False),
                ),
            )
            row = cur.fetchone()
            conn.commit()
            if log_audit:
                log_audit(current_user.get("name", ""), current_user.get("role", ""), "create", "marketing_publication", row["id"], "Создана маркетинговая публикация", project_name)
            return {"ok": True, "publication": _public_publication(row)}
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()

    @app.put("/marketing-publications/{publication_id}")
    def update_marketing_publication(publication_id: int, data: dict, current_user: dict = Depends(marketing_access)):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            existing = fetch_publication(cur, publication_id)
            payload = _publication_payload(data or {}, existing)
            project_id, project_name = resolve_project(cur, payload["projectId"], payload["projectName"])
            publication_url = payload["publicationUrl"] or default_publication_url(project_id)
            cur.execute(
                """
                UPDATE marketing_publications
                   SET title=%s,
                       body=%s,
                       status=%s,
                       project_id=%s,
                       project_name=%s,
                       publication_url=%s,
                       target_site=%s,
                       target_max=%s,
                       channel_ids=%s::jsonb,
                       utm_campaign=%s,
                       scheduled_at=%s,
                       updated_by=%s,
                       metadata_json=%s::jsonb,
                       updated_at=NOW()
                 WHERE id=%s
             RETURNING *
                """,
                (
                    payload["title"],
                    payload["body"],
                    payload["status"],
                    project_id,
                    project_name,
                    publication_url,
                    payload["targetSite"],
                    payload["targetMax"],
                    json.dumps(payload["channelIds"], ensure_ascii=False),
                    payload["utmCampaign"],
                    payload["scheduledAt"] or None,
                    current_user.get("name") or "",
                    json.dumps(payload["metadata"], ensure_ascii=False),
                    publication_id,
                ),
            )
            row = cur.fetchone()
            conn.commit()
            if log_audit:
                log_audit(current_user.get("name", ""), current_user.get("role", ""), "update", "marketing_publication", publication_id, "Обновлена маркетинговая публикация", project_name)
            return {"ok": True, "publication": _public_publication(row)}
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()

    @app.post("/marketing-publications/{publication_id}/publish")
    def publish_marketing_publication(publication_id: int, data: dict = None, current_user: dict = Depends(marketing_access)):
        data = data or {}
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            publication = fetch_publication(cur, publication_id)
            channel_ids = _channel_ids(data.get("channelIds") or data.get("channel_ids") or publication.get("channel_ids"))
            should_publish_max = _bool_value(data.get("targetMax"), bool(publication.get("target_max")))
            should_publish_site = _bool_value(data.get("targetSite"), bool(publication.get("target_site")))
            channels = fetch_marketing_channels(cur, channel_ids) if should_publish_max else []
            if should_publish_max and not channels:
                raise HTTPException(status_code=400, detail="Выберите маркетинговый MAX-канал")
            utm_campaign = _text(data.get("utmCampaign") or publication.get("utm_campaign") or f"publication-{publication_id}", 160)
            public_url = _with_utm(publication.get("publication_url") or default_publication_url(publication.get("project_id")), utm_campaign)
            outbox_ids = []
            for channel in channels:
                payload = {
                    "publicationId": publication_id,
                    "publicationUrl": public_url,
                    "utmCampaign": utm_campaign,
                    "channelId": channel.get("id"),
                    "channelTitle": channel.get("title") or "",
                    "projectId": publication.get("project_id"),
                    "projectName": publication.get("project_name") or "",
                }
                actions = [
                    {
                        "id": "openPublication",
                        "label": "Открыть",
                        "kind": "open_url",
                        "url": public_url,
                    }
                ]
                cur.execute(
                    """
                    INSERT INTO messenger_outbox
                        (provider,chat_id,event_type,entity_type,entity_id,title,body,payload_json,actions_json,status,priority)
                    VALUES
                        ('max',%s,'marketing_publication','marketing_publication',%s,%s,%s,%s::jsonb,%s::jsonb,'queued',6)
                    RETURNING id
                    """,
                    (
                        channel.get("chat_id") or "",
                        publication_id,
                        publication.get("title") or "",
                        publication.get("body") or "",
                        json.dumps(payload, ensure_ascii=False),
                        json.dumps(actions, ensure_ascii=False),
                    ),
                )
                outbox_ids.append(cur.fetchone()["id"])

            metadata = _json_dict(publication.get("metadata_json"))
            metadata["lastPublish"] = {
                "outboxIds": outbox_ids,
                "targetSite": should_publish_site,
                "targetMax": should_publish_max,
                "utmCampaign": utm_campaign,
                "publicationUrl": public_url,
                "publishedBy": current_user.get("name") or "",
                "publishedAt": dt.datetime.utcnow().isoformat() + "Z",
            }
            next_status = "В очереди" if outbox_ids else "Опубликовано"
            cur.execute(
                """
                UPDATE marketing_publications
                   SET status=%s,
                       target_site=%s,
                       target_max=%s,
                       channel_ids=%s::jsonb,
                       publication_url=%s,
                       utm_campaign=%s,
                       queued_at=CASE WHEN %s THEN NOW() ELSE queued_at END,
                       published_at=CASE WHEN %s THEN NOW() ELSE published_at END,
                       updated_by=%s,
                       metadata_json=%s::jsonb,
                       updated_at=NOW()
                 WHERE id=%s
             RETURNING *
                """,
                (
                    next_status,
                    should_publish_site,
                    should_publish_max,
                    json.dumps(channel_ids, ensure_ascii=False),
                    public_url,
                    utm_campaign,
                    bool(outbox_ids),
                    not bool(outbox_ids),
                    current_user.get("name") or "",
                    json.dumps(metadata, ensure_ascii=False),
                    publication_id,
                ),
            )
            row = cur.fetchone()
            conn.commit()
            if log_audit:
                log_audit(current_user.get("name", ""), current_user.get("role", ""), "publish", "marketing_publication", publication_id, "Публикация поставлена в маркетинговые каналы", publication.get("project_name") or "")
            return {"ok": True, "publication": _public_publication(row), "outboxIds": outbox_ids}
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()
