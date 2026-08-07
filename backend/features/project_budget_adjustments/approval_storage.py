"""Deterministic PostgreSQL boundaries for E6 budget approval."""

from decimal import Decimal, InvalidOperation

from .approval_errors import BudgetAdjustmentApprovalError
from .preview_storage import load_budget_adjustment_source


MAX_LOCKED_ESTIMATES = 10000
RECEIPT_SELECT = """
    SELECT id,company_id,project_id,reconciliation_id,base_estimate_id,
           next_estimate_id,project_budget_before,estimate_base_total,
           estimate_next_total,adjustment_amount,project_budget_after,
           plan_sha256,approved_by_user_id,approved_by_name,approved_by_role,
           approved_at,created_at
      FROM public.project_budget_adjustments
"""


def lock_budget_adjustment_source(
    cur,
    reconciliation_id,
    company_id,
    *,
    max_locked_estimates=MAX_LOCKED_ESTIMATES,
    source_loader=load_budget_adjustment_source,
):
    """Lock project, all project estimates by ID, then reconciliation."""

    cur.execute(
        "SELECT current_setting('transaction_isolation') AS isolation_level"
    )
    isolation = cur.fetchone()
    if not isolation or str(isolation.get("isolation_level") or "").lower() != (
        "serializable"
    ):
        raise BudgetAdjustmentApprovalError(
            "budget_adjustment_serializable_required"
        )

    cur.execute(
        """SELECT base_estimate.project_id,
                  r.base_estimate_id,r.next_estimate_id
             FROM public.estimate_reconciliations r
             JOIN public.estimates base_estimate
               ON base_estimate.id=r.base_estimate_id
             JOIN public.projects project
               ON project.id=base_estimate.project_id
              AND project.company_id=base_estimate.company_id
            WHERE r.id=%s AND project.company_id=%s
            LIMIT 1""",
        (reconciliation_id, company_id),
    )
    identity = cur.fetchone()
    if not identity:
        return None
    identity = dict(identity)
    project_id = identity.get("project_id")
    base_estimate_id = identity.get("base_estimate_id")
    next_estimate_id = identity.get("next_estimate_id")

    cur.execute(
        """SELECT id FROM public.projects
            WHERE id=%s AND company_id=%s
            FOR UPDATE""",
        (project_id, company_id),
    )
    if not cur.fetchone():
        return None

    limit = max(0, int(max_locked_estimates))
    cur.execute(
        """SELECT id FROM public.estimates
            WHERE company_id=%s AND project_id=%s
            ORDER BY id LIMIT %s FOR UPDATE""",
        (company_id, project_id, limit + 1),
    )
    estimate_rows = [dict(row or {}) for row in (cur.fetchall() or [])]
    if len(estimate_rows) > limit:
        raise BudgetAdjustmentApprovalError(
            "budget_adjustment_estimate_lock_limit_exceeded"
        )
    locked_ids = {row.get("id") for row in estimate_rows}
    if not {base_estimate_id, next_estimate_id}.issubset(locked_ids):
        raise BudgetAdjustmentApprovalError("budget_adjustment_source_drift")

    cur.execute(
        """SELECT id FROM public.estimate_reconciliations
            WHERE id=%s AND base_estimate_id=%s AND next_estimate_id=%s
            FOR UPDATE""",
        (reconciliation_id, base_estimate_id, next_estimate_id),
    )
    if not cur.fetchone():
        raise BudgetAdjustmentApprovalError("budget_adjustment_source_drift")
    return source_loader(cur, reconciliation_id, company_id)


def load_authorized_budget_actor(cur, actor, company_id):
    cur.execute(
        """SELECT users.id,users.name,actor.role
             FROM public.user_company_roles actor
             JOIN public.users users ON users.id=actor.user_id
            WHERE actor.user_id=%s AND actor.company_id=%s AND actor.role=%s
              AND actor.role IN ('директор','зам_директора')
              AND COALESCE(actor.active,TRUE)=TRUE
            ORDER BY actor.id LIMIT 2
            FOR KEY SHARE OF actor,users""",
        (actor["id"], company_id, actor["role"]),
    )
    rows = [dict(row or {}) for row in (cur.fetchall() or [])]
    if len(rows) != 1:
        return None
    row = rows[0]
    name = str(row.get("name") or "").strip()
    if row.get("id") != actor["id"] or row.get("role") != actor["role"] or not name:
        return None
    return {
        "id": actor["id"],
        "companyId": company_id,
        "name": name,
        "role": actor["role"],
    }


def load_budget_adjustment_receipt(cur, reconciliation_id, company_id):
    cur.execute(
        RECEIPT_SELECT
        + " WHERE reconciliation_id=%s AND company_id=%s LIMIT 1 FOR KEY SHARE",
        (reconciliation_id, company_id),
    )
    row = cur.fetchone()
    return dict(row) if row else None


def load_budget_adjustment_history(
    cur,
    project_id,
    company_id,
    *,
    before_id,
    limit,
):
    """Return one bounded newest-first page, or None for a foreign project."""

    cur.execute(
        """SELECT id FROM public.projects
            WHERE id=%s AND company_id=%s
            LIMIT 1""",
        (project_id, company_id),
    )
    if not cur.fetchone():
        return None
    if before_id is None:
        cur.execute(
            RECEIPT_SELECT
            + """ WHERE project_id=%s AND company_id=%s
                   ORDER BY id DESC LIMIT %s""",
            (project_id, company_id, limit),
        )
    else:
        cur.execute(
            RECEIPT_SELECT
            + """ WHERE project_id=%s AND company_id=%s AND id < %s
                   ORDER BY id DESC LIMIT %s""",
            (project_id, company_id, before_id, limit),
        )
    return [dict(row or {}) for row in (cur.fetchall() or [])]


def insert_budget_adjustment_receipt(cur, plan, actor):
    cur.execute(
        """INSERT INTO public.project_budget_adjustments
             (company_id,project_id,reconciliation_id,base_estimate_id,
              next_estimate_id,project_budget_before,estimate_base_total,
              estimate_next_total,adjustment_amount,project_budget_after,
              plan_sha256,approved_by_user_id,approved_by_name,
              approved_by_role,approved_at)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW())
           RETURNING id,company_id,project_id,reconciliation_id,
                     base_estimate_id,next_estimate_id,project_budget_before,
                     estimate_base_total,estimate_next_total,adjustment_amount,
                     project_budget_after,plan_sha256,approved_by_user_id,
                     approved_by_name,approved_by_role,approved_at,created_at""",
        (
            plan["companyId"], plan["projectId"], plan["reconciliationId"],
            plan["baseEstimateId"], plan["nextEstimateId"],
            plan["projectBudgetBefore"], plan["estimateBaseTotal"],
            plan["estimateNextTotal"], plan["adjustmentAmount"],
            plan["projectBudgetAfter"], plan["planSha256"], actor["id"],
            actor["name"], actor["role"],
        ),
    )
    row = cur.fetchone()
    return dict(row) if row else None


def update_project_budget(cur, plan):
    cur.execute(
        """UPDATE public.projects SET budget=%s
            WHERE id=%s AND company_id=%s AND budget=%s
            RETURNING budget""",
        (
            plan["projectBudgetAfter"], plan["projectId"],
            plan["companyId"], plan["projectBudgetBefore"],
        ),
    )
    row = cur.fetchone()
    if not row:
        return False
    try:
        return Decimal(str(row.get("budget"))) == Decimal(
            str(plan["projectBudgetAfter"])
        )
    except (InvalidOperation, TypeError, ValueError):
        return False


__all__ = [
    "MAX_LOCKED_ESTIMATES",
    "insert_budget_adjustment_receipt",
    "load_authorized_budget_actor",
    "load_budget_adjustment_history",
    "load_budget_adjustment_receipt",
    "lock_budget_adjustment_source",
    "update_project_budget",
]
