"""Tenant-bound draft/review/approval API for inert E4.2 plans."""

import re
from typing import Optional

import psycopg2
import psycopg2.extras
from fastapi import Depends, Header, HTTPException

from backend.features.estimate_row_transfer.plan import (
    PlanValidationError,
    calculate_plan_sha256,
    normalize_draft_payload,
    reviewed_plan_to_draft_payload,
)
from backend.features.estimate_row_transfer.service import build_current_plan
from backend.features.estimate_row_transfer.storage import (
    approve_plan,
    find_other_approved_plan,
    find_plan_id_by_hash,
    insert_draft,
    load_stored_plan,
)


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _positive_int(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else None


def _public_plan(stored):
    canonical = dict(stored["canonicalPlan"])
    return {
        "id": stored["id"],
        "status": stored["status"],
        **canonical,
        "approvedPlanSha256": stored.get("approvedPlanSha256"),
        "createdBy": stored.get("createdBy"),
        "approvedBy": stored.get("approvedBy"),
        "approvedAt": stored.get("approvedAt") or "",
        "createdAt": stored.get("createdAt") or "",
        "updatedAt": stored.get("updatedAt") or "",
    }


def register_estimate_row_transfer_module(app, deps):
    get_db = deps["get_db"]
    get_current_user = deps["get_current_user"]
    resolve_work_company_context = deps["resolve_work_company_context"]
    effective_company_actors = deps["effective_company_actors"]
    require_project_write_actor = deps["require_project_write_actor"]
    resolve_project_parent = deps["resolve_project_parent"]
    require_project_parent_access = deps["require_project_parent_access"]
    has_package_access = deps["has_package_access"]
    estimate_write_roles = tuple(deps["estimate_write_roles"])
    approval_roles = tuple(deps["approval_roles"])
    full_view_roles = tuple(deps["full_view_roles"])
    package_limit_roles = set(deps["package_limit_roles"])
    build_plan = deps.get("build_current_plan", build_current_plan)
    find_by_hash = deps.get("find_plan_id_by_hash", find_plan_id_by_hash)
    insert_plan = deps.get("insert_draft", insert_draft)
    load_plan = deps.get("load_stored_plan", load_stored_plan)
    approve_stored = deps.get("approve_plan", approve_plan)
    find_other_approved = deps.get("find_other_approved_plan", find_other_approved_plan)

    def open_transaction():
        conn = get_db()
        conn.set_session(autocommit=False, isolation_level="REPEATABLE READ")
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SET LOCAL lock_timeout='5s'")
        cur.execute("SET LOCAL statement_timeout='30s'")
        return conn, cur

    def selected_actor(
        cur,
        current_user,
        x_company_id,
        x_company_mode,
        roles,
        action_mode,
    ):
        context = resolve_work_company_context(
            cur,
            current_user,
            None,
            action_mode,
            x_company_id=x_company_id,
            x_company_mode=x_company_mode,
        )
        actor = require_project_write_actor(
            effective_company_actors(current_user, context),
            roles,
        )
        actor_id = _positive_int(actor.get("id"))
        company_id = _positive_int(actor.get("companyId") or actor.get("company_id"))
        name = str(actor.get("name") or "").strip()
        role = str(actor.get("role") or "").strip()
        if not actor_id or not company_id or not name or not role:
            raise HTTPException(status_code=409, detail="transfer_actor_identity_invalid")
        actor["id"] = actor_id
        actor["companyId"] = company_id
        actor["company_id"] = company_id
        actor["name"] = name
        actor["role"] = role
        return actor

    def authorize_scope(cur, actor, canonical_plan):
        company_id = _positive_int(canonical_plan.get("companyId"))
        project_id = _positive_int(canonical_plan.get("projectId"))
        if company_id != actor["companyId"]:
            raise HTTPException(status_code=403, detail="transfer_plan_company_mismatch")
        project = resolve_project_parent(cur, actor, project_id=project_id)
        require_project_parent_access(cur, actor, project, full_view_roles)
        work_package = str(canonical_plan.get("workPackage") or "").strip()
        if not work_package:
            raise HTTPException(status_code=409, detail="transfer_plan_package_invalid")
        if actor["role"] in package_limit_roles and not has_package_access(actor, work_package):
            raise HTTPException(status_code=403, detail="transfer_plan_package_forbidden")

    def require_stored_integrity(stored):
        canonical = dict((stored or {}).get("canonicalPlan") or {})
        stored_hash = canonical.get("planSha256")
        if not stored_hash or calculate_plan_sha256(canonical) != stored_hash:
            abort(409, "transfer_plan_integrity_invalid")
        if stored.get("status") == "approved" and stored.get("approvedPlanSha256") != stored_hash:
            abort(409, "transfer_plan_integrity_invalid")
        return canonical

    def abort(status_code, detail):
        raise HTTPException(status_code=status_code, detail=detail)

    @app.post("/estimate-row-transfer-plans")
    def create_transfer_plan(
        data: dict,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        try:
            payload = normalize_draft_payload(data)
        except PlanValidationError as exc:
            raise HTTPException(status_code=422, detail=exc.code)
        conn, cur = open_transaction()
        try:
            actor = selected_actor(
                cur, current_user, x_company_id, x_company_mode,
                estimate_write_roles, "write",
            )
            try:
                canonical = build_plan(cur, payload)
            except PlanValidationError as exc:
                abort(409, exc.code)
            authorize_scope(cur, actor, canonical)
            existing_id = find_by_hash(
                cur,
                canonical["companyId"],
                canonical["reconciliationId"],
                canonical["planSha256"],
            )
            if existing_id:
                stored = load_plan(cur, existing_id, actor["companyId"])
                if not stored:
                    abort(409, "transfer_plan_idempotency_conflict")
                stored_canonical = require_stored_integrity(stored)
                authorize_scope(cur, actor, stored_canonical)
                conn.rollback()
                return _public_plan(stored)
            plan_id = insert_plan(cur, canonical, actor)
            stored = load_plan(cur, plan_id, actor["companyId"])
            if not stored:
                abort(409, "transfer_plan_insert_postcheck_failed")
            if require_stored_integrity(stored) != canonical:
                abort(409, "transfer_plan_insert_postcheck_failed")
            conn.commit()
            return _public_plan(stored)
        except HTTPException:
            conn.rollback()
            raise
        except psycopg2.errors.UndefinedTable:
            conn.rollback()
            raise HTTPException(status_code=503, detail="transfer_plan_schema_not_ready")
        except psycopg2.IntegrityError:
            conn.rollback()
            raise HTTPException(status_code=409, detail="transfer_plan_write_conflict")
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()

    @app.get("/estimate-row-transfer-plans/{plan_id}")
    def get_transfer_plan(
        plan_id: int,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        if not _positive_int(plan_id):
            raise HTTPException(status_code=422, detail="transfer_plan_id_invalid")
        conn, cur = open_transaction()
        try:
            actor = selected_actor(
                cur, current_user, x_company_id, x_company_mode,
                estimate_write_roles, "read",
            )
            stored = load_plan(cur, plan_id, actor["companyId"])
            if not stored:
                abort(404, "transfer_plan_not_found")
            canonical = require_stored_integrity(stored)
            authorize_scope(cur, actor, canonical)
            conn.rollback()
            return _public_plan(stored)
        except HTTPException:
            conn.rollback()
            raise
        except psycopg2.errors.UndefinedTable:
            conn.rollback()
            raise HTTPException(status_code=503, detail="transfer_plan_schema_not_ready")
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()

    @app.post("/estimate-row-transfer-plans/{plan_id}/approval")
    def approve_transfer_plan(
        plan_id: int,
        data: dict,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        expected_hash = data.get("planSha256") if isinstance(data, dict) else None
        if (
            not _positive_int(plan_id)
            or not isinstance(data, dict)
            or set(data) != {"planSha256"}
            or not isinstance(expected_hash, str)
            or not _SHA256_RE.fullmatch(expected_hash)
        ):
            raise HTTPException(status_code=422, detail="transfer_plan_approval_invalid")
        conn, cur = open_transaction()
        try:
            actor = selected_actor(
                cur, current_user, x_company_id, x_company_mode,
                approval_roles, "approve",
            )
            stored = load_plan(cur, plan_id, actor["companyId"], for_update=True)
            if not stored:
                abort(404, "transfer_plan_not_found")
            canonical = require_stored_integrity(stored)
            authorize_scope(cur, actor, canonical)
            stored_hash = canonical.get("planSha256")
            if expected_hash != stored_hash:
                abort(409, "transfer_plan_hash_mismatch")
            if stored["status"] == "approved":
                if stored.get("approvedPlanSha256") != stored_hash:
                    abort(409, "transfer_plan_integrity_invalid")
                conn.rollback()
                return _public_plan(stored)
            if stored["status"] != "draft":
                abort(409, "transfer_plan_status_invalid")
            try:
                current = build_plan(cur, reviewed_plan_to_draft_payload(canonical))
            except PlanValidationError:
                abort(409, "transfer_plan_stale")
            if current != canonical:
                abort(409, "transfer_plan_stale")
            other_plan_id = find_other_approved(
                cur,
                company_id=actor["companyId"],
                reconciliation_id=canonical["reconciliationId"],
                plan_id=plan_id,
            )
            if other_plan_id:
                abort(409, "transfer_plan_already_approved")
            if not approve_stored(
                cur,
                plan_id=plan_id,
                company_id=actor["companyId"],
                expected_plan_sha256=expected_hash,
                actor=actor,
            ):
                abort(409, "transfer_plan_approval_conflict")
            approved = load_plan(cur, plan_id, actor["companyId"])
            if not approved or approved["status"] != "approved":
                abort(409, "transfer_plan_approval_postcheck_failed")
            conn.commit()
            return _public_plan(approved)
        except HTTPException:
            conn.rollback()
            raise
        except psycopg2.errors.UndefinedTable:
            conn.rollback()
            raise HTTPException(status_code=503, detail="transfer_plan_schema_not_ready")
        except psycopg2.IntegrityError:
            conn.rollback()
            raise HTTPException(status_code=409, detail="transfer_plan_approval_conflict")
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()
