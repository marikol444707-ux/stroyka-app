"""Staff directory routes.

Extracted verbatim from backend/main.py (Task 13.1, slice 39):
the seven staff routes with their column maps, sanitizer, access
provisioning (creates/updates the linked user account) and the
fire-with-deactivation flow that disables user logins and revokes
sessions. Shared access-scope validation stays in main.py and is
injected; password hashing and session revocation come from the
auth module.
"""

import json

import psycopg2.extras
from fastapi import Depends, HTTPException
from pydantic import BaseModel
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
    assignedProjects: list[str] = []
    assignedPackages: list[str] = []


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
        signature_url, notes"""
    STAFF_PLACEHOLDERS = ",".join(["%s"] * 37)

    STAFF_ACCESS_ROLES = (
        "директор", "зам_директора", "бухгалтер", "прораб", "главный_инженер",
        "сметчик", "мастер", "субподрядчик", "бригадир", "кладовщик", "снабженец",
        "технадзор", "стройконтроль", "менеджер_crm",
    )

    def _sync_staff_access(cur, s: StaffModel):
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
        project_name = (s.project or "").strip()
        project_id = None
        if project_name:
            cur.execute("SELECT id FROM projects WHERE name=%s LIMIT 1", (project_name,))
            project_row = cur.fetchone()
            if project_row:
                project_id = project_row.get("id") if isinstance(project_row, dict) else project_row[0]
        assigned_projects, assigned_packages = prepare_user_access_scope(cur, role, project_name, assigned_projects, assigned_packages)

        cur.execute("SELECT id FROM users WHERE LOWER(email)=LOWER(%s) LIMIT 1", (email,))
        existing = cur.fetchone()
        user_id = existing.get("id") if isinstance(existing, dict) and existing else (existing[0] if existing else None)
        full_name = (s.name or "Сотрудник").strip()
        if user_id:
            if password:
                cur.execute("""
                    UPDATE users
                       SET name=%s, email=%s, password=%s, role=%s, project_id=%s, project_name=%s,
                           assigned_projects=%s::jsonb, assigned_packages=%s::jsonb,
                           active=TRUE, failed_login_count=0, locked_until=NULL
                     WHERE id=%s
                """, (full_name, email, hash_password(password), role, project_id, project_name,
                      json.dumps(assigned_projects), json.dumps(assigned_packages), user_id))
                action = "password_updated"
            else:
                cur.execute("""
                    UPDATE users
                       SET name=%s, email=%s, role=%s, project_id=%s, project_name=%s,
                           assigned_projects=%s::jsonb, assigned_packages=%s::jsonb,
                           active=TRUE, locked_until=NULL
                     WHERE id=%s
                """, (full_name, email, role, project_id, project_name,
                      json.dumps(assigned_projects), json.dumps(assigned_packages), user_id))
                action = "updated"
        else:
            if not password:
                raise HTTPException(status_code=400, detail="Для нового доступа сотрудника нужен пароль")
            cur.execute("""
                INSERT INTO users (name,email,password,role,project_id,project_name,assigned_projects,assigned_packages,active)
                VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,TRUE)
                RETURNING id
            """, (full_name, email, hash_password(password), role, project_id, project_name,
                  json.dumps(assigned_projects), json.dumps(assigned_packages)))
            new_row = cur.fetchone()
            user_id = new_row.get("id") if isinstance(new_row, dict) else new_row[0]
            action = "created"
        return {
            "id": user_id,
            "email": email,
            "role": role,
            "action": action,
            "assignedProjects": assigned_projects,
            "assignedPackages": assigned_packages,
        }

    @app.get("/staff")
    def get_staff(current_user: dict = Depends(get_current_user)):
        if current_user.get("role") not in staff_view_roles:
            return []
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        role = current_user.get("role")
        if role in ("прораб", "главный_инженер") and role not in staff_manage_roles:
            projects = user_project_names(current_user)
            if not projects:
                cur.close(); conn.close()
                return []
            cur.execute("SELECT " + STAFF_COLUMNS + " FROM staff WHERE project = ANY(%s) ORDER BY id", (projects,))
        else:
            cur.execute("SELECT " + STAFF_COLUMNS + " FROM staff ORDER BY id")
        rows = cur.fetchall()
        conn.close()
        result = []
        for r in rows:
            d = dict(r)
            if role in ("прораб", "главный_инженер") and role not in staff_manage_roles:
                d = _sanitize_staff_for_project_roles(d)
            for k in ("birthDate", "passportIssuedDate", "hiredDate", "firedDate"):
                d[k] = str(d[k]) if d.get(k) else ""
            for k in list(d.keys()):
                if d[k] is None:
                    d[k] = ""
            result.append(d)
        return result

    @app.post("/staff")
    def create_staff(s: StaffModel, _current_user: dict = Depends(require_roles(*staff_manage_roles))):
        conn = get_db()
        cur = conn.cursor()
        try:
            cur.execute("INSERT INTO staff (" + STAFF_INSERT_COLS + ") VALUES (" + STAFF_PLACEHOLDERS + ") RETURNING id", _staff_tuple(s))
            new_id = cur.fetchone()[0]
            access = _sync_staff_access(cur, s)
            conn.commit()
            log_audit(
                _current_user.get("name", ""),
                _current_user.get("role", ""),
                "create",
                "staff",
                new_id,
                ("Создан сотрудник: " + str(s.name or "") + ", роль " + str(s.role or ""))[:250],
                s.project or "",
            )
            return {"id": new_id, "ok": True, "access": access}
        except HTTPException:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=400, detail=str(e))
        finally:
            cur.close()
            conn.close()

    @app.put("/staff/{id}")
    def update_staff(id: int, s: StaffModel, _current_user: dict = Depends(require_roles(*staff_manage_roles))):
        conn = get_db()
        cur = conn.cursor()
        try:
            cur.execute("""UPDATE staff SET name=%s, role=%s, phone=%s, salary=%s, project=%s, pay_type=%s,
                last_name=%s, first_name=%s, middle_name=%s, birth_date=%s, citizenship=%s, address=%s, photo_url=%s,
                email_work=%s, email_personal=%s, phone_extra=%s,
                passport_series=%s, passport_number=%s, passport_issued_by=%s, passport_issued_date=%s,
                inn=%s, snils=%s, specialization=%s, category=%s,
                employment_type=%s, hired_date=%s, fired_date=%s, status=%s, brigade=%s,
                bank_account=%s, bank_name=%s, bank_bik=%s, bank_corr=%s, ogrnip=%s, card_number=%s,
                signature_url=%s, notes=%s WHERE id=%s""", _staff_tuple(s) + (id,))
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Сотрудник не найден")
            access = _sync_staff_access(cur, s)
            conn.commit()
            log_audit(
                _current_user.get("name", ""),
                _current_user.get("role", ""),
                "update",
                "staff",
                id,
                ("Обновлен сотрудник: " + str(s.name or "") + ", роль " + str(s.role or ""))[:250],
                s.project or "",
            )
            return {"ok": True, "access": access}
        except HTTPException:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=400, detail=str(e))
        finally:
            cur.close()
            conn.close()

    @app.delete("/staff/{id}")
    def delete_staff(id: int, _current_user: dict = Depends(require_roles(*staff_manage_roles))):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            cur.execute("SELECT name,role,COALESCE(project,'') AS project,email_work,email_personal FROM staff WHERE id=%s", (id,))
            staff_row = cur.fetchone()
            if not staff_row:
                conn.rollback()
                raise HTTPException(status_code=404, detail="Сотрудник не найден")
            emails = sorted(set([
                str(staff_row.get("email_work") or "").strip().lower(),
                str(staff_row.get("email_personal") or "").strip().lower(),
            ]) - {""})
            cur.execute("""
                UPDATE staff
                   SET status='Уволен',
                       fired_date=COALESCE(fired_date, CURRENT_DATE)
                 WHERE id=%s
            """, (id,))
            disabled_users = 0
            if emails:
                cur.execute("""
                    UPDATE users
                       SET active=FALSE,
                           assigned_projects='[]'::jsonb,
                           assigned_packages='[]'::jsonb,
                           locked_until=NULL
                     WHERE LOWER(COALESCE(email,'')) = ANY(%s)
                     RETURNING id
                """, (emails,))
                disabled_user_ids = [row.get("id") for row in cur.fetchall()]
                disabled_users = len(disabled_user_ids)
                for user_id in disabled_user_ids:
                    _revoke_user_sessions(cur, user_id)
            conn.commit()
            log_audit(
                _current_user.get("name", ""),
                _current_user.get("role", ""),
                "deactivate",
                "staff",
                id,
                ("Сотрудник уволен/отключен: " + str(staff_row.get("name") or "") + ", роль " + str(staff_row.get("role") or ""))[:250],
                staff_row.get("project") or "",
            )
            return {"ok": True, "status": "Уволен", "disabledUsers": disabled_users}
        except HTTPException:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=400, detail=str(e))
        finally:
            cur.close()
            conn.close()

    @app.get("/staff/{staff_id}/profile")
    def get_staff_profile(staff_id: int, _current_user: dict = Depends(require_roles(*staff_view_roles))):
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT id, name, COALESCE(project,'') FROM staff WHERE id=%s", (staff_id,))
        row = cur.fetchone()
        if not row:
            cur.close(); conn.close()
            raise HTTPException(status_code=404, detail="Сотрудник не найден")
        staff_name = row[1] or ""
        staff_project = row[2] or ""
        allowed_staff_projects = None
        if _current_user.get("role") not in staff_full_view_roles:
            allowed_staff_projects = user_project_names(_current_user)
            if staff_project not in allowed_staff_projects:
                cur.close(); conn.close()
                raise HTTPException(status_code=403, detail="Нет доступа к карточке сотрудника этого объекта")

        if _current_user.get("role") in staff_full_view_roles:
            cur.execute("SELECT id, doc_type, title, file_url, status, signed_at, expires_at, notes, created_at FROM staff_documents WHERE staff_id=%s ORDER BY id DESC", (staff_id,))
            custom = [{"id": r[0], "docType": r[1], "title": r[2] or "", "fileUrl": r[3] or "", "status": r[4] or "", "signedAt": str(r[5]) if r[5] else "", "expiresAt": str(r[6]) if r[6] else "", "notes": r[7] or "", "createdAt": str(r[8])} for r in cur.fetchall()]
        else:
            custom = []

        # Match user by name (legacy linkage)
        cur.execute("SELECT id FROM users WHERE name=%s LIMIT 1", (staff_name,))
        u = cur.fetchone()
        user_id = u[0] if u else None

        contracts_list = []
        if user_id is not None:
            if allowed_staff_projects is None:
                cur.execute("SELECT id, contract_number, project, start_date, end_date FROM contracts WHERE master_id=%s ORDER BY id DESC", (user_id,))
            else:
                cur.execute("SELECT id, contract_number, project, start_date, end_date FROM contracts WHERE master_id=%s AND project = ANY(%s) ORDER BY id DESC", (user_id, allowed_staff_projects))
            for r in cur.fetchall():
                contracts_list.append({"id": r[0], "contractNumber": r[1] or "", "project": r[2] or "", "startDate": str(r[3]) if r[3] else "", "endDate": str(r[4]) if r[4] else "", "signedAt": "", "status": ""})

        acts_list = []
        if user_id is not None:
            if allowed_staff_projects is None:
                cur.execute("SELECT id, project, COALESCE(work_package,'') as work_package, period_start, period_end, total_amount, paid_amount, status FROM interim_acts WHERE master_id=%s ORDER BY id DESC", (user_id,))
            else:
                cur.execute("SELECT id, project, COALESCE(work_package,'') as work_package, period_start, period_end, total_amount, paid_amount, status FROM interim_acts WHERE master_id=%s AND project = ANY(%s) ORDER BY id DESC", (user_id, allowed_staff_projects))
            for r in cur.fetchall():
                acts_list.append({"id": r[0], "actNumber": str(r[0]), "project": r[1] or "", "workPackage": r[2] or "", "periodFrom": str(r[3]) if r[3] else "", "periodTo": str(r[4]) if r[4] else "", "totalAmount": float(r[5] or 0), "paidAmount": float(r[6] or 0), "status": r[7] or "", "createdAt": ""})

        pd_consents = []
        if user_id is not None and _current_user.get("role") in staff_full_view_roles:
            cur.execute("SELECT id, signed_at, scan_url, uploaded_by FROM pd_consents WHERE user_id=%s ORDER BY id DESC", (user_id,))
            for r in cur.fetchall():
                pd_consents.append({"id": r[0], "signedAt": r[1] or "", "scanUrl": r[2] or "", "uploadedBy": r[3] or ""})

        tb_entries = []
        if allowed_staff_projects is None:
            cur.execute("SELECT id, project_name, instructor, instruction_type, date FROM tb_journal WHERE master_name=%s ORDER BY id DESC LIMIT 20", (staff_name,))
        else:
            cur.execute("SELECT id, project_name, instructor, instruction_type, date FROM tb_journal WHERE master_name=%s AND project_name = ANY(%s) ORDER BY id DESC LIMIT 20", (staff_name, allowed_staff_projects))
        for r in cur.fetchall():
            tb_entries.append({"id": r[0], "projectName": r[1] or "", "instructor": r[2] or "", "instructionType": r[3] or "", "date": str(r[4]) if r[4] else ""})

        works = []
        if allowed_staff_projects is None:
            cur.execute("SELECT project, description, quantity, unit, total, date, status FROM work_journal WHERE master_name=%s ORDER BY id DESC LIMIT 50", (staff_name,))
        else:
            cur.execute("SELECT project, description, quantity, unit, total, date, status FROM work_journal WHERE master_name=%s AND project = ANY(%s) ORDER BY id DESC LIMIT 50", (staff_name, allowed_staff_projects))
        for r in cur.fetchall():
            works.append({"project": r[0] or "", "description": r[1] or "", "quantity": float(r[2] or 0), "unit": r[3] or "", "total": float(r[4] or 0), "date": str(r[5]) if r[5] else "", "status": r[6] or ""})

        cur.close(); conn.close()
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

    @app.post("/staff/{staff_id}/documents")
    def add_staff_document(staff_id: int, data: dict, _current_user: dict = Depends(require_roles(*staff_manage_roles))):
        conn = get_db()
        cur = conn.cursor()
        signed_at = date_or_none(data.get("signedAt") or data.get("signed_at"))
        expires_at = date_or_none(data.get("expiresAt") or data.get("expires_at"))
        cur.execute("""INSERT INTO staff_documents (staff_id, doc_type, title, file_url, status, signed_at, expires_at, notes, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
            (staff_id, data.get("docType","другое"), data.get("title",""), data.get("fileUrl","") or None,
             data.get("status","действует"), signed_at, expires_at,
             data.get("notes",""), data.get("createdBy","")))
        new_id = cur.fetchone()[0]
        conn.commit(); cur.close(); conn.close()
        return {"id": new_id, "ok": True}

    @app.delete("/staff-documents/{doc_id}")
    def delete_staff_document(doc_id: int, _current_user: dict = Depends(require_roles(*staff_manage_roles))):
        conn = get_db()
        cur = conn.cursor()
        cur.execute("DELETE FROM staff_documents WHERE id=%s", (doc_id,))
        conn.commit(); cur.close(); conn.close()
        return {"ok": True}
