"""Authenticated HTTP boundaries for E6 approval and immutable history."""

from typing import Optional

import psycopg2
import psycopg2.extras
from fastapi import Depends, Header, HTTPException, Query

from .approval import public_budget_adjustment_receipt
from .approval_storage import load_budget_adjustment_history
from .preview_routes import selected_budget_leader


MAX_HISTORY_PAGE_SIZE = 100


def _positive_int(value):
    return (
        value
        if isinstance(value, int) and not isinstance(value, bool) and value > 0
        else None
    )


def register_project_budget_adjustment_runtime_module(app, deps):
    get_db = deps["get_db"]
    get_current_user = deps["get_current_user"]
    resolve_work_company_context = deps["resolve_work_company_context"]
    effective_company_actors = deps["effective_company_actors"]
    leadership_roles = tuple(deps["leadership_roles"])
    load_history = deps.get(
        "load_budget_adjustment_history",
        load_budget_adjustment_history,
    )

    @app.get("/projects/{project_id}/budget-adjustments")
    def get_project_budget_adjustments(
        project_id: int,
        limit: int = Query(default=50, ge=1, le=MAX_HISTORY_PAGE_SIZE),
        before_id: Optional[int] = Query(
            default=None,
            ge=1,
            alias="beforeId",
        ),
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(
            default=None,
            alias="X-Company-Mode",
        ),
        current_user: dict = Depends(get_current_user),
    ):
        page_size = _positive_int(limit)
        if (
            _positive_int(project_id) is None
            or page_size is None
            or page_size > MAX_HISTORY_PAGE_SIZE
            or (before_id is not None and _positive_int(before_id) is None)
        ):
            raise HTTPException(
                status_code=422,
                detail="budget_adjustment_history_query_invalid",
            )
        conn = get_db()
        cur = None
        try:
            conn.set_session(
                readonly=True,
                autocommit=False,
                isolation_level="REPEATABLE READ",
            )
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute("SET LOCAL lock_timeout='5s'")
            cur.execute("SET LOCAL statement_timeout='30s'")
            context = resolve_work_company_context(
                cur,
                current_user,
                None,
                "read",
                x_company_id=x_company_id,
                x_company_mode=x_company_mode,
            )
            actor = selected_budget_leader(
                effective_company_actors(current_user, context),
                leadership_roles,
            )
            stored = load_history(
                cur,
                project_id,
                actor["companyId"],
                before_id=before_id,
                limit=page_size + 1,
            )
            if stored is None:
                raise HTTPException(
                    status_code=404,
                    detail="budget_adjustment_project_not_found",
                )
            page = stored[:page_size]
            items = [
                public_budget_adjustment_receipt(row)
                for row in page
            ]
            next_before_id = (
                items[-1]["id"] if len(stored) > page_size and items else None
            )
            conn.rollback()
            return {
                "projectId": project_id,
                "items": items,
                "nextBeforeId": next_before_id,
            }
        except HTTPException:
            conn.rollback()
            raise
        except (psycopg2.errors.UndefinedTable, psycopg2.errors.UndefinedColumn):
            conn.rollback()
            raise HTTPException(
                status_code=503,
                detail="budget_adjustment_schema_not_ready",
            )
        except Exception:
            conn.rollback()
            raise
        finally:
            if cur is not None:
                cur.close()
            conn.close()


__all__ = ["register_project_budget_adjustment_runtime_module"]
