"""Bounded assistant SELECTs using the existing resolved company memberships."""

from ..company_context.service import company_id_scope_filter, effective_company_actors
from ..project_access.service import project_visibility_filter
from ..project_payment_access.service import project_payment_visibility_filter
from .chat import bounded_company_data

FULL_VIEW_ROLES = ("директор", "зам_директора", "бухгалтер", "главный_инженер", "сметчик")


def load_company_data(cur, current_user, company_context, *, warehouse_roles, finance_roles):
    actors = effective_company_actors(current_user, company_context)
    project_sql, project_params = project_visibility_filter(actors, FULL_VIEW_ROLES)
    rows = {}
    cur.execute(
        "SELECT p.name,p.status,p.company_id FROM projects p WHERE " + project_sql
        + " ORDER BY p.company_id,p.id LIMIT 30", tuple(project_params),
    )
    rows["projects_name_status_company"] = cur.fetchall()

    warehouse_actors = [a for a in actors if a["role"] in (*warehouse_roles, *finance_roles)]
    warehouse_context = {"mode": "all_companies", "companyIds": [a["companyId"] for a in warehouse_actors]}
    warehouse_visibility_sql, warehouse_visibility_params = company_id_scope_filter(warehouse_context)
    cur.execute(
        "SELECT name,quantity,unit,company_id FROM warehouse_main WHERE TRUE"
        + warehouse_visibility_sql + " ORDER BY company_id,id LIMIT 20",
        tuple(warehouse_visibility_params),
    )
    rows["warehouse_name_quantity_unit_company"] = cur.fetchall()

    staff_companies = [a["companyId"] for a in actors if a["role"] in FULL_VIEW_ROLES]
    if staff_companies:
        cur.execute(
            """SELECT u.name,m.role,m.company_id FROM user_company_roles m
               JOIN users u ON u.id=m.user_id
               WHERE m.company_id = ANY(%s) AND m.active=TRUE AND u.active=TRUE
                 AND m.role NOT IN ('заказчик','поставщик')
               ORDER BY m.company_id,u.id LIMIT 15""", (staff_companies,),
        )
        rows["staff_name_role_company"] = cur.fetchall()
    else:
        rows["staff_name_role_company"] = [(current_user.get("name", ""), a["role"], a["companyId"]) for a in actors][:15]

    # Materials have a legacy project-name reference: require the same company,
    # never join another tenant's identically named project.
    cur.execute(
        """SELECT mat.name,mat.quantity,mat.unit,mat.project,mat.company_id FROM materials mat
           WHERE mat.quantity > 0 AND EXISTS (
             SELECT 1 FROM projects p WHERE p.company_id=mat.company_id AND p.name=mat.project
             AND """ + project_sql + ") ORDER BY mat.company_id,mat.project,mat.id LIMIT 20",
        tuple(project_params),
    )
    rows["materials_name_quantity_unit_project_company"] = cur.fetchall()
    cur.execute(
        """SELECT bc.project_name,bc.brigade_name,bc.status,bc.company_id FROM brigade_contracts bc
           WHERE EXISTS (
             SELECT 1 FROM projects p WHERE p.company_id=bc.company_id AND p.name=bc.project_name
             AND (bc.project_id IS NULL OR bc.project_id=p.id) AND """ + project_sql
        + ") ORDER BY bc.company_id,bc.id LIMIT 10", tuple(project_params),
    )
    rows["brigades_project_name_status_company"] = cur.fetchall()

    finance_actors = [a for a in actors if a["role"] in finance_roles]
    payment_sql, payment_params = project_payment_visibility_filter(finance_actors, finance_roles)
    rows["payments_project_amount_note_company"] = []
    if payment_sql != "FALSE":
        cur.execute("SELECT to_regclass('public.supplier_payment_operations') IS NOT NULL")
        exclusion = (
            "AND NOT EXISTS (SELECT 1 FROM public.supplier_payment_operations ledger "
            "WHERE ledger.project_payment_id=pp.id)"
        ) if cur.fetchone()[0] else ""
        cur.execute(
            "SELECT pp.project_name,pp.amount,pp.note,pp.company_id FROM project_payments pp WHERE ("
            + payment_sql + ") " + exclusion + " ORDER BY pp.id DESC LIMIT 10", tuple(payment_params),
        )
        rows["payments_project_amount_note_company"] = cur.fetchall()
    rows["limitations"] = [("Ограниченная выборка, не полная сводка. Платежи поставщикам и их сторно исключены.",)]
    return bounded_company_data(rows)
