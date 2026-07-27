"""API error and system status routes.

Extracted verbatim from backend/main.py (Task 13): POST /client-errors
and GET /system-status keep their URLs, payload fields and owner
behavior; main.py only registers this module. Shared helpers stay in
main.py and arrive through the deps dict, ownership logic comes from
this feature's runtime module.
"""

import time

import psycopg2.extras
from fastapi import Depends, Header, HTTPException, Request
from typing import Optional

try:
    from backend.features.api_error_ownership.runtime import (
        insert_api_error,
        resolve_api_error_read_scope,
        resolve_api_error_write_owner,
        scoped_api_error_filter,
    )
except ModuleNotFoundError:
    from features.api_error_ownership.runtime import (
        insert_api_error,
        resolve_api_error_read_scope,
        resolve_api_error_write_owner,
        scoped_api_error_filter,
    )


def register_api_errors_module(app, deps):
    get_db = deps["get_db"]
    require_roles = deps["require_roles"]
    leadership_roles = tuple(deps.get("leadership_roles") or ())
    resolve_work_company_context = deps["resolve_work_company_context"]
    effective_company_actors = deps["effective_company_actors"]
    client_error_logging_enabled = deps["client_error_logging_enabled"]
    client_error_last_submit = deps["client_error_last_submit"]
    client_error_rate_limit_seconds = deps["client_error_rate_limit_seconds"]
    clip_api_error_text = deps["clip_api_error_text"]
    request_user_snapshot = deps["request_user_snapshot"]
    utc_now_iso = deps["utc_now_iso"]
    app_version = deps["app_version"]
    count_table = deps["count_table"]
    storage_backend = deps["storage_backend"]
    s3_enabled = deps["s3_enabled"]
    s3_missing_config_keys = deps["s3_missing_config_keys"]
    s3_endpoint_url = deps["s3_endpoint_url"]
    s3_bucket = deps["s3_bucket"]
    s3_public_url = deps["s3_public_url"]
    s3_prefix = deps["s3_prefix"]
    max_upload_bytes = deps["max_upload_bytes"]
    upload_dir = deps["upload_dir"]
    limited_dir_stats = deps["limited_dir_stats"]
    latest_backup_status = deps["latest_backup_status"]

    @app.post("/client-errors")
    def log_client_error(data: dict, request: Request):
        if not client_error_logging_enabled:
            return {"ok": True, "disabled": True}
        client_ip = request.client.host if request.client else ""
        path = clip_api_error_text(data.get("path") or data.get("url") or "client", 255)
        error_type = clip_api_error_text(data.get("type") or data.get("name") or "ClientError", 120)
        message = clip_api_error_text(data.get("message") or "", 450)
        stack = clip_api_error_text(data.get("stack") or "", 900)
        now = time.time()
        rate_key = "|".join([client_ip, path, error_type])
        last = client_error_last_submit.get(rate_key, 0)
        if now - last < max(1, client_error_rate_limit_seconds):
            return {"ok": True, "rateLimited": True}
        client_error_last_submit[rate_key] = now
        if len(client_error_last_submit) > 2000:
            cutoff = now - 3600
            for key, ts in list(client_error_last_submit.items())[:500]:
                if ts < cutoff:
                    client_error_last_submit.pop(key, None)
        conn = None
        cur = None
        try:
            conn = get_db()
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            user = request_user_snapshot(request, cur)
            owner = resolve_api_error_write_owner(
                cur,
                user,
                resolve_work_company_context,
                x_company_id=request.headers.get("x-company-id"),
                x_company_mode=request.headers.get("x-company-mode"),
            )
            insert_api_error(
                cur,
                method="CLIENT",
                path=path,
                status_code=499,
                error_type=error_type,
                error_message=clip_api_error_text((message + ("\n" + stack if stack else "")).strip(), 1000),
                user_id=user.get("user_id"),
                user_name=user.get("user_name") or "",
                user_role=user.get("user_role") or "",
                owner=owner,
            )
            conn.commit()
            return {"ok": True}
        except Exception as exc:
            print("CLIENT ERROR LOG ERROR:", str(exc))
            return {"ok": False, "error": exc.__class__.__name__}
        finally:
            try:
                if cur:
                    cur.close()
            except Exception:
                pass
            try:
                if conn:
                    conn.close()
            except Exception:
                pass

    @app.get("/system-status")
    def system_status(
        api_errors_since: Optional[float] = None,
        api_errors_hours: int = 24,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(require_roles(*leadership_roles, "system_owner")),
    ):
        started = time.time()
        try:
            api_errors_hours = max(1, min(int(api_errors_hours or 24), 168))
        except (TypeError, ValueError):
            api_errors_hours = 24
        if api_errors_since:
            api_errors_where = "created_at >= (to_timestamp(%s) AT TIME ZONE 'UTC')"
            api_errors_params = (api_errors_since,)
            api_errors_window = "since"
        else:
            api_errors_where = "created_at >= NOW() - (%s || ' hours')::interval"
            api_errors_params = (api_errors_hours,)
            api_errors_window = f"last_{api_errors_hours}h"
        status = {
            "ok": True,
            "service": "stroyka-backend",
            "time": utc_now_iso(),
            "version": app_version(),
            "storage": {
                "backend": storage_backend,
                "s3Configured": s3_enabled(),
                "s3Missing": s3_missing_config_keys(),
                "s3Required": storage_backend == "s3",
                "s3EndpointConfigured": bool(s3_endpoint_url),
                "s3BucketConfigured": bool(s3_bucket),
                "s3PublicUrlConfigured": bool(s3_public_url),
                "prefix": s3_prefix,
                "maxUploadMb": round(max_upload_bytes / 1024 / 1024, 1),
                "uploads": limited_dir_stats(upload_dir),
            },
            "backup": latest_backup_status(),
            "counts": {},
            "recentAudit": [],
            "apiErrors": [],
            "apiErrorsWindow": api_errors_window,
        }
        conn = None
        cur = None
        scope_cur = None
        try:
            conn = get_db()
            scope_cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            api_error_scope = resolve_api_error_read_scope(
                scope_cur,
                current_user,
                resolve_work_company_context,
                effective_company_actors,
                allowed_roles=leadership_roles,
                x_company_id=x_company_id,
                x_company_mode=x_company_mode,
            )
            scope_cur.close()
            scope_cur = None
            cur = conn.cursor()
            status["counts"]["projects"] = count_table(cur, "projects")
            status["counts"]["activeProjects"] = count_table(cur, "projects", "COALESCE(status,'') <> 'Завершён'")
            status["counts"]["users"] = count_table(cur, "users")
            status["counts"]["activeUsers"] = count_table(cur, "users", "COALESCE(active, TRUE)=TRUE")
            status["counts"]["inactiveUsers"] = count_table(cur, "users", "COALESCE(active, TRUE)=FALSE")
            status["counts"]["estimates"] = count_table(cur, "estimates")
            status["counts"]["workJournal"] = count_table(cur, "work_journal")
            status["counts"]["materials"] = count_table(cur, "materials")
            status["counts"]["warehouseMain"] = count_table(cur, "warehouse_main")
            status["counts"]["supplyRequests"] = count_table(cur, "supply_requests")
            status["counts"]["openAiTasks"] = count_table(cur, "ai_tasks", "COALESCE(status,'') NOT IN ('Закрыто','Готово','Отменено')")
            api_scope_where, api_scope_params = scoped_api_error_filter(api_error_scope)
            api_errors_count = count_table(cur, "api_errors", api_scope_where, api_scope_params)
            if api_errors_count is not None:
                status["counts"]["apiErrors"] = api_errors_count
                last_24h_where, last_24h_params = scoped_api_error_filter(
                    api_error_scope,
                    "created_at >= NOW() - INTERVAL '24 hours'",
                )
                client_last_24h_where, client_last_24h_params = scoped_api_error_filter(
                    api_error_scope,
                    "method='CLIENT' AND created_at >= NOW() - INTERVAL '24 hours'",
                )
                shown_where, shown_params = scoped_api_error_filter(
                    api_error_scope,
                    api_errors_where,
                    api_errors_params,
                )
                status["counts"]["apiErrorsLast24h"] = count_table(
                    cur, "api_errors", last_24h_where, last_24h_params
                )
                status["counts"]["clientErrorsLast24h"] = count_table(
                    cur, "api_errors", client_last_24h_where, client_last_24h_params
                )
                cur.execute("SELECT COUNT(*) FROM api_errors WHERE " + shown_where, shown_params)
                status["counts"]["apiErrorsShown"] = int((cur.fetchone() or [0])[0] or 0)
                cur.execute("""SELECT id, method, path, status_code, error_type, error_message,
                                      user_name, user_role, created_at, owner_scope, company_id, project_id
                               FROM api_errors
                               WHERE """ + shown_where + """
                               ORDER BY id DESC LIMIT 20""", shown_params)
                status["apiErrors"] = [
                    {
                        "id": r[0],
                        "method": r[1] or "",
                        "path": r[2] or "",
                        "statusCode": r[3] or 500,
                        "errorType": r[4] or "",
                        "message": r[5] or "",
                        "user": r[6] or "",
                        "role": r[7] or "",
                        "createdAt": str(r[8]) if r[8] else "",
                        "ownerScope": r[9] or "",
                        "companyId": r[10],
                        "projectId": r[11],
                    }
                    for r in cur.fetchall()
                ]
            if count_table(cur, "audit_log") is not None:
                audit_scope_where, audit_scope_params = scoped_api_error_filter(api_error_scope)
                cur.execute("""SELECT user_name, user_role, action, entity_type, description, created_at,
                                      owner_scope, company_id, project_id
                               FROM audit_log
                               WHERE """ + audit_scope_where + """
                               ORDER BY id DESC LIMIT 8""", audit_scope_params)
                status["recentAudit"] = [
                    {
                        "user": r[0] or "",
                        "role": r[1] or "",
                        "action": r[2] or "",
                        "entityType": r[3] or "",
                        "description": r[4] or "",
                        "createdAt": str(r[5]) if r[5] else "",
                        "ownerScope": r[6] or "",
                        "companyId": r[7],
                        "projectId": r[8],
                    }
                    for r in cur.fetchall()
                ]
            status["db"] = {"ok": True, "latencyMs": round((time.time() - started) * 1000, 1)}
        except HTTPException:
            raise
        except Exception as e:
            status["ok"] = False
            status["db"] = {"ok": False, "error": e.__class__.__name__}
        finally:
            try:
                if scope_cur:
                    scope_cur.close()
            except Exception:
                pass
            try:
                if cur:
                    cur.close()
            except Exception:
                pass
            try:
                if conn:
                    conn.close()
            except Exception:
                pass
        return status
