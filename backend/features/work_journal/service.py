from fastapi import HTTPException

from ..project_access.service import project_visibility_filter


def _positive_int(value):
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def resolve_work_journal_create_scope(
    cur,
    current_user,
    project_name,
    *,
    x_company_id,
    x_company_mode,
    deps,
):
    context = deps["resolve_work_company_context"](
        cur,
        current_user,
        None,
        "create",
        x_company_id=x_company_id,
        x_company_mode=x_company_mode,
    )
    actor = deps["require_project_write_actor"](
        deps["effective_company_actors"](current_user, context),
        deps["journal_write_roles"],
    )
    project = deps["resolve_project_parent"](
        cur,
        actor,
        project_name=str(project_name or "").strip(),
    )
    deps["require_project_parent_access"](
        cur,
        actor,
        project,
        deps["full_view_roles"],
    )
    company_id = _positive_int(project.get("companyId") or project.get("company_id"))
    project_id = _positive_int(project.get("id"))
    canonical_name = str(project.get("name") or "").strip()
    if not company_id or not project_id or not canonical_name:
        raise HTTPException(status_code=409, detail="Объект не имеет точного владельца")
    return actor, {
        "id": project_id,
        "companyId": company_id,
        "name": canonical_name,
    }


def require_work_journal_parent_owner(parent, project, label):
    if (
        _positive_int((parent or {}).get("companyId") or (parent or {}).get("company_id"))
        != _positive_int((project or {}).get("companyId") or (project or {}).get("company_id"))
        or _positive_int((parent or {}).get("projectId") or (parent or {}).get("project_id"))
        != _positive_int((project or {}).get("id"))
    ):
        raise HTTPException(
            status_code=409,
            detail=label + " относится к другой компании или объекту",
        )


def _values(actor, camel_key, snake_key):
    value = (actor or {}).get(camel_key, (actor or {}).get(snake_key, []))
    if isinstance(value, str):
        try:
            import json
            value = json.loads(value)
        except (TypeError, ValueError):
            value = []
    return sorted({str(item).strip() for item in (value or []) if str(item or "").strip()})


def work_journal_visibility_filter(
    company_actors,
    *,
    full_view_roles,
    scoped_roles,
    worker_roles,
    customer_roles,
    package_limit_roles,
):
    full_roles = set(full_view_roles)
    scoped = set(scoped_roles)
    workers = set(worker_roles)
    customers = set(customer_roles)
    package_roles = set(package_limit_roles)
    clauses, params, visible_actors = [], [], []
    for source_actor in company_actors or []:
        actor = dict(source_actor or {})
        company_id = _positive_int(actor.get("companyId") or actor.get("company_id"))
        role = str(actor.get("role") or "").strip()
        if not company_id or role not in full_roles | scoped | workers | customers:
            continue
        actor["companyId"] = company_id
        actor["role"] = role
        actor_clauses = ["wj.company_id=%s"]
        actor_params = [company_id]
        if role in scoped | customers:
            project_sql, project_params = project_visibility_filter(
                [actor],
                full_view_roles,
                column_prefix="p",
            )
            if project_sql == "FALSE":
                continue
            actor_clauses.append(project_sql)
            actor_params.extend(project_params)
        if role in workers:
            actor_clauses.append(
                "(COALESCE(wj.master_id,0)=%s OR "
                "(COALESCE(wj.master_id,0)=0 AND LOWER(TRIM(wj.master_name))=LOWER(TRIM(%s))))"
            )
            actor_params.extend([actor.get("id"), actor.get("name") or ""])
        if role in package_roles and role != "прораб":
            packages = _values(actor, "assignedPackages", "assigned_packages")
            if not packages:
                continue
            actor_clauses.append("COALESCE(NULLIF(wj.work_package,''),'Основная') = ANY(%s)")
            actor_params.append(packages)
        if role in customers:
            actor_clauses.append("wj.status='Подтверждено'")
        clauses.append("(" + " AND ".join(actor_clauses) + ")")
        params.extend(actor_params)
        visible_actors.append(actor)
    if not clauses:
        return "FALSE", [], []
    return "(" + " OR ".join(clauses) + ")", params, visible_actors


def mask_work_journal_money(row, actor, worker_roles):
    item = dict(row or {})
    role = str((actor or {}).get("role") or "")
    if role in ("заказчик", "технадзор", "стройконтроль"):
        for key in (
            "pricePerUnit", "total", "executionPricePerUnit", "executionTotal",
            "customerPricePerUnit", "customerTotal",
        ):
            item[key] = 0
    elif role in set(worker_roles):
        item["customerPricePerUnit"] = 0
        item["customerTotal"] = 0
        item["pricePerUnit"] = item.get("executionPricePerUnit") or 0
        item["total"] = item.get("executionTotal") or 0
    return item


def resolve_work_journal_mutation_scope(
    cur,
    current_user,
    journal_id,
    *,
    action_mode,
    x_company_id,
    x_company_mode,
    allowed_roles,
    deps,
):
    context = deps["resolve_work_company_context"](
        cur, current_user, None, action_mode,
        x_company_id=x_company_id,
        x_company_mode=x_company_mode,
    )
    actor = deps["require_project_write_actor"](
        deps["effective_company_actors"](current_user, context),
        allowed_roles,
    )
    cur.execute(
        """SELECT id,company_id,project,COALESCE(NULLIF(work_package,''),'Основная') AS work_package,
                  master_id,master_name
             FROM work_journal WHERE id=%s FOR UPDATE""",
        (journal_id,),
    )
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Запись журнала не найдена")
    stored_company = _positive_int(row.get("company_id"))
    if not stored_company:
        raise HTTPException(status_code=409, detail="Компания записи ЖПР не определена")
    actor_company = _positive_int(actor.get("companyId") or actor.get("company_id"))
    if actor_company != stored_company:
        raise HTTPException(status_code=404, detail="Запись журнала не найдена")
    project = deps["resolve_project_parent"](
        cur,
        actor,
        project_name=str(row.get("project") or "").strip(),
        for_update=True,
    )
    deps["require_project_parent_access"](
        cur, actor, project, deps["full_view_roles"],
    )
    if _positive_int(project.get("companyId")) != stored_company:
        raise HTTPException(status_code=409, detail="Владелец ЖПР не совпадает с объектом")
    return actor, project, row
