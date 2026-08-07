"""Authenticated read-only HTTP boundary for the E6 adjustment preview."""

from typing import Optional

import psycopg2
import psycopg2.extras
from fastapi import Depends, Header, HTTPException

from .preview import BudgetAdjustmentPreviewError
from .preview_service import build_budget_adjustment_preview


def _positive_int(value):
    return (
        value
        if isinstance(value, int) and not isinstance(value, bool) and value > 0
        else None
    )


def _selected_leader(actors, leadership_roles):
    candidates = [dict(actor or {}) for actor in (actors or [])]
    if len(candidates) != 1:
        raise HTTPException(
            status_code=409,
            detail="budget_adjustment_company_context_ambiguous",
        )
    actor = candidates[0]
    actor_id = _positive_int(actor.get("id") or actor.get("userId"))
    company_id = _positive_int(actor.get("companyId") or actor.get("company_id"))
    role = str(actor.get("role") or "").strip()
    if not actor_id or not company_id or not role:
        raise HTTPException(
            status_code=409,
            detail="budget_adjustment_actor_identity_invalid",
        )
    if role not in set(leadership_roles or ()):
        raise HTTPException(
            status_code=403,
            detail="budget_adjustment_role_forbidden",
        )
    actor.update({
        "id": actor_id,
        "companyId": company_id,
        "company_id": company_id,
        "role": role,
    })
    return actor


def register_project_budget_adjustment_preview_module(app, deps):
    get_db = deps["get_db"]
    get_current_user = deps["get_current_user"]
    resolve_work_company_context = deps["resolve_work_company_context"]
    effective_company_actors = deps["effective_company_actors"]
    leadership_roles = tuple(deps["leadership_roles"])
    build_preview = deps.get(
        "build_budget_adjustment_preview",
        build_budget_adjustment_preview,
    )

    @app.get(
        "/estimate-reconciliations/{reconciliation_id}/budget-adjustment-preview"
    )
    def get_budget_adjustment_preview(
        reconciliation_id: int,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(
            default=None,
            alias="X-Company-Mode",
        ),
        current_user: dict = Depends(get_current_user),
    ):
        if not _positive_int(reconciliation_id):
            raise HTTPException(
                status_code=422,
                detail="budget_adjustment_identity_invalid",
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
            actor = _selected_leader(
                effective_company_actors(current_user, context),
                leadership_roles,
            )
            preview = build_preview(
                cur,
                reconciliation_id,
                actor["companyId"],
            )
            conn.rollback()
            return preview
        except BudgetAdjustmentPreviewError as exc:
            conn.rollback()
            raise HTTPException(
                status_code=(404 if exc.code == "budget_adjustment_not_found" else 409),
                detail=exc.code,
            )
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


__all__ = ["register_project_budget_adjustment_preview_module"]
