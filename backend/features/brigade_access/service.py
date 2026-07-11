import json
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from fastapi import HTTPException


def _positive_int(value):
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def _values(value):
    if isinstance(value, list):
        return sorted({str(item).strip() for item in value if str(item or "").strip()})
    if isinstance(value, str):
        try:
            return _values(json.loads(value))
        except Exception:
            return []
    return []


def _actor_projects(actor):
    projects = _values((actor or {}).get("assignedProjects", (actor or {}).get("assigned_projects", [])))
    legacy_project = str((actor or {}).get("projectName") or (actor or {}).get("project_name") or "").strip()
    return sorted(set(projects + ([legacy_project] if legacy_project else [])))


def _row_value(row, key, index):
    if isinstance(row, dict):
        return row.get(key)
    if isinstance(row, (list, tuple)) and len(row) > index:
        return row[index]
    return None


def _unique_contractor_candidate(rows):
    user_ids = sorted({
        user_id
        for row in rows or []
        for user_id in [_positive_int(_row_value(row, "id", 0))]
        if user_id
    })
    if len(user_ids) > 1:
        raise HTTPException(
            status_code=409,
            detail="В выбранной компании найдено несколько исполнителей с такими данными. Укажите точного пользователя.",
        )
    return user_ids[0] if user_ids else None


def require_brigade_write_actor(company_actors, write_roles):
    """Return the sole selected-company actor allowed to mutate brigade contracts."""
    actors = [
        dict(actor)
        for actor in company_actors or []
        if _positive_int((actor or {}).get("companyId") or (actor or {}).get("company_id"))
    ]
    if len(actors) != 1:
        raise HTTPException(
            status_code=409,
            detail="Для изменения договора бригады выберите одну конкретную компанию",
        )
    actor = actors[0]
    allowed_roles = {str(role or "").strip() for role in write_roles or [] if str(role or "").strip()}
    if str(actor.get("role") or "").strip() not in allowed_roles:
        raise HTTPException(
            status_code=403,
            detail="Роль в выбранной компании не позволяет изменять договоры бригад",
        )
    company_id = _positive_int(actor.get("companyId") or actor.get("company_id"))
    actor["companyId"] = company_id
    actor["company_id"] = company_id
    return actor


def resolve_brigade_contractor_user(cur, company_id, contractor_id=None, contractor_name=""):
    """Resolve an optional contractor user without crossing the selected-company boundary."""
    normalized_company_id = _positive_int(company_id)
    if not normalized_company_id:
        raise HTTPException(status_code=409, detail="Компания договора бригады не определена")
    if contractor_id not in (None, "") and not _positive_int(contractor_id):
        raise HTTPException(status_code=400, detail="contractorId должен быть положительным целым числом")
    normalized_contractor_id = _positive_int(contractor_id)
    normalized_name = str(contractor_name or "").strip()
    company_scope_sql = """(
        u.company_id=%s OR EXISTS (
            SELECT 1 FROM user_company_roles m
             WHERE m.user_id=u.id AND m.company_id=%s AND COALESCE(m.active,TRUE)=TRUE
        )
    )"""

    if normalized_contractor_id:
        cur.execute(
            "SELECT u.id,u.name FROM users u WHERE u.id=%s AND COALESCE(u.active,TRUE)=TRUE AND "
            + company_scope_sql
            + " LIMIT 1",
            (normalized_contractor_id, normalized_company_id, normalized_company_id),
        )
        user_row = cur.fetchone()
        cur.execute(
            """SELECT s.name,s.email_work,s.email_personal
                 FROM staff s
                WHERE s.id=%s AND s.company_id=%s
                LIMIT 1""",
            (normalized_contractor_id, normalized_company_id),
        )
        staff_row = cur.fetchone()
        if not user_row and not staff_row:
            raise HTTPException(
                status_code=400,
                detail="Исполнитель не найден в выбранной компании",
            )
        if user_row and not staff_row:
            return _positive_int(_row_value(user_row, "id", 0))
        if user_row and staff_row:
            if not normalized_name:
                raise HTTPException(
                    status_code=409,
                    detail="ID исполнителя неоднозначен. Укажите ФИО из выбранной карточки.",
                )
            requested_name = normalized_name.casefold()
            user_name = str(_row_value(user_row, "name", 1) or "").strip().casefold()
            staff_name = str(_row_value(staff_row, "name", 0) or "").strip().casefold()
            if requested_name == user_name and requested_name != staff_name:
                return _positive_int(_row_value(user_row, "id", 0))
            if requested_name != staff_name:
                raise HTTPException(
                    status_code=409,
                    detail="ID и ФИО исполнителя указывают на разные карточки",
                )
        normalized_name = str(_row_value(staff_row, "name", 0) or normalized_name).strip()
        emails = sorted({
            str(value or "").strip().lower()
            for value in (
                _row_value(staff_row, "email_work", 1),
                _row_value(staff_row, "email_personal", 2),
            )
            if str(value or "").strip()
        })
        if emails:
            cur.execute(
                "SELECT u.id FROM users u WHERE COALESCE(u.active,TRUE)=TRUE AND "
                + company_scope_sql
                + " AND LOWER(COALESCE(u.email,'')) = ANY(%s) ORDER BY u.id",
                (normalized_company_id, normalized_company_id, emails),
            )
            email_user_id = _unique_contractor_candidate(cur.fetchall())
            if email_user_id:
                return email_user_id

    if not normalized_name:
        return None
    cur.execute(
        "SELECT u.id FROM users u WHERE COALESCE(u.active,TRUE)=TRUE AND "
        + company_scope_sql
        + " AND LOWER(TRIM(COALESCE(u.name,'')))=LOWER(TRIM(%s)) ORDER BY u.id",
        (normalized_company_id, normalized_company_id, normalized_name),
    )
    return _unique_contractor_candidate(cur.fetchall())


def grant_brigade_contractor_scope(
    cur,
    company_id,
    user_id,
    project_name,
    work_package,
    *,
    project_scoped_roles,
    package_required_roles,
):
    """Grant project/package scope only to the contractor's membership in this company."""
    normalized_company_id = _positive_int(company_id)
    normalized_user_id = _positive_int(user_id)
    project = str(project_name or "").strip()
    package = str(work_package or "Основная").strip() or "Основная"
    scoped_roles = sorted({str(role or "").strip() for role in project_scoped_roles or [] if str(role or "").strip()})
    package_roles = sorted({str(role or "").strip() for role in package_required_roles or [] if str(role or "").strip()})
    if not normalized_company_id or not normalized_user_id or not project or not scoped_roles:
        return None

    cur.execute(
        """UPDATE user_company_roles
              SET assigned_projects=CASE
                      WHEN COALESCE(assigned_projects,'[]'::jsonb) @> jsonb_build_array(%s::text)
                      THEN COALESCE(assigned_projects,'[]'::jsonb)
                      ELSE COALESCE(assigned_projects,'[]'::jsonb) || jsonb_build_array(%s::text)
                  END,
                  assigned_packages=CASE
                      WHEN NOT (role = ANY(%s)) THEN COALESCE(assigned_packages,'[]'::jsonb)
                      WHEN COALESCE(assigned_packages,'[]'::jsonb) @> jsonb_build_array(%s::text)
                      THEN COALESCE(assigned_packages,'[]'::jsonb)
                      ELSE COALESCE(assigned_packages,'[]'::jsonb) || jsonb_build_array(%s::text)
                  END,
                  updated_at=NOW()
            WHERE user_id=%s AND company_id=%s
              AND COALESCE(active,TRUE)=TRUE AND role = ANY(%s)""",
        (project, project, package_roles, package, package, normalized_user_id, normalized_company_id, scoped_roles),
    )
    cur.execute(
        """UPDATE users
              SET project_name=CASE WHEN COALESCE(TRIM(project_name),'')='' THEN %s ELSE project_name END,
                  assigned_projects=CASE
                      WHEN COALESCE(assigned_projects,'[]'::jsonb) @> jsonb_build_array(%s::text)
                      THEN COALESCE(assigned_projects,'[]'::jsonb)
                      ELSE COALESCE(assigned_projects,'[]'::jsonb) || jsonb_build_array(%s::text)
                  END,
                  assigned_packages=CASE
                      WHEN NOT (role = ANY(%s)) THEN COALESCE(assigned_packages,'[]'::jsonb)
                      WHEN COALESCE(assigned_packages,'[]'::jsonb) @> jsonb_build_array(%s::text)
                      THEN COALESCE(assigned_packages,'[]'::jsonb)
                      ELSE COALESCE(assigned_packages,'[]'::jsonb) || jsonb_build_array(%s::text)
                  END,
                  active=TRUE
            WHERE id=%s AND company_id=%s AND COALESCE(active,TRUE)=TRUE
              AND role = ANY(%s)""",
        (project, project, project, package_roles, package, package, normalized_user_id, normalized_company_id, scoped_roles),
    )
    return {
        "companyId": normalized_company_id,
        "userId": normalized_user_id,
        "projectName": project,
        "workPackage": package,
    }


def require_brigade_child_company(child_company_id, contract_company_id):
    """Reject a child row whose stored tenant differs from its contract owner."""
    child_id = _positive_int(child_company_id)
    parent_id = _positive_int(contract_company_id)
    if not child_id or not parent_id or child_id != parent_id:
        raise HTTPException(
            status_code=409,
            detail="Дочерняя запись бригады относится к другой компании",
        )
    return parent_id


def require_positive_brigade_amount(value):
    try:
        amount = Decimal(str(value).strip())
    except (InvalidOperation, TypeError, ValueError):
        amount = Decimal(0)
    if not amount.is_finite() or amount < Decimal("0.01"):
        raise HTTPException(status_code=400, detail="Сумма оплаты должна быть не меньше 0.01 ₽")
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def brigade_contract_project_reference(project_id, project_name):
    """Use an immutable project id when present; names are legacy fallback only."""
    normalized_project_id = _positive_int(project_id)
    normalized_name = str(project_name or "").strip()
    return normalized_project_id, "" if normalized_project_id else normalized_name


def require_brigade_project_payment_link(project_payment_id):
    link_id = _positive_int(project_payment_id)
    if not link_id:
        raise HTTPException(
            status_code=409,
            detail="Выплата не связана с денежной проводкой однозначно. Нужна ручная сверка.",
        )
    return link_id


def brigade_contract_visibility_filter(
    company_actors,
    *,
    allowed_roles,
    full_view_roles,
    worker_roles=(),
    package_limit_roles=(),
    package_optional_roles=(),
    item_alias="",
):
    """Build a fail-closed contract scope for effective company memberships."""
    allowed = {str(role or "").strip() for role in allowed_roles or () if str(role or "").strip()}
    full_view = {str(role or "").strip() for role in full_view_roles or () if str(role or "").strip()}
    workers = {str(role or "").strip() for role in worker_roles or () if str(role or "").strip()}
    package_limited = {
        str(role or "").strip() for role in package_limit_roles or () if str(role or "").strip()
    }
    package_optional = {
        str(role or "").strip() for role in package_optional_roles or () if str(role or "").strip()
    }
    item_prefix = str(item_alias or "").strip()
    if item_prefix and not item_prefix.replace("_", "").isalnum():
        raise ValueError("Invalid brigade item table alias")
    clauses = []
    params = []
    for actor in company_actors or []:
        company_id = _positive_int((actor or {}).get("companyId") or (actor or {}).get("company_id"))
        role = str((actor or {}).get("role") or "").strip()
        if not company_id or role not in allowed:
            continue
        actor_clauses = ["bc.company_id=%s"]
        actor_params = [company_id]
        if role not in full_view:
            projects = _actor_projects(actor)
            if not projects:
                continue
            actor_clauses.append("bc.project_name = ANY(%s)")
            actor_params.append(projects)
        if role in workers:
            actor_id = _positive_int((actor or {}).get("id")) or 0
            actor_name = str((actor or {}).get("name") or "").strip()
            if not actor_id and not actor_name:
                continue
            actor_clauses.append(
                "(COALESCE(bc.contractor_id,0)=%s OR "
                "(COALESCE(bc.contractor_id,0)=0 AND LOWER(COALESCE(bc.brigade_name,''))=LOWER(%s)))"
            )
            actor_params.extend([actor_id, actor_name])
        if role in package_limited:
            packages = _values((actor or {}).get("assignedPackages", (actor or {}).get("assigned_packages", [])))
            if not packages and role not in package_optional:
                continue
            if packages:
                if item_prefix:
                    actor_clauses.append(
                        f"COALESCE(NULLIF({item_prefix}.work_package,''), "
                        "NULLIF(bc.work_package,''), 'Основная') = ANY(%s)"
                    )
                else:
                    actor_clauses.append("""EXISTS (
                        SELECT 1 FROM brigade_contract_items bci_scope
                        WHERE bci_scope.contract_id=bc.id
                          AND COALESCE(NULLIF(bci_scope.work_package,''), NULLIF(bc.work_package,''), 'Основная') = ANY(%s)
                    )""")
                actor_params.append(packages)
        clauses.append("(" + " AND ".join(actor_clauses) + ")")
        params.extend(actor_params)
    if not clauses:
        return "FALSE", []
    if len(clauses) == 1:
        return clauses[0], params
    return "(" + " OR ".join(clauses) + ")", params
