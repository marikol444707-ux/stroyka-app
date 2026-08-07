"""Bounded tenant-scoped reads for the E6 budget-adjustment preview."""


def load_budget_adjustment_source(cur, reconciliation_id, company_id):
    """Load one source graph; caller validates every returned invariant."""

    cur.execute(
        """
        SELECT
          r.id AS reconciliation_id,
          r.base_estimate_id,
          r.next_estimate_id,
          r.status AS reconciliation_status,
          r.smeta_type AS reconciliation_type,
          r.work_package AS reconciliation_package,
          r.base_total AS reconciliation_base_total,
          r.next_total AS reconciliation_next_total,
          project.id AS project_id,
          project.company_id,
          project.budget AS project_budget,
          base_estimate.id AS stored_base_estimate_id,
          base_estimate.company_id AS base_company_id,
          base_estimate.project_id AS base_project_id,
          base_estimate.status AS base_status,
          base_estimate.smeta_type AS base_type,
          base_estimate.work_package AS base_package,
          base_estimate.total AS base_stored_total,
          base_estimate.sections_json AS base_sections_json,
          next_estimate.id AS stored_next_estimate_id,
          next_estimate.company_id AS next_company_id,
          next_estimate.project_id AS next_project_id,
          next_estimate.status AS next_status,
          next_estimate.smeta_type AS next_type,
          next_estimate.work_package AS next_package,
          next_estimate.total AS next_stored_total,
          next_estimate.sections_json AS next_sections_json,
          receipt.id AS existing_adjustment_id,
          (
            SELECT COUNT(*)
              FROM public.estimates active_estimate
             WHERE active_estimate.company_id=project.company_id
               AND active_estimate.project_id=project.id
               AND COALESCE(NULLIF(active_estimate.smeta_type,''),'Заказчик')
                   =COALESCE(NULLIF(r.smeta_type,''),'Заказчик')
               AND COALESCE(NULLIF(active_estimate.work_package,''),'Основная')
                   =COALESCE(NULLIF(r.work_package,''),'Основная')
               AND active_estimate.status='Активная'
          ) AS active_scope_count
          FROM public.estimate_reconciliations r
          JOIN public.estimates base_estimate
            ON base_estimate.id=r.base_estimate_id
          JOIN public.estimates next_estimate
            ON next_estimate.id=r.next_estimate_id
          JOIN public.projects project
            ON project.id=base_estimate.project_id
           AND project.company_id=base_estimate.company_id
          LEFT JOIN public.project_budget_adjustments receipt
            ON receipt.reconciliation_id=r.id
         WHERE r.id=%s AND project.company_id=%s
         LIMIT 1
        """,
        (reconciliation_id, company_id),
    )
    row = cur.fetchone()
    return dict(row) if row else None


__all__ = ["load_budget_adjustment_source"]
