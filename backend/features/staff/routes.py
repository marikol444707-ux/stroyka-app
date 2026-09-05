"""Staff directory routes.

Extracted from backend/main.py (Task 13.1, slice 39): the staff routes
with their column maps, sanitizer, access
provisioning (creates/updates the linked user account) and the
fire-with-deactivation flow that disables user logins and revokes
sessions. Shared access-scope validation stays in main.py and is
injected; password hashing and session revocation come from the
auth module.
"""

import json
from collections.abc import Mapping

import psycopg2.extras
from fastapi import Depends, Header, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

try:
    from backend.auth import hash_password, _revoke_user_sessions
except ModuleNotFoundError:
    from auth import hash_password, _revoke_user_sessions


class StaffModel(BaseModel):
    name: str
    role: str = ""
    phone: str = ""
    salary: float = 0
    project: str = ""
    payType: str = "оклад"
    lastName: Optional[str] = ""
    firstName: Optional[str] = ""
    middleName: Optional[str] = ""
    birthDate: Optional[str] = ""
    citizenship: Optional[str] = ""
    address: Optional[str] = ""
    photoUrl: Optional[str] = ""
    emailWork: Optional[str] = ""
    emailPersonal: Optional[str] = ""
    phoneExtra: Optional[str] = ""
    passportSeries: Optional[str] = ""
    passportNumber: Optional[str] = ""
    passportIssuedBy: Optional[str] = ""
    passportIssuedDate: Optional[str] = ""
    inn: Optional[str] = ""
    snils: Optional[str] = ""
    specialization: Optional[str] = ""
    category: Optional[str] = ""
    employmentType: Optional[str] = ""
    hiredDate: Optional[str] = ""
    firedDate: Optional[str] = ""
    status: Optional[str] = "Активен"
    brigade: Optional[str] = ""
    bankAccount: Optional[str] = ""
    bankName: Optional[str] = ""
    bankBik: Optional[str] = ""
    bankCorr: Optional[str] = ""
    ogrnip: Optional[str] = ""
    cardNumber: Optional[str] = ""
    signatureUrl: Optional[str] = ""
    notes: Optional[str] = ""
    email: Optional[str] = ""
    password: Optional[str] = ""
    systemRole: Optional[str] = ""
    assignedProjects: list[str] = Field(default_factory=list)
    assignedPackages: list[str] = Field(default_factory=list)


def register_staff_module(app, deps):
    get_db = deps["get_db"]
    get_current_user = deps["get_current_user"]
    require_roles = deps["require_roles"]
    staff_view_roles = tuple(deps.get("staff_view_roles") or ())
    staff_manage_roles = tuple(deps.get("staff_manage_roles") or ())
    staff_full_view_roles = tuple(deps.get("staff_full_view_roles") or ())
    user_project_names = deps["user_project_names"]
    safe_project_list = deps["safe_project_list"]
    prepare_user_access_scope = deps["prepare_user_access_scope"]
    date_or_none = deps["date_or_none"]
    log_audit = deps["log_audit"]
    resolve_work_company_context = deps["resolve_work_company_context"]
    effective_company_actors = deps["effective_company_actors"]

    def _positive_int(value):
        return value if type(value) is int and value > 0 else None

    def _row_value(row, key, index):
        if isinstance(row, Mapping):
            return row.get(key)
        if isinstance(row, (list, tuple)) and len(row) > index:
            return row[index]
        return None

    def _selected_actor(
        cur, current_user, action_mode, x_company_id, x_company_mode, allowed_roles
    ):
        context = resolve_work_company_context(
            cur,
            current_user,
            None,
            action_mode,
            x_company_id=x_company_id,
            x_company_mode=x_company_mode,
        )
        if (context or {}).get("mode") != "company":
            raise HTTPException(
                status_code=409,
                detail="Для сотрудников выберите одну конкретную компанию",
            )
        company_id = _positive_int(
            (context or {}).get("companyId") or (context or {}).get("company_id")
        )
        if company_id is None:
            raise HTTPException(status_code=409, detail="Компания сотрудников не определена")
        actors = [
            dict(actor or {})
            for actor in effective_company_actors(current_user, context)
            if str((actor or {}).get("role") or "").strip() in allowed_roles
        ]
        if len(actors) != 1:
            if not actors:
                return None
            raise HTTPException(
                status_code=409,
                detail="Для сотрудников выберите одну конкретную компанию",
            )
        actor = actors[0]
        actor_company_id = _positive_int(
            actor.get("companyId") or actor.get("company_id")
        )
        if actor_company_id != company_id:
            raise HTTPException(
                status_code=409,
                detail="Компания сотрудника не совпадает с выбранной компанией",
            )
        actor["companyId"] = company_id
        actor["company_id"] = company_id
        return actor

    def _actor_name(actor):
        return str(
            (actor or {}).get("name")
            or (actor or {}).get("email")
            or (actor or {}).get("id")
            or ""
        ).strip()

    def _exact_project(cur, company_id, project_name):
        project_name = str(project_name or "").strip()
        if not project_name:
            return {"id": None, "name": ""}
        cur.execute(
            """SELECT id,name
                 FROM public.projects
                WHERE name=%s AND company_id=%s
                ORDER BY id
                LIMIT 2""",
            (project_name, company_id),
        )
        rows = cur.fetchall()
        if len(rows) != 1:
            raise HTTPException(
                status_code=404,
                detail="Объект сотрудника не найден в выбранной компании",
            )
        row = rows[0]
        project_id = _positive_int(_row_value(row, "id", 0))
        exact_name = str(_row_value(row, "name", 1) or "").strip()
        if project_id is None or not exact_name:
            raise HTTPException(
                status_code=404,
                detail="Объект сотрудника не найден в выбранной компании",
            )
        return {"id": project_id, "name": exact_name}

    def _exact_staff(cur, company_id, staff_id, *, lock=None, columns="id"):
        if _positive_int(staff_id) is None:
            raise HTTPException(status_code=400, detail="Некорректный id сотрудника")
        suffix = ""
        if lock == "update":
            suffix = " FOR UPDATE"
        elif lock == "share":
            suffix = " FOR SHARE"
        cur.execute(
            f"""SELECT {columns}
                  FROM public.staff
                 WHERE id=%s AND company_id=%s
                   AND company_scope_verified IS TRUE{suffix}""",
            (staff_id, company_id),
        )
        row = cur.fetchone()
        if _positive_int(_row_value(row, "id", 0)) is None:
            raise HTTPException(
                status_code=404,
                detail="Сотрудник не найден в выбранной компании",
            )
        return row

    STAFF_COLUMNS = """id, name, role, phone, salary, project, pay_type as "payType",
        last_name as "lastName", first_name as "firstName", middle_name as "middleName",
        birth_date as "birthDate", citizenship, address, photo_url as "photoUrl",
        email_work as "emailWork", email_personal as "emailPersonal", phone_extra as "phoneExtra",
        passport_series as "passportSeries", passport_number as "passportNumber",
        passport_issued_by as "passportIssuedBy", passport_issued_date as "passportIssuedDate",
        inn, snils, specialization, category,
        employment_type as "employmentType", hired_date as "hiredDate", fired_date as "firedDate",
        status, brigade, bank_account as "bankAccount", bank_name as "bankName",
        bank_bik as "bankBik", bank_corr as "bankCorr", ogrnip, card_number as "cardNumber",
        signature_url as "signatureUrl", notes"""

    SENSITIVE_STAFF_FIELDS = {
        "salary", "birthDate", "citizenship", "address", "emailPersonal", "phoneExtra",
        "passportSeries", "passportNumber", "passportIssuedBy", "passportIssuedDate",
        "inn", "snils", "bankAccount", "bankName", "bankBik", "bankCorr", "ogrnip",
        "cardNumber", "signatureUrl", "notes",
    }

    def _sanitize_staff_for_project_roles(row: dict) -> dict:
        data = dict(row or {})
        for key in SENSITIVE_STAFF_FIELDS:
            if key in data:
                data[key] = ""
        return data

    def _staff_tuple(s):
        def d(v):
            return v if v else None
        return (s.name, s.role, s.phone, s.salary, s.project, s.payType,
                s.lastName or None, s.firstName or None, s.middleName or None,
                d(s.birthDate), s.citizenship or None, s.address or None, s.photoUrl or None,
                s.emailWork or None, s.emailPersonal or None, s.phoneExtra or None,
                s.passportSeries or None, s.passportNumber or None,
                s.passportIssuedBy or None, d(s.passportIssuedDate),
                s.inn or None, s.snils or None, s.specialization or None, s.category or None,
                s.employmentType or None, d(s.hiredDate), d(s.firedDate),
                s.status or "Активен", s.brigade or None,
                s.bankAccount or None, s.bankName or None, s.bankBik or None, s.bankCorr or None,
                s.ogrnip or None, s.cardNumber or None, s.signatureUrl or None, s.notes or None)

    STAFF_INSERT_COLS = """name, role, phone, salary, project, pay_type,
        last_name, first_name, middle_name, birth_date, citizenship, address, photo_url,
        email_work, email_personal, phone_extra,
        passport_series, passport_number, passport_issued_by, passport_issued_date,
        inn, snils, specialization, category,
        employment_type, hired_date, fired_date, status, brigade,
        bank_account, bank_name, bank_bik, bank_corr, ogrnip, card_number,
        signature_url, notes, company_id, company_scope_verified"""
    STAFF_PLACEHOLDERS = ",".join(["%s"] * 39)

    STAFF_ACCESS_ROLES = (
        "директор", "зам_директора", "бухгалтер", "прораб", "главный_инженер",
        "сметчик", "мастер", "субподрядчик", "бригадир", "кладовщик", "снабженец",
        "технадзор", "стройконтроль", "менеджер_crm",
    )

    def _sync_staff_access(cur, s: StaffModel, company_id, staff_id, exact_project):
        if _positive_int(staff_id) is None:
            raise HTTPException(status_code=400, detail="Некорректная связь сотрудника")
        email = ((s.email or s.emailWork or "") or "").strip().lower()
        password = ((s.password or "") or "").strip()
        role = ((s.systemRole or "") or "").strip()
        has_access_input = bool(email or password or role or s.assignedProjects or s.assignedPackages)
        if not has_access_input:
            return None
        if not email or not role:
            raise HTTPException(status_code=400, detail="Для доступа сотрудника нужны системная роль и email")
        if role not in STAFF_ACCESS_ROLES:
            raise HTTPException(status_code=400, detail="Недопустимая системная роль: " + role)
        if password and len(password) < 5:
            raise HTTPException(status_code=400, detail="Пароль минимум 5 символов")

        assigned_projects = safe_project_list(s.assignedProjects or [])
        assigned_packages = safe_project_list(s.assignedPackages or [])
        project_name = exact_project["name"]
        project_id = exact_project["id"]
        if project_name and project_name not in assigned_projects:
            assigned_projects.append(project_name)
        assigned_projects = list(dict.fromkeys(assigned_projects))
        if assigned_projects:
            cur.execute(
                """SELECT name
                     FROM public.projects
                    WHERE company_id=%s AND name=ANY(%s)
                    ORDER BY name""",
                (company_id, assigned_projects),
            )
            exact_names = {
                str(_row_value(row, "name", 0) or "").strip()
                for row in cur.fetchall()
            }
            if exact_names != set(assigned_projects):
                raise HTTPException(
                    status_code=404,
                    detail="Один из объектов доступа не найден в выбранной компании",
                )

        cur.execute(
            """SELECT id,company_id
                 FROM public.users
                WHERE LOWER(email)=LOWER(%s)
                ORDER BY id
                LIMIT 2
                FOR UPDATE""",
            (email,),
        )
        identity_rows = cur.fetchall()
        if len(identity_rows) > 1:
            raise HTTPException(
                status_code=409,
                detail="Email связан с несколькими аккаунтами — сначала устраните дубликат",
            )
        existing = identity_rows[0] if identity_rows else None
        user_id = _positive_int(_row_value(existing, "id", 0))
        full_name = (s.name or "Сотрудник").strip()
        if user_id:
            # A password and the global user identity are shared by all company
            # memberships. A manager of one company must never rewrite them.
            action = "updated"
        else:
            if not password:
                raise HTTPException(status_code=400, detail="Для нового доступа сотрудника нужен пароль")
            cur.execute("""
                INSERT INTO public.users
                    (name,email,password,role,project_id,project_name,
                     assigned_projects,assigned_packages,active,company_id)
                VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,TRUE,%s)
                RETURNING id
            """, (full_name, email, hash_password(password), role, project_id, project_name,
                  json.dumps(assigned_projects), json.dumps(assigned_packages), company_id))
            new_row = cur.fetchone()
            user_id = _positive_int(_row_value(new_row, "id", 0))
            if user_id is None:
                raise HTTPException(status_code=400, detail="Не удалось создать доступ сотрудника")
            action = "created"
        cur.execute(
            """SELECT user_id
                 FROM public.user_company_roles
                WHERE company_id=%s
                  AND staff_id=%s
                  AND COALESCE(active,TRUE)=TRUE
                  AND user_id<>%s
                LIMIT 1
                FOR UPDATE""",
            (company_id, staff_id, user_id),
        )
        if cur.fetchone() is not None:
            raise HTTPException(
                status_code=409,
                detail="Карточка сотрудника уже связана с другим аккаунтом",
            )
        cur.execute(
            """SELECT staff_id
                 FROM public.user_company_roles
                WHERE company_id=%s
                  AND user_id=%s
                  AND staff_id IS NOT NULL
                  AND staff_id<>%s
                  AND COALESCE(active,TRUE)=TRUE
                LIMIT 1
                FOR UPDATE""",
            (company_id, user_id, staff_id),
        )
        if cur.fetchone() is not None:
            raise HTTPException(
                status_code=409,
                detail="Аккаунт уже связан с другой карточкой сотрудника",
            )
        cur.execute(
            """UPDATE public.user_company_roles
                  SET active=FALSE,updated_at=NOW()
                WHERE user_id=%s AND company_id=%s AND role<>%s AND active IS TRUE""",
            (user_id, company_id, role),
        )
        cur.execute(
            """INSERT INTO public.user_company_roles
                   (user_id,company_id,staff_id,role,assigned_projects,assigned_packages,
                    active,is_default,updated_at)
                VALUES (%s,%s,%s,%s,%s::jsonb,%s::jsonb,TRUE,FALSE,NOW())
                ON CONFLICT (user_id,company_id,role) DO UPDATE
                  SET staff_id=EXCLUDED.staff_id,
                      assigned_projects=EXCLUDED.assigned_projects,
                      assigned_packages=EXCLUDED.assigned_packages,
                      active=TRUE,updated_at=NOW()""",
            (
                user_id,
                company_id,
                staff_id,
                role,
                json.dumps(assigned_projects),
                json.dumps(assigned_packages),
            ),
        )
        return {
            "id": user_id,
            "email": email,
            "role": role,
            "action": action,
            "assignedProjects": assigned_projects,
            "assignedPackages": assigned_packages,
        }

    @app.get("/staff")
    def get_staff(
        x_company_id: Optional[str] = Header(None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            actor = _selected_actor(
                cur, current_user, "read", x_company_id, x_company_mode,
                staff_view_roles,
            )
            if actor is None:
                return []
            company_id = actor["companyId"]
            role = actor.get("role")
            where = ["company_id=%s", "company_scope_verified IS TRUE"]
            params = [company_id]
            if role in ("прораб", "главный_инженер") and role not in staff_manage_roles:
                projects = user_project_names(actor)
                if not projects:
                    return []
                where.append("project = ANY(%s)")
                params.append(projects)
            cur.execute(
                "SELECT " + STAFF_COLUMNS + " FROM public.staff WHERE "
                + " AND ".join(where) + " ORDER BY id",
                tuple(params),
            )
            rows = cur.fetchall()
            access_by_staff = {}
            if role in staff_full_view_roles:
                cur.execute(
                    """SELECT membership.staff_id,
                              account.id AS "accessUserId",
                              account.email AS "accessEmail",
                              membership.role AS "accessRole",
                              membership.assigned_projects AS "accessAssignedProjects",
                              membership.assigned_packages AS "accessAssignedPackages"
                         FROM public.user_company_roles membership
                         JOIN public.users account ON account.id=membership.user_id
                        WHERE membership.company_id=%s
                          AND membership.staff_id IS NOT NULL
                          AND COALESCE(membership.active,TRUE)=TRUE
                          AND COALESCE(account.active,TRUE)=TRUE
                        ORDER BY membership.staff_id""",
                    (company_id,),
                )
                for access_row in cur.fetchall():
                    staff_id = _positive_int(_row_value(access_row, "staff_id", 0))
                    if staff_id is None:
                        continue
                    access_by_staff[staff_id] = {
                        "accessUserId": _positive_int(
                            _row_value(access_row, "accessUserId", 1)
                        ),
                        "accessEmail": str(
                            _row_value(access_row, "accessEmail", 2) or ""
                        ).strip(),
                        "accessRole": str(
                            _row_value(access_row, "accessRole", 3) or ""
                        ).strip(),
                        "accessAssignedProjects": safe_project_list(
                            _row_value(access_row, "accessAssignedProjects", 4) or []
                        ),
                        "accessAssignedPackages": safe_project_list(
                            _row_value(access_row, "accessAssignedPackages", 5) or []
                        ),
                    }
        finally:
            cur.close()
            conn.close()
        result = []
        for r in rows:
            d = dict(r)
            d.update(access_by_staff.get(_positive_int(d.get("id")), {}))
            if role in ("прораб", "главный_инженер") and role not in staff_manage_roles:
                d = _sanitize_staff_for_project_roles(d)
            for k in ("birthDate", "passportIssuedDate", "hiredDate", "firedDate"):
                d[k] = str(d[k]) if d.get(k) else ""
            for k in list(d.keys()):
                if d[k] is None:
                    d[k] = ""
            result.append(d)
        return result

    @app.post("/staff/current-user-link")
    def link_current_user_to_staff(
        x_company_id: Optional[str] = Header(None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(None, alias="X-Company-Mode"),
        _current_user: dict = Depends(require_roles(*staff_manage_roles)),
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            actor = _selected_actor(
                cur, _current_user, "write", x_company_id, x_company_mode,
                staff_manage_roles,
            )
            if actor is None:
                raise HTTPException(status_code=403, detail="Недостаточно прав для сотрудников")
            company_id = actor["companyId"]
            user_id = _positive_int(actor.get("id"))
            membership_id = _positive_int(
                actor.get("membershipId") or actor.get("membership_id")
            )
            role = str(actor.get("role") or "").strip()
            email = str(actor.get("email") or "").strip().lower()
            name = _actor_name(actor)
            if user_id is None or membership_id is None or not email or not role:
                raise HTTPException(
                    status_code=409,
                    detail="Основной аккаунт выбранной компании не определён",
                )

            cur.execute(
                """SELECT id,user_id,company_id,staff_id,role
                     FROM public.user_company_roles
                    WHERE id=%s AND user_id=%s AND company_id=%s AND role=%s
                      AND COALESCE(active,TRUE)=TRUE
                    FOR UPDATE""",
                (membership_id, user_id, company_id, role),
            )
            membership = cur.fetchone()
            if _positive_int(_row_value(membership, "id", 0)) is None:
                raise HTTPException(
                    status_code=409,
                    detail="Активная роль основного аккаунта не найдена",
                )

            linked_staff_id = _positive_int(_row_value(membership, "staff_id", 3))
            if linked_staff_id is not None:
                staff_row = _exact_staff(
                    cur, company_id, linked_staff_id,
                    columns="id,name,email_work",
                )
                return {
                    "ok": True,
                    "created": False,
                    "staffId": linked_staff_id,
                    "email": str(_row_value(staff_row, "email_work", 2) or email),
                }

            cur.execute(
                """SELECT id
                     FROM public.staff
                    WHERE company_id=%s
                      AND company_scope_verified IS TRUE
                      AND (LOWER(BTRIM(email_work))=%s
                           OR LOWER(BTRIM(email_personal))=%s)
                    ORDER BY id
                    LIMIT 2
                    FOR UPDATE""",
                (company_id, email, email),
            )
            matching_staff = list(cur.fetchall() or [])
            if len(matching_staff) > 1:
                raise HTTPException(
                    status_code=409,
                    detail="Email связан с несколькими сотрудниками",
                )

            created = not matching_staff
            if matching_staff:
                staff_id = _positive_int(_row_value(matching_staff[0], "id", 0))
            else:
                human_role = {
                    "директор": "Директор",
                    "зам_директора": "Заместитель директора",
                }.get(role, role.replace("_", " ").strip().title())
                cur.execute(
                    """INSERT INTO public.staff
                              (name,role,salary,pay_type,email_work,status,
                               company_id,company_scope_verified)
                         VALUES (%s,%s,0,'оклад',%s,'Активен',%s,TRUE)
                      RETURNING id""",
                    (name or email, human_role, email, company_id),
                )
                staff_id = _positive_int(_row_value(cur.fetchone(), "id", 0))
            if staff_id is None:
                raise HTTPException(status_code=409, detail="Карточка сотрудника не определена")

            cur.execute(
                """SELECT user_id
                     FROM public.user_company_roles
                    WHERE company_id=%s AND staff_id=%s
                      AND COALESCE(active,TRUE)=TRUE AND user_id<>%s
                    LIMIT 1
                    FOR UPDATE""",
                (company_id, staff_id, user_id),
            )
            if cur.fetchone() is not None:
                raise HTTPException(
                    status_code=409,
                    detail="Карточка сотрудника уже связана с другим аккаунтом",
                )

            cur.execute(
                """UPDATE public.user_company_roles
                      SET staff_id=%s,updated_at=NOW()
                    WHERE id=%s AND user_id=%s AND company_id=%s
                      AND COALESCE(active,TRUE)=TRUE""",
                (staff_id, membership_id, user_id, company_id),
            )
            if cur.rowcount != 1:
                raise HTTPException(
                    status_code=409,
                    detail="Не удалось связать основной аккаунт с сотрудником",
                )
            conn.commit()
            log_audit(
                _actor_name(actor), role, "link", "staff", staff_id,
                "Основной аккаунт связан с карточкой сотрудника", "",
            )
            return {
                "ok": True,
                "created": created,
                "staffId": staff_id,
                "email": email,
            }
        except BaseException:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()

    @app.post("/staff")
    def create_staff(
        s: StaffModel,
        x_company_id: Optional[str] = Header(None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(None, alias="X-Company-Mode"),
        _current_user: dict = Depends(require_roles(*staff_manage_roles)),
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            actor = _selected_actor(
                cur, _current_user, "create", x_company_id, x_company_mode,
                staff_manage_roles,
            )
            if actor is None:
                raise HTTPException(status_code=403, detail="Недостаточно прав для сотрудников")
            company_id = actor["companyId"]
            project = _exact_project(cur, company_id, s.project)
            values = list(_staff_tuple(s))
            values[4] = project["name"]
            cur.execute(
                "INSERT INTO public.staff (" + STAFF_INSERT_COLS + ") VALUES ("
                + STAFF_PLACEHOLDERS + ") RETURNING id",
                tuple(values) + (company_id, True),
            )
            new_id = _positive_int(_row_value(cur.fetchone(), "id", 0))
            if new_id is None:
                raise HTTPException(status_code=400, detail="Не удалось создать сотрудника")
            access = _sync_staff_access(cur, s, company_id, new_id, project)
            conn.commit()
            log_audit(
                _actor_name(actor), actor.get("role", ""),
                "create",
                "staff",
                new_id,
                ("Создан сотрудник: " + str(s.name or "") + ", роль " + str(s.role or ""))[:250],
                s.project or "",
            )
            return {"id": new_id, "ok": True, "access": access}
        except BaseException:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()

    @app.put("/staff/{id}")
    def update_staff(
        id: int,
        s: StaffModel,
        x_company_id: Optional[str] = Header(None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(None, alias="X-Company-Mode"),
        _current_user: dict = Depends(require_roles(*staff_manage_roles)),
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            actor = _selected_actor(
                cur, _current_user, "write", x_company_id, x_company_mode,
                staff_manage_roles,
            )
            if actor is None:
                raise HTTPException(status_code=403, detail="Недостаточно прав для сотрудников")
            company_id = actor["companyId"]
            project = _exact_project(cur, company_id, s.project)
            _exact_staff(cur, company_id, id, lock="update")
            values = list(_staff_tuple(s))
            values[4] = project["name"]
            cur.execute("""UPDATE staff SET name=%s, role=%s, phone=%s, salary=%s, project=%s, pay_type=%s,
                last_name=%s, first_name=%s, middle_name=%s, birth_date=%s, citizenship=%s, address=%s, photo_url=%s,
                email_work=%s, email_personal=%s, phone_extra=%s,
                passport_series=%s, passport_number=%s, passport_issued_by=%s, passport_issued_date=%s,
                inn=%s, snils=%s, specialization=%s, category=%s,
                employment_type=%s, hired_date=%s, fired_date=%s, status=%s, brigade=%s,
                bank_account=%s, bank_name=%s, bank_bik=%s, bank_corr=%s, ogrnip=%s, card_number=%s,
                signature_url=%s, notes=%s
                WHERE id=%s AND company_id=%s
                  AND company_scope_verified IS TRUE""", tuple(values) + (id, company_id))
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Сотрудник не найден")
            access = _sync_staff_access(cur, s, company_id, id, project)
            conn.commit()
            log_audit(
                _actor_name(actor), actor.get("role", ""),
                "update",
                "staff",
                id,
                ("Обновлен сотрудник: " + str(s.name or "") + ", роль " + str(s.role or ""))[:250],
                s.project or "",
            )
            return {"ok": True, "access": access}
        except BaseException:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()

    @app.delete("/staff/{id}")
    def delete_staff(
        id: int,
        x_company_id: Optional[str] = Header(None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(None, alias="X-Company-Mode"),
        _current_user: dict = Depends(require_roles(*staff_manage_roles)),
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            actor = _selected_actor(
                cur, _current_user, "write", x_company_id, x_company_mode,
                staff_manage_roles,
            )
            if actor is None:
                raise HTTPException(status_code=403, detail="Недостаточно прав для сотрудников")
            company_id = actor["companyId"]
            staff_row = _exact_staff(
                cur, company_id, id, lock="update",
                columns=("id,name,role,COALESCE(project,'') AS project,"
                         "email_work,email_personal"),
            )
            emails = sorted(set([
                str(staff_row.get("email_work") or "").strip().lower(),
                str(staff_row.get("email_personal") or "").strip().lower(),
            ]) - {""})
            cur.execute("""
                UPDATE staff
                   SET status='Уволен',
                       fired_date=COALESCE(fired_date, CURRENT_DATE)
                 WHERE id=%s AND company_id=%s
                   AND company_scope_verified IS TRUE
            """, (id, company_id))
            cur.execute("""
                UPDATE public.user_company_roles membership
                   SET active=FALSE,updated_at=NOW()
                  FROM public.users linked_user
                 WHERE membership.user_id=linked_user.id
                   AND membership.company_id=%s
                   AND membership.active IS TRUE
                   AND (
                       membership.staff_id=%s
                       OR LOWER(COALESCE(linked_user.email,''))=ANY(%s)
                   )
                 RETURNING membership.user_id AS id
            """, (company_id, id, emails))
            disabled_users = len(cur.fetchall())
            conn.commit()
            log_audit(
                _actor_name(actor), actor.get("role", ""),
                "deactivate",
                "staff",
                id,
                ("Сотрудник уволен/отключен: " + str(staff_row.get("name") or "") + ", роль " + str(staff_row.get("role") or ""))[:250],
                staff_row.get("project") or "",
            )
            return {"ok": True, "status": "Уволен", "disabledUsers": disabled_users}
        except BaseException:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()

    @app.get("/staff/{staff_id}/profile")
    def get_staff_profile(
        staff_id: int,
        x_company_id: Optional[str] = Header(None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(None, alias="X-Company-Mode"),
        _current_user: dict = Depends(require_roles(*staff_view_roles)),
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            actor = _selected_actor(
                cur, _current_user, "read", x_company_id, x_company_mode,
                staff_view_roles,
            )
            if actor is None:
                raise HTTPException(status_code=403, detail="Нет доступа к сотрудникам")
            company_id = actor["companyId"]
            row = _exact_staff(
                cur, company_id, staff_id,
                columns=("id,name,COALESCE(project,'') AS project,"
                         "email_work,email_personal"),
            )
            staff_name = str(_row_value(row, "name", 1) or "")
            staff_project = str(_row_value(row, "project", 2) or "")
            emails = sorted({
                str(_row_value(row, "email_work", 3) or "").strip().lower(),
                str(_row_value(row, "email_personal", 4) or "").strip().lower(),
            } - {""})

            cur.execute(
                "SELECT name FROM public.projects WHERE company_id=%s ORDER BY name",
                (company_id,),
            )
            company_projects = [
                str(_row_value(item, "name", 0) or "") for item in cur.fetchall()
            ]
            full_view = actor.get("role") in staff_full_view_roles
            if full_view:
                allowed_staff_projects = company_projects
            else:
                assigned = set(user_project_names(actor))
                allowed_staff_projects = [name for name in company_projects if name in assigned]
                if staff_project not in allowed_staff_projects:
                    raise HTTPException(
                        status_code=403,
                        detail="Нет доступа к карточке сотрудника этого объекта",
                    )

            custom = []
            if full_view:
                cur.execute(
                    """SELECT id,doc_type,title,file_url,status,signed_at,
                              expires_at,notes,created_at
                         FROM public.staff_documents
                        WHERE staff_id=%s ORDER BY id DESC""",
                    (staff_id,),
                )
                for item in cur.fetchall():
                    custom.append({
                        "id": _row_value(item, "id", 0),
                        "docType": _row_value(item, "doc_type", 1),
                        "title": _row_value(item, "title", 2) or "",
                        "fileUrl": _row_value(item, "file_url", 3) or "",
                        "status": _row_value(item, "status", 4) or "",
                        "signedAt": str(_row_value(item, "signed_at", 5) or ""),
                        "expiresAt": str(_row_value(item, "expires_at", 6) or ""),
                        "notes": _row_value(item, "notes", 7) or "",
                        "createdAt": str(_row_value(item, "created_at", 8) or ""),
                    })

            user_id = None
            if emails:
                cur.execute(
                    """SELECT u.id
                         FROM public.users u
                         JOIN public.user_company_roles membership
                           ON membership.user_id=u.id
                          AND membership.company_id=%s
                          AND membership.active IS TRUE
                        WHERE LOWER(COALESCE(u.email,''))=ANY(%s)
                        ORDER BY u.id LIMIT 2""",
                    (company_id, emails),
                )
                linked = cur.fetchall()
                if len(linked) == 1:
                    user_id = _positive_int(_row_value(linked[0], "id", 0))

            contracts_list = []
            acts_list = []
            pd_consents = []
            if user_id is not None and allowed_staff_projects:
                cur.execute(
                    """SELECT id,contract_number,project,start_date,end_date
                         FROM public.contracts
                        WHERE master_id=%s AND project=ANY(%s)
                        ORDER BY id DESC""",
                    (user_id, allowed_staff_projects),
                )
                for item in cur.fetchall():
                    contracts_list.append({
                        "id": _row_value(item, "id", 0),
                        "contractNumber": _row_value(item, "contract_number", 1) or "",
                        "project": _row_value(item, "project", 2) or "",
                        "startDate": str(_row_value(item, "start_date", 3) or ""),
                        "endDate": str(_row_value(item, "end_date", 4) or ""),
                        "signedAt": "", "status": "",
                    })
                cur.execute(
                    """SELECT id,project,COALESCE(work_package,'') AS work_package,
                              period_start,period_end,total_amount,paid_amount,status
                         FROM public.interim_acts
                        WHERE master_id=%s AND project=ANY(%s)
                        ORDER BY id DESC""",
                    (user_id, allowed_staff_projects),
                )
                for item in cur.fetchall():
                    item_id = _row_value(item, "id", 0)
                    acts_list.append({
                        "id": item_id, "actNumber": str(item_id),
                        "project": _row_value(item, "project", 1) or "",
                        "workPackage": _row_value(item, "work_package", 2) or "",
                        "periodFrom": str(_row_value(item, "period_start", 3) or ""),
                        "periodTo": str(_row_value(item, "period_end", 4) or ""),
                        "totalAmount": float(_row_value(item, "total_amount", 5) or 0),
                        "paidAmount": float(_row_value(item, "paid_amount", 6) or 0),
                        "status": _row_value(item, "status", 7) or "", "createdAt": "",
                    })
            if user_id is not None and full_view:
                cur.execute(
                    """SELECT id,signed_at,scan_url,uploaded_by
                         FROM public.pd_consents
                        WHERE user_id=%s ORDER BY id DESC""",
                    (user_id,),
                )
                for item in cur.fetchall():
                    pd_consents.append({
                        "id": _row_value(item, "id", 0),
                        "signedAt": _row_value(item, "signed_at", 1) or "",
                        "scanUrl": _row_value(item, "scan_url", 2) or "",
                        "uploadedBy": _row_value(item, "uploaded_by", 3) or "",
                    })

            tb_entries = []
            works = []
            if allowed_staff_projects:
                cur.execute(
                    """SELECT id,project_name,instructor,instruction_type,date
                         FROM public.tb_journal
                        WHERE master_name=%s AND project_name=ANY(%s)
                        ORDER BY id DESC LIMIT 20""",
                    (staff_name, allowed_staff_projects),
                )
                for item in cur.fetchall():
                    tb_entries.append({
                        "id": _row_value(item, "id", 0),
                        "projectName": _row_value(item, "project_name", 1) or "",
                        "instructor": _row_value(item, "instructor", 2) or "",
                        "instructionType": _row_value(item, "instruction_type", 3) or "",
                        "date": str(_row_value(item, "date", 4) or ""),
                    })
                cur.execute(
                    """SELECT project,description,quantity,unit,total,date,status
                         FROM public.work_journal
                        WHERE master_name=%s AND project=ANY(%s)
                        ORDER BY id DESC LIMIT 50""",
                    (staff_name, allowed_staff_projects),
                )
                for item in cur.fetchall():
                    works.append({
                        "project": _row_value(item, "project", 0) or "",
                        "description": _row_value(item, "description", 1) or "",
                        "quantity": float(_row_value(item, "quantity", 2) or 0),
                        "unit": _row_value(item, "unit", 3) or "",
                        "total": float(_row_value(item, "total", 4) or 0),
                        "date": str(_row_value(item, "date", 5) or ""),
                        "status": _row_value(item, "status", 6) or "",
                    })

            return {
                "staffId": staff_id,
                "staffName": staff_name,
                "userId": user_id,
                "customDocuments": custom,
                "contracts": contracts_list,
                "acts": acts_list,
                "pdConsents": pd_consents,
                "tbJournal": tb_entries,
                "workJournal": works,
            }
        finally:
            cur.close()
            conn.close()

    @app.post("/staff/{staff_id}/documents")
    def add_staff_document(
        staff_id: int,
        data: dict,
        x_company_id: Optional[str] = Header(None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(None, alias="X-Company-Mode"),
        _current_user: dict = Depends(require_roles(*staff_manage_roles)),
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            actor = _selected_actor(
                cur, _current_user, "create", x_company_id, x_company_mode,
                staff_manage_roles,
            )
            if actor is None:
                raise HTTPException(status_code=403, detail="Недостаточно прав для документов")
            company_id = actor["companyId"]
            _exact_staff(cur, company_id, staff_id, lock="share")
            signed_at = date_or_none(data.get("signedAt") or data.get("signed_at"))
            expires_at = date_or_none(data.get("expiresAt") or data.get("expires_at"))
            cur.execute(
                """INSERT INTO public.staff_documents
                       (staff_id,doc_type,title,file_url,status,signed_at,
                        expires_at,notes,created_by)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                (
                    staff_id, data.get("docType", "другое"), data.get("title", ""),
                    data.get("fileUrl", "") or None,
                    data.get("status", "действует"), signed_at, expires_at,
                    data.get("notes", ""), _actor_name(actor),
                ),
            )
            new_id = _positive_int(_row_value(cur.fetchone(), "id", 0))
            if new_id is None:
                raise HTTPException(status_code=400, detail="Не удалось создать документ")
            conn.commit()
            return {"id": new_id, "ok": True}
        except BaseException:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()

    @app.delete("/staff-documents/{doc_id}")
    def delete_staff_document(
        doc_id: int,
        x_company_id: Optional[str] = Header(None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(None, alias="X-Company-Mode"),
        _current_user: dict = Depends(require_roles(*staff_manage_roles)),
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            actor = _selected_actor(
                cur, _current_user, "write", x_company_id, x_company_mode,
                staff_manage_roles,
            )
            if actor is None:
                raise HTTPException(status_code=403, detail="Недостаточно прав для документов")
            company_id = actor["companyId"]
            cur.execute(
                """SELECT document.id,document.staff_id
                     FROM public.staff_documents document
                     JOIN public.staff staff_row ON staff_row.id=document.staff_id
                    WHERE document.id=%s AND staff_row.company_id=%s
                      AND staff_row.company_scope_verified IS TRUE
                    FOR UPDATE OF document,staff_row""",
                (doc_id, company_id),
            )
            row = cur.fetchone()
            document_id = _positive_int(_row_value(row, "id", 0))
            staff_id = _positive_int(_row_value(row, "staff_id", 1))
            if document_id is None or staff_id is None:
                raise HTTPException(status_code=404, detail="Документ сотрудника не найден")
            cur.execute(
                "DELETE FROM public.staff_documents WHERE id=%s AND staff_id=%s",
                (document_id, staff_id),
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Документ сотрудника не найден")
            conn.commit()
            return {"ok": True}
        except BaseException:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()
