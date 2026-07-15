import datetime as dt
import json
import uuid

import psycopg2.extras
from fastapi import Depends, Header, HTTPException

from .writer_ownership import resolve_authenticated_lead_owner, resolve_lead_child_owner


CRM_LEAD_TYPES = {
    "client": "Клиент",
    "supplier": "Поставщик",
    "master": "Мастер",
    "brigade": "Бригадир",
    "subcontractor": "Субподрядчик",
}


def _text(value, limit=255):
    return str(value or "").strip()[:limit]


def _num(value):
    try:
        return float(str(value if value is not None else 0).replace(" ", "").replace(",", "."))
    except Exception:
        return 0.0


def _lead_type(value, fallback="Клиент"):
    raw = _text(value, 80)
    return CRM_LEAD_TYPES.get(raw, raw or fallback)


def _bool(value):
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in ("1", "true", "yes", "да")


def _ensure_crm_schema(get_db):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS lead_type VARCHAR(80) DEFAULT 'Клиент';
        ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS counterparty_type VARCHAR(80);
        ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS responsible_name VARCHAR(255);
        ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS next_contact_at VARCHAR(50);
        ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS address TEXT;
        ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS work_type VARCHAR(255);
        ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS area NUMERIC(14,2) DEFAULT 0;
        ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS priority VARCHAR(50) DEFAULT 'Обычный';
        ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS loss_reason TEXT;
        ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS legal_form VARCHAR(80);
        ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS passport_data TEXT;
        ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS inn VARCHAR(50);
        ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS kpp VARCHAR(50);
        ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS ogrn VARCHAR(50);
        ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS legal_address TEXT;
        ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS contract_subject TEXT;
        ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS bank VARCHAR(255);
        ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS bik VARCHAR(50);
        ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS bank_account VARCHAR(50);
        ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS corr_account VARCHAR(50);
        ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS signer_name VARCHAR(255);
        ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS signer_basis VARCHAR(255);
        ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS estimate_id INT;
        ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS document_status VARCHAR(80) DEFAULT 'Не собраны';
        ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS review_status VARCHAR(80) DEFAULT 'Новая';

        CREATE TABLE IF NOT EXISTS crm_lead_documents (
            id SERIAL PRIMARY KEY,
            lead_id INT NOT NULL,
            doc_type VARCHAR(100),
            title VARCHAR(255),
            file_url VARCHAR(500),
            status VARCHAR(80) DEFAULT 'Загружен',
            number VARCHAR(100),
            doc_date VARCHAR(50),
            confidential BOOLEAN DEFAULT FALSE,
            notes TEXT,
            uploaded_by VARCHAR(255),
            created_at TIMESTAMP DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_crm_lead_documents_lead_id ON crm_lead_documents(lead_id);

        CREATE TABLE IF NOT EXISTS crm_lead_tasks (
            id SERIAL PRIMARY KEY,
            lead_id INT NOT NULL,
            title VARCHAR(255) NOT NULL,
            due_date VARCHAR(50),
            status VARCHAR(80) DEFAULT 'Новая',
            assigned_to VARCHAR(255),
            notes TEXT,
            created_by VARCHAR(255),
            created_at TIMESTAMP DEFAULT NOW(),
            completed_at TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_crm_lead_tasks_lead_id ON crm_lead_tasks(lead_id);
    """)
    conn.commit()
    cur.close()
    conn.close()


LEAD_SELECT = """
    id,company_id AS "companyId",name,phone,email,source,budget,notes,stage,created_by AS "createdBy",created_at AS "createdAt",
    project_id AS "projectId",photo_url AS "photoUrl",
    COALESCE(lead_type,'Клиент') AS "leadType",
    COALESCE(counterparty_type,'') AS "counterpartyType",
    COALESCE(responsible_name,'') AS "responsibleName",
    COALESCE(next_contact_at,'') AS "nextContactAt",
    COALESCE(address,'') AS address,
    COALESCE(work_type,'') AS "workType",
    COALESCE(area,0) AS area,
    COALESCE(priority,'Обычный') AS priority,
    COALESCE(loss_reason,'') AS "lossReason",
    COALESCE(legal_form,'') AS "legalForm",
    COALESCE(passport_data,'') AS "passportData",
    COALESCE(inn,'') AS inn,
    COALESCE(kpp,'') AS kpp,
    COALESCE(ogrn,'') AS ogrn,
    COALESCE(legal_address,'') AS "legalAddress",
    COALESCE(contract_subject,'') AS "contractSubject",
    COALESCE(bank,'') AS bank,
    COALESCE(bik,'') AS bik,
    COALESCE(bank_account,'') AS "bankAccount",
    COALESCE(corr_account,'') AS "corrAccount",
    COALESCE(signer_name,'') AS "signerName",
    COALESCE(signer_basis,'') AS "signerBasis",
    estimate_id AS "estimateId",
    COALESCE(document_status,'Не собраны') AS "documentStatus",
    COALESCE(review_status,'Новая') AS "reviewStatus",
    COALESCE((SELECT COUNT(*) FROM crm_lead_documents d
              WHERE d.lead_id=crm_leads.id
                AND d.company_id=crm_leads.company_id
                AND d.project_id IS NOT DISTINCT FROM crm_leads.project_id),0) AS "documentsCount",
    COALESCE((SELECT COUNT(*) FROM crm_lead_tasks t
              WHERE t.lead_id=crm_leads.id
                AND t.company_id=crm_leads.company_id
                AND t.project_id IS NOT DISTINCT FROM crm_leads.project_id
                AND COALESCE(t.status,'')<>'Закрыта'),0) AS "openTasksCount",
    COALESCE((SELECT MIN(NULLIF(t.due_date,'')) FROM crm_lead_tasks t
              WHERE t.lead_id=crm_leads.id
                AND t.company_id=crm_leads.company_id
                AND t.project_id IS NOT DISTINCT FROM crm_leads.project_id
                AND COALESCE(t.status,'')<>'Закрыта'),'') AS "nextTaskDueDate"
"""


def _lead_dict(row):
    data = dict(row or {})
    data["budget"] = float(data.get("budget") or 0)
    data["area"] = float(data.get("area") or 0)
    data["documentsCount"] = int(data.get("documentsCount") or 0)
    data["openTasksCount"] = int(data.get("openTasksCount") or 0)
    return data


def _doc_dict(row):
    data = dict(row or {})
    data["leadId"] = data.pop("lead_id", data.get("leadId", None))
    data["docType"] = data.pop("doc_type", data.get("docType", ""))
    data["fileUrl"] = data.pop("file_url", data.get("fileUrl", ""))
    data["docDate"] = data.pop("doc_date", data.get("docDate", ""))
    data["uploadedBy"] = data.pop("uploaded_by", data.get("uploadedBy", ""))
    data["createdAt"] = str(data.pop("created_at", data.get("createdAt", "")) or "")
    return data


def _task_dict(row):
    data = dict(row or {})
    data["leadId"] = data.pop("lead_id", data.get("leadId", None))
    data["dueDate"] = data.pop("due_date", data.get("dueDate", ""))
    data["assignedTo"] = data.pop("assigned_to", data.get("assignedTo", ""))
    data["createdBy"] = data.pop("created_by", data.get("createdBy", ""))
    data["createdAt"] = str(data.pop("created_at", data.get("createdAt", "")) or "")
    data["completedAt"] = str(data.pop("completed_at", data.get("completedAt", "")) or "")
    return data


def _project_dict(row):
    data = dict(row or {})
    data["budget"] = float(data.get("budget") or 0)
    data["tasks"] = data.get("tasks") or []
    data["pricelistId"] = data.pop("pricelist_id", data.get("pricelistId", None))
    data["archived"] = bool(data.get("archived"))
    data["archivedAt"] = str(data.pop("archived_at", data.get("archivedAt", "")) or "")
    return data


def register_crm_module(app, deps):
    get_db = deps["get_db"]
    require_roles = deps["require_roles"]
    leadership_roles = deps["leadership_roles"]
    log_audit = deps.get("log_audit")
    prepare_user_access_scope = deps.get("prepare_user_access_scope")
    supplier_find_match = deps.get("supplier_find_match")
    supplier_update_missing_fields = deps.get("supplier_update_missing_fields")
    supplier_remember_alias = deps.get("supplier_remember_alias")
    app_public_url = (deps.get("app_public_url") or "").rstrip("/")
    resolve_work_company_context = deps["resolve_work_company_context"]
    effective_company_actors = deps["effective_company_actors"]
    resolve_resource_company_actor = deps["resolve_resource_company_actor"]

    _ensure_crm_schema(get_db)

    crm_access = require_roles(*leadership_roles, "менеджер_crm")
    crm_roles = (*leadership_roles, "менеджер_crm")

    def create_owner(cur, current_user, x_company_id, x_company_mode):
        context = resolve_work_company_context(
            cur,
            current_user,
            None,
            "create",
            x_company_id=x_company_id,
            x_company_mode=x_company_mode,
        )
        return resolve_authenticated_lead_owner(
            context,
            effective_company_actors(current_user, context),
            allowed_roles=crm_roles,
        )

    def readable_company_ids(cur, current_user, x_company_id, x_company_mode):
        context = resolve_work_company_context(
            cur,
            current_user,
            None,
            "read",
            x_company_id=x_company_id,
            x_company_mode=x_company_mode,
        )
        allowed_roles = set(crm_roles)
        company_ids = sorted({
            int(actor.get("companyId") or actor.get("company_id") or 0)
            for actor in effective_company_actors(current_user, context)
            if (actor.get("role") or "") in allowed_roles
            and int(actor.get("companyId") or actor.get("company_id") or 0) > 0
        })
        if not company_ids:
            raise HTTPException(status_code=403, detail="Роль в выбранной компании не позволяет читать CRM")
        return company_ids

    def authorize_owner(cur, current_user, owner, action_mode, x_company_id, x_company_mode):
        resolve_resource_company_actor(
            cur,
            current_user,
            owner["companyId"],
            action_mode,
            x_company_id=x_company_id,
            x_company_mode=x_company_mode,
            allowed_roles=crm_roles,
            forbidden_detail="Роль в выбранной компании не позволяет менять CRM",
        )
        return owner

    def child_owner(cur, current_user, lead, action_mode, x_company_id, x_company_mode):
        return authorize_owner(
            cur,
            current_user,
            resolve_lead_child_owner(lead),
            action_mode,
            x_company_id,
            x_company_mode,
        )

    def fetch_stored_child_owner(cur, table, record_id, not_found_detail):
        if table not in ("crm_lead_documents", "crm_lead_tasks"):
            raise ValueError("Unsupported CRM child table")
        cur.execute(f"""
            SELECT child.id,child.lead_id,child.company_id,child.project_id
              FROM {table} child
              JOIN crm_leads lead
                ON lead.id=child.lead_id
               AND lead.company_id=child.company_id
               AND lead.project_id IS NOT DISTINCT FROM child.project_id
             WHERE child.id=%s
             FOR UPDATE OF child,lead
        """, (record_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=not_found_detail)
        return {
            "companyId": int(row.get("company_id") or 0),
            "projectId": row.get("project_id"),
            "leadId": int(row.get("lead_id") or 0),
        }

    def fetch_lead(cur, lead_id, *, for_update=False):
        lock_sql = " FOR UPDATE" if for_update else ""
        cur.execute("SELECT " + LEAD_SELECT + " FROM crm_leads WHERE id=%s" + lock_sql, (lead_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="CRM-заявка не найдена")
        return _lead_dict(row)

    def fetch_readable_lead(cur, lead_id, company_ids):
        cur.execute(
            "SELECT " + LEAD_SELECT + " FROM crm_leads WHERE id=%s AND company_id = ANY(%s)",
            (lead_id, company_ids),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="CRM-заявка не найдена")
        return _lead_dict(row)

    def company_platform_account_id(cur, company_id):
        cur.execute("SELECT platform_account_id FROM companies WHERE id=%s", (company_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=409, detail="Компания CRM-заявки не найдена")
        return row.get("platform_account_id")

    def validate_company_projects(cur, company_id, project_names):
        requested = sorted({_text(name, 255) for name in (project_names or []) if _text(name, 255)})
        if not requested:
            return
        cur.execute(
            "SELECT name FROM projects WHERE company_id=%s AND name = ANY(%s)",
            (company_id, requested),
        )
        found = {row.get("name") for row in (cur.fetchall() or [])}
        if found != set(requested):
            raise HTTPException(status_code=404, detail="Один из выбранных объектов не найден в компании CRM-заявки")

    def invite_role_for_lead(lead, data):
        requested = _text(data.get("role"), 80)
        if requested:
            return requested
        lead_type = _text(lead.get("leadType"), 80)
        return {
            "Поставщик": "поставщик",
            "Мастер": "мастер",
            "Бригадир": "бригадир",
            "Субподрядчик": "субподрядчик",
            "Клиент": "заказчик",
        }.get(lead_type, "")

    def supplier_id_for_lead(cur, lead, data):
        supplier_payload = {
            **(data or {}),
            "id": None,
            "supplierId": None,
            "supplier_id": None,
            "name": lead.get("name") or "",
            "supplierName": lead.get("name") or "",
            "phone": lead.get("phone") or "",
            "email": lead.get("email") or "",
            "inn": lead.get("inn") or data.get("inn") or "",
            "kpp": lead.get("kpp") or data.get("kpp") or "",
            "ogrn": lead.get("ogrn") or data.get("ogrn") or "",
        }
        if supplier_find_match:
            supplier = supplier_find_match(cur, supplier_payload)
            if supplier:
                return int(supplier.get("id") or 0) or None
        cur.execute("""
            SELECT id FROM suppliers
            WHERE LOWER(COALESCE(name,''))=LOWER(%s)
               OR (%s<>'' AND COALESCE(phone,'')=%s)
               OR (%s<>'' AND LOWER(COALESCE(email,''))=LOWER(%s))
            ORDER BY id LIMIT 1
        """, (lead["name"], lead["phone"], lead["phone"], lead["email"], lead["email"]))
        row = cur.fetchone()
        if not row:
            return None
        return row.get("id") if isinstance(row, dict) else row[0]

    @app.get("/crm/lead-summaries")
    def crm_lead_summaries(
        x_company_id: str = Header(default=None, alias="X-Company-Id"),
        x_company_mode: str = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(crm_access),
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            company_ids = readable_company_ids(cur, current_user, x_company_id, x_company_mode)
            cur.execute(
                "SELECT " + LEAD_SELECT + " FROM crm_leads WHERE company_id = ANY(%s) ORDER BY id DESC",
                (company_ids,),
            )
            return [_lead_dict(row) for row in cur.fetchall()]
        finally:
            cur.close()
            conn.close()

    @app.get("/crm/leads/{lead_id}/details")
    def crm_lead_details(
        lead_id: int,
        x_company_id: str = Header(default=None, alias="X-Company-Id"),
        x_company_mode: str = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(crm_access),
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            company_ids = readable_company_ids(cur, current_user, x_company_id, x_company_mode)
            lead = fetch_readable_lead(cur, lead_id, company_ids)
            owner_params = (lead_id, lead["companyId"], lead.get("projectId"))
            cur.execute(
                """SELECT * FROM crm_lead_documents
                   WHERE lead_id=%s AND company_id=%s AND project_id IS NOT DISTINCT FROM %s
                   ORDER BY created_at DESC,id DESC""",
                owner_params,
            )
            documents = [_doc_dict(row) for row in cur.fetchall()]
            cur.execute(
                """SELECT * FROM crm_lead_tasks
                   WHERE lead_id=%s AND company_id=%s AND project_id IS NOT DISTINCT FROM %s
                   ORDER BY COALESCE(due_date,''),id""",
                owner_params,
            )
            tasks = [_task_dict(row) for row in cur.fetchall()]
            return {"lead": lead, "documents": documents, "tasks": tasks}
        finally:
            cur.close()
            conn.close()

    @app.post("/crm/leads")
    def crm_create_lead(
        data: dict,
        x_company_id: str = Header(default=None, alias="X-Company-Id"),
        x_company_mode: str = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(crm_access),
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            owner = create_owner(cur, current_user, x_company_id, x_company_mode)
            cur.execute("""
                INSERT INTO crm_leads (
                    company_id,name,phone,email,source,budget,notes,stage,created_by,created_at,photo_url,
                    lead_type,counterparty_type,responsible_name,next_contact_at,address,work_type,area,
                    priority,loss_reason,legal_form,passport_data,inn,kpp,ogrn,legal_address,
                    contract_subject,bank,bik,bank_account,corr_account,signer_name,signer_basis,estimate_id,
                    document_status,review_status
                ) VALUES (
                    %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                    %s,%s,%s,%s,%s,%s,%s,
                    %s,%s,%s,%s,%s,%s,%s,%s,
                    %s,%s,%s,%s,%s,%s,%s,%s,
                    %s,%s
                ) RETURNING id
            """, (
                owner["companyId"],
                _text(data.get("name")), _text(data.get("phone"), 80), _text(data.get("email")),
                _text(data.get("source")), _num(data.get("budget")), data.get("notes") or "",
                _text(data.get("stage") or "Новый", 80), current_user.get("name") or "",
                data.get("createdAt") or dt.datetime.utcnow().strftime("%Y-%m-%d"), data.get("photoUrl") or "",
                _lead_type(data.get("leadType")), _text(data.get("counterpartyType"), 80),
                _text(data.get("responsibleName")), _text(data.get("nextContactAt"), 50),
                data.get("address") or "", _text(data.get("workType")), _num(data.get("area")),
                _text(data.get("priority") or "Обычный", 50), data.get("lossReason") or "",
                _text(data.get("legalForm"), 80), data.get("passportData") or "",
                _text(data.get("inn"), 50), _text(data.get("kpp"), 50), _text(data.get("ogrn"), 50),
                data.get("legalAddress") or "", data.get("contractSubject") or "",
                _text(data.get("bank")), _text(data.get("bik"), 50),
                _text(data.get("bankAccount"), 50), _text(data.get("corrAccount"), 50),
                _text(data.get("signerName")), _text(data.get("signerBasis")),
                int(data.get("estimateId") or 0) or None,
                _text(data.get("documentStatus") or "Не собраны", 80),
                _text(data.get("reviewStatus") or "Новая", 80),
            ))
            created = cur.fetchone()
            lead_id = created.get("id") if isinstance(created, dict) else created[0]
            conn.commit()
            if log_audit:
                log_audit(current_user.get("name", ""), current_user.get("role", ""), "create", "crm_lead", lead_id, "Создана CRM-заявка", "")
            return {"ok": True, "id": lead_id}
        except HTTPException:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=400, detail=str(e))
        finally:
            cur.close()
            conn.close()

    @app.put("/crm/leads/{lead_id}")
    def crm_update_lead(
        lead_id: int,
        data: dict,
        x_company_id: str = Header(default=None, alias="X-Company-Id"),
        x_company_mode: str = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(crm_access),
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            lead = fetch_lead(cur, lead_id, for_update=True)
            owner = child_owner(cur, current_user, lead, "update", x_company_id, x_company_mode)
            cur.execute("""
                UPDATE crm_leads SET
                    name=%s,phone=%s,email=%s,source=%s,budget=%s,notes=%s,stage=%s,photo_url=%s,
                    lead_type=%s,counterparty_type=%s,responsible_name=%s,next_contact_at=%s,
                    address=%s,work_type=%s,area=%s,priority=%s,loss_reason=%s,
                    legal_form=%s,passport_data=%s,inn=%s,kpp=%s,ogrn=%s,legal_address=%s,
                    contract_subject=%s,bank=%s,bik=%s,bank_account=%s,corr_account=%s,signer_name=%s,signer_basis=%s,
                    estimate_id=%s,document_status=%s,review_status=%s
                WHERE id=%s AND company_id=%s AND project_id IS NOT DISTINCT FROM %s
            """, (
                _text(data.get("name")), _text(data.get("phone"), 80), _text(data.get("email")),
                _text(data.get("source")), _num(data.get("budget")), data.get("notes") or "",
                _text(data.get("stage") or "Новый", 80), data.get("photoUrl") or "",
                _lead_type(data.get("leadType")), _text(data.get("counterpartyType"), 80),
                _text(data.get("responsibleName")), _text(data.get("nextContactAt"), 50),
                data.get("address") or "", _text(data.get("workType")), _num(data.get("area")),
                _text(data.get("priority") or "Обычный", 50), data.get("lossReason") or "",
                _text(data.get("legalForm"), 80), data.get("passportData") or "",
                _text(data.get("inn"), 50), _text(data.get("kpp"), 50), _text(data.get("ogrn"), 50),
                data.get("legalAddress") or "", data.get("contractSubject") or "",
                _text(data.get("bank")), _text(data.get("bik"), 50),
                _text(data.get("bankAccount"), 50), _text(data.get("corrAccount"), 50),
                _text(data.get("signerName")), _text(data.get("signerBasis")),
                int(data.get("estimateId") or 0) or None,
                _text(data.get("documentStatus") or "Не собраны", 80),
                _text(data.get("reviewStatus") or "Новая", 80),
                lead_id, owner["companyId"], owner["projectId"],
            ))
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="CRM-заявка не найдена")
            conn.commit()
            if log_audit:
                log_audit(current_user.get("name", ""), current_user.get("role", ""), "update", "crm_lead", lead_id, "Обновлена CRM-заявка", "")
            return {"ok": True}
        except HTTPException:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=400, detail=str(e))
        finally:
            cur.close()
            conn.close()

    @app.delete("/crm/leads/{lead_id}")
    def crm_delete_lead(
        lead_id: int,
        x_company_id: str = Header(default=None, alias="X-Company-Id"),
        x_company_mode: str = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(crm_access),
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            lead = fetch_lead(cur, lead_id, for_update=True)
            owner = child_owner(cur, current_user, lead, "delete", x_company_id, x_company_mode)
            owner_params = (lead_id, owner["companyId"], owner["projectId"])
            for table in ("crm_lead_documents", "crm_lead_tasks"):
                cur.execute(f"""
                    SELECT 1 FROM {table}
                     WHERE lead_id=%s
                       AND (company_id IS DISTINCT FROM %s OR project_id IS DISTINCT FROM %s)
                     LIMIT 1
                """, owner_params)
                if cur.fetchone():
                    raise HTTPException(status_code=409, detail="Данные CRM имеют конфликт владельца. Сначала исправьте привязку.")
            cur.execute(
                """DELETE FROM crm_lead_documents
                    WHERE lead_id=%s AND company_id=%s AND project_id IS NOT DISTINCT FROM %s""",
                owner_params,
            )
            cur.execute(
                """DELETE FROM crm_lead_tasks
                    WHERE lead_id=%s AND company_id=%s AND project_id IS NOT DISTINCT FROM %s""",
                owner_params,
            )
            cur.execute(
                """DELETE FROM crm_leads
                    WHERE id=%s AND company_id=%s AND project_id IS NOT DISTINCT FROM %s""",
                owner_params,
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="CRM-заявка не найдена")
            conn.commit()
            return {"ok": True}
        except HTTPException:
            conn.rollback()
            raise
        except Exception as error:
            conn.rollback()
            raise HTTPException(status_code=400, detail=str(error))
        finally:
            cur.close()
            conn.close()

    @app.post("/crm-leads/{lead_id}/create-project")
    @app.post("/crm/leads/{lead_id}/create-project")
    def crm_create_project_from_lead(
        lead_id: int,
        data: dict = None,
        x_company_id: str = Header(default=None, alias="X-Company-Id"),
        x_company_mode: str = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(crm_access),
    ):
        data = data or {}
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            lead = fetch_lead(cur, lead_id, for_update=True)
            owner = child_owner(cur, current_user, lead, "create", x_company_id, x_company_mode)
            if lead.get("projectId"):
                cur.execute("""
                    SELECT id,company_id,name,client,status,budget,deadline,progress,tasks,pricelist_id,
                           COALESCE(archived,false) AS archived,archived_at
                      FROM projects
                     WHERE id=%s AND company_id=%s
                """, (lead.get("projectId"), owner["companyId"]))
                project = cur.fetchone()
                if project:
                    return {"ok": True, "alreadyExists": True, "project": _project_dict(project)}
                raise HTTPException(status_code=409, detail="Объект CRM-заявки не принадлежит её компании")

            owner_params = (lead_id, owner["companyId"], owner["projectId"])
            for table in ("crm_lead_documents", "crm_lead_tasks"):
                cur.execute(f"""
                    SELECT 1 FROM {table}
                     WHERE lead_id=%s
                       AND (company_id IS DISTINCT FROM %s OR project_id IS DISTINCT FROM %s)
                     LIMIT 1
                """, owner_params)
                if cur.fetchone():
                    raise HTTPException(status_code=409, detail="Данные CRM имеют конфликт владельца. Сначала исправьте привязку.")

            project_name = _text(data.get("projectName") or lead.get("name") or ("Заявка #" + str(lead_id)), 255)
            client_name = _text(data.get("client") or lead.get("name") or lead.get("phone") or "", 255)
            if not project_name:
                raise HTTPException(status_code=400, detail="Укажите название объекта")

            cur.execute(
                "SELECT id FROM projects WHERE company_id=%s AND LOWER(name)=LOWER(%s) LIMIT 1",
                (owner["companyId"], project_name),
            )
            if cur.fetchone():
                raise HTTPException(status_code=409, detail="Объект с таким названием уже существует")

            budget = _num(data.get("budget") if data.get("budget") not in (None, "") else lead.get("budget"))
            cur.execute("""
                INSERT INTO projects (company_id,name,client,status,budget,deadline,progress,tasks,pricelist_id,floors,liters)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING id,company_id,name,client,status,budget,deadline,progress,tasks,pricelist_id,
                          COALESCE(archived,false) AS archived,archived_at
            """, (
                owner["companyId"], project_name, client_name, data.get("status") or "Планирование", budget,
                data.get("deadline") or "", 0, [], None, int(data.get("floors") or 1), data.get("liters") or "",
            ))
            project = _project_dict(cur.fetchone())
            source_note = "Создан объект #" + str(project["id"]) + " из CRM-заявки #" + str(lead_id)
            notes = lead.get("notes") or ""
            if source_note not in notes:
                notes = (notes + ("\n\n" if notes else "") + source_note)[:4000]
            for table in ("crm_lead_documents", "crm_lead_tasks"):
                cur.execute(
                    f"""UPDATE {table} SET project_id=%s
                         WHERE lead_id=%s AND company_id=%s AND project_id IS NOT DISTINCT FROM %s""",
                    (project["id"], *owner_params),
                )
            cur.execute("""
                UPDATE crm_leads
                   SET project_id=%s, stage=%s, review_status=%s, notes=%s
                 WHERE id=%s AND company_id=%s AND project_id IS NOT DISTINCT FROM %s
            """, (
                project["id"], data.get("stage") or "Договор", data.get("reviewStatus") or "Передан в объект", notes,
                lead_id, owner["companyId"], owner["projectId"],
            ))
            if cur.rowcount == 0:
                raise HTTPException(status_code=409, detail="CRM-заявка изменилась во время создания объекта")
            conn.commit()
            if log_audit:
                log_audit(
                    current_user.get("name", ""),
                    current_user.get("role", ""),
                    "create",
                    "project",
                    project["id"],
                    "Создан объект из CRM-заявки #" + str(lead_id),
                    project["name"],
                )
            return {"ok": True, "alreadyExists": False, "project": project}
        except HTTPException:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=400, detail=str(e))
        finally:
            cur.close()
            conn.close()

    @app.post("/crm/leads/{lead_id}/documents")
    def crm_create_document(
        lead_id: int,
        data: dict,
        x_company_id: str = Header(default=None, alias="X-Company-Id"),
        x_company_mode: str = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(crm_access),
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            lead = fetch_lead(cur, lead_id, for_update=True)
            owner = child_owner(cur, current_user, lead, "create", x_company_id, x_company_mode)
            cur.execute("""
                INSERT INTO crm_lead_documents (
                    company_id,project_id,lead_id,doc_type,title,file_url,status,number,doc_date,confidential,notes,uploaded_by
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *
            """, (
                owner["companyId"], owner["projectId"], lead_id,
                _text(data.get("docType"), 100), _text(data.get("title")),
                data.get("fileUrl") or "", _text(data.get("status") or "Загружен", 80),
                _text(data.get("number"), 100), _text(data.get("docDate"), 50),
                _bool(data.get("confidential")), data.get("notes") or "", current_user.get("name") or "",
            ))
            row = _doc_dict(cur.fetchone())
            cur.execute(
                """UPDATE crm_leads SET document_status='Есть документы'
                    WHERE id=%s AND company_id=%s AND project_id IS NOT DISTINCT FROM %s""",
                (lead_id, owner["companyId"], owner["projectId"]),
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="CRM-заявка не найдена")
            conn.commit()
            return row
        except HTTPException:
            conn.rollback()
            raise
        except Exception as error:
            conn.rollback()
            raise HTTPException(status_code=400, detail=str(error))
        finally:
            cur.close()
            conn.close()

    @app.put("/crm/documents/{doc_id}")
    def crm_update_document(
        doc_id: int,
        data: dict,
        x_company_id: str = Header(default=None, alias="X-Company-Id"),
        x_company_mode: str = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(crm_access),
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            owner = fetch_stored_child_owner(cur, "crm_lead_documents", doc_id, "Документ CRM не найден")
            authorize_owner(cur, current_user, owner, "update", x_company_id, x_company_mode)
            cur.execute("""
                UPDATE crm_lead_documents SET doc_type=%s,title=%s,file_url=%s,status=%s,number=%s,doc_date=%s,confidential=%s,notes=%s
                WHERE id=%s AND lead_id=%s AND company_id=%s AND project_id IS NOT DISTINCT FROM %s
                RETURNING *
            """, (
                _text(data.get("docType"), 100), _text(data.get("title")), data.get("fileUrl") or "",
                _text(data.get("status") or "Загружен", 80), _text(data.get("number"), 100),
                _text(data.get("docDate"), 50), _bool(data.get("confidential")), data.get("notes") or "",
                doc_id, owner["leadId"], owner["companyId"], owner["projectId"],
            ))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Документ CRM не найден")
            conn.commit()
            return _doc_dict(row)
        except HTTPException:
            conn.rollback()
            raise
        except Exception as error:
            conn.rollback()
            raise HTTPException(status_code=400, detail=str(error))
        finally:
            cur.close()
            conn.close()

    @app.delete("/crm/documents/{doc_id}")
    def crm_delete_document(
        doc_id: int,
        x_company_id: str = Header(default=None, alias="X-Company-Id"),
        x_company_mode: str = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(crm_access),
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            owner = fetch_stored_child_owner(cur, "crm_lead_documents", doc_id, "Документ CRM не найден")
            authorize_owner(cur, current_user, owner, "delete", x_company_id, x_company_mode)
            cur.execute(
                """DELETE FROM crm_lead_documents
                    WHERE id=%s AND lead_id=%s AND company_id=%s AND project_id IS NOT DISTINCT FROM %s""",
                (doc_id, owner["leadId"], owner["companyId"], owner["projectId"]),
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Документ CRM не найден")
            conn.commit()
            return {"ok": True}
        except HTTPException:
            conn.rollback()
            raise
        except Exception as error:
            conn.rollback()
            raise HTTPException(status_code=400, detail=str(error))
        finally:
            cur.close()
            conn.close()

    @app.post("/crm/leads/{lead_id}/tasks")
    def crm_create_task(
        lead_id: int,
        data: dict,
        x_company_id: str = Header(default=None, alias="X-Company-Id"),
        x_company_mode: str = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(crm_access),
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            lead = fetch_lead(cur, lead_id, for_update=True)
            owner = child_owner(cur, current_user, lead, "create", x_company_id, x_company_mode)
            cur.execute("""
                INSERT INTO crm_lead_tasks (company_id,project_id,lead_id,title,due_date,status,assigned_to,notes,created_by)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *
            """, (
                owner["companyId"], owner["projectId"], lead_id,
                _text(data.get("title") or "Следующий шаг"), _text(data.get("dueDate"), 50),
                _text(data.get("status") or "Новая", 80), _text(data.get("assignedTo")),
                data.get("notes") or "", current_user.get("name") or "",
            ))
            row = _task_dict(cur.fetchone())
            conn.commit()
            return row
        except HTTPException:
            conn.rollback()
            raise
        except Exception as error:
            conn.rollback()
            raise HTTPException(status_code=400, detail=str(error))
        finally:
            cur.close()
            conn.close()

    @app.put("/crm/tasks/{task_id}")
    def crm_update_task(
        task_id: int,
        data: dict,
        x_company_id: str = Header(default=None, alias="X-Company-Id"),
        x_company_mode: str = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(crm_access),
    ):
        completed_sql = ",completed_at=NOW()" if data.get("status") == "Закрыта" else ""
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            owner = fetch_stored_child_owner(cur, "crm_lead_tasks", task_id, "Задача CRM не найдена")
            authorize_owner(cur, current_user, owner, "update", x_company_id, x_company_mode)
            cur.execute(f"""
                UPDATE crm_lead_tasks SET title=%s,due_date=%s,status=%s,assigned_to=%s,notes=%s{completed_sql}
                WHERE id=%s AND lead_id=%s AND company_id=%s AND project_id IS NOT DISTINCT FROM %s
                RETURNING *
            """, (
                _text(data.get("title") or "Следующий шаг"), _text(data.get("dueDate"), 50),
                _text(data.get("status") or "Новая", 80), _text(data.get("assignedTo")),
                data.get("notes") or "", task_id, owner["leadId"], owner["companyId"], owner["projectId"],
            ))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Задача CRM не найдена")
            conn.commit()
            return _task_dict(row)
        except HTTPException:
            conn.rollback()
            raise
        except Exception as error:
            conn.rollback()
            raise HTTPException(status_code=400, detail=str(error))
        finally:
            cur.close()
            conn.close()

    @app.delete("/crm/tasks/{task_id}")
    def crm_delete_task(
        task_id: int,
        x_company_id: str = Header(default=None, alias="X-Company-Id"),
        x_company_mode: str = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(crm_access),
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            owner = fetch_stored_child_owner(cur, "crm_lead_tasks", task_id, "Задача CRM не найдена")
            authorize_owner(cur, current_user, owner, "delete", x_company_id, x_company_mode)
            cur.execute(
                """DELETE FROM crm_lead_tasks
                    WHERE id=%s AND lead_id=%s AND company_id=%s AND project_id IS NOT DISTINCT FROM %s""",
                (task_id, owner["leadId"], owner["companyId"], owner["projectId"]),
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Задача CRM не найдена")
            conn.commit()
            return {"ok": True}
        except HTTPException:
            conn.rollback()
            raise
        except Exception as error:
            conn.rollback()
            raise HTTPException(status_code=400, detail=str(error))
        finally:
            cur.close()
            conn.close()

    @app.post("/crm/leads/{lead_id}/approve-supplier")
    def crm_approve_supplier(
        lead_id: int,
        data: dict = None,
        x_company_id: str = Header(default=None, alias="X-Company-Id"),
        x_company_mode: str = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(crm_access),
    ):
        data = data or {}
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            lead = fetch_lead(cur, lead_id, for_update=True)
            owner = child_owner(cur, current_user, lead, "update", x_company_id, x_company_mode)
            supplier_payload = {
                **(data or {}),
                "id": None,
                "supplierId": None,
                "supplier_id": None,
                "name": lead.get("name") or "",
                "supplierName": lead.get("name") or "",
                "phone": lead.get("phone") or "",
                "email": lead.get("email") or "",
                "specialization": lead.get("workType") or data.get("specialization") or "",
                "category": data.get("category") or lead.get("counterpartyType") or lead.get("workType") or "Прочее",
                "status": "На проверке",
                "inn": lead.get("inn") or data.get("inn") or "",
                "kpp": lead.get("kpp") or data.get("kpp") or "",
                "ogrn": lead.get("ogrn") or data.get("ogrn") or "",
                "legalAddress": lead.get("legalAddress") or data.get("legalAddress") or "",
                "actualAddress": lead.get("address") or data.get("actualAddress") or "",
                "bank": lead.get("bank") or data.get("bank") or "",
                "bik": lead.get("bik") or data.get("bik") or "",
                "bankAccount": lead.get("bankAccount") or data.get("bankAccount") or "",
                "corrAccount": lead.get("corrAccount") or data.get("corrAccount") or "",
                "signerName": lead.get("signerName") or data.get("signerName") or "",
                "signerBasis": lead.get("signerBasis") or data.get("signerBasis") or "",
                "notes": ("Создан из CRM-заявки #" + str(lead_id) + "\n\n" + (lead.get("notes") or ""))[:4000],
            }
            supplier = supplier_find_match(cur, supplier_payload) if supplier_find_match else None
            if supplier and supplier_update_missing_fields:
                supplier_update_missing_fields(cur, supplier.get("id"), supplier_payload)
                if supplier_remember_alias:
                    supplier_remember_alias(cur, supplier.get("id"), supplier_payload, "crm_supplier")
                cur.execute("SELECT * FROM suppliers WHERE id=%s", (supplier.get("id"),))
                supplier = cur.fetchone()
            if not supplier:
                cur.execute("""
                    SELECT * FROM suppliers
                    WHERE LOWER(COALESCE(name,''))=LOWER(%s)
                       OR (%s<>'' AND COALESCE(phone,'')=%s)
                       OR (%s<>'' AND LOWER(COALESCE(email,''))=LOWER(%s))
                    ORDER BY id LIMIT 1
                """, (lead["name"], lead["phone"], lead["phone"], lead["email"], lead["email"]))
                supplier = cur.fetchone()
            if not supplier:
                cur.execute("""
                    INSERT INTO suppliers (
                        name,phone,email,specialization,category,status,inn,kpp,ogrn,legal_address,
                        actual_address,bank,bik,account,kor_account,director_name,director_position,notes
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    RETURNING *
                """, (
                    lead["name"], lead["phone"], lead["email"], lead.get("workType") or data.get("specialization") or "",
                    data.get("category") or lead.get("counterpartyType") or lead.get("workType") or "Прочее",
                    "На проверке", lead.get("inn"), lead.get("kpp"), lead.get("ogrn"), lead.get("legalAddress"),
                    lead.get("address"), lead.get("bank"), lead.get("bik"), lead.get("bankAccount"),
                    lead.get("corrAccount"), lead.get("signerName"), lead.get("signerBasis"),
                    ("Создан из CRM-заявки #" + str(lead_id) + "\n\n" + (lead.get("notes") or ""))[:4000],
                ))
                supplier = cur.fetchone()
                if supplier_remember_alias:
                    supplier_remember_alias(cur, supplier["id"], supplier_payload, "crm_supplier")
            cur.execute("""
                UPDATE crm_leads
                   SET lead_type='Поставщик', review_status='Одобрен как поставщик',
                       stage='Одобрен как поставщик', document_status=COALESCE(document_status,'Не собраны')
                 WHERE id=%s AND company_id=%s AND project_id IS NOT DISTINCT FROM %s
            """, (lead_id, owner["companyId"], owner["projectId"]))
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="CRM-заявка не найдена")
            conn.commit()
            if log_audit:
                log_audit(current_user.get("name", ""), current_user.get("role", ""), "create", "supplier", supplier["id"], "Поставщик создан/связан из CRM-заявки #" + str(lead_id), "")
            return {"ok": True, "supplier": dict(supplier), "nextAction": "send_supplier_invite"}
        except HTTPException:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=400, detail=str(e))
        finally:
            cur.close()
            conn.close()

    @app.post("/crm/leads/{lead_id}/approve-worker")
    def crm_approve_worker(
        lead_id: int,
        data: dict = None,
        x_company_id: str = Header(default=None, alias="X-Company-Id"),
        x_company_mode: str = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(crm_access),
    ):
        data = data or {}
        role = _text(data.get("role") or "", 80)
        if role not in ("мастер", "бригадир", "субподрядчик"):
            raise HTTPException(status_code=400, detail="Укажите роль: мастер, бригадир или субподрядчик")
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            lead = fetch_lead(cur, lead_id, for_update=True)
            owner = child_owner(cur, current_user, lead, "update", x_company_id, x_company_mode)
            worker_project_name = _text(data.get("projectName"), 255)
            validate_company_projects(cur, owner["companyId"], [worker_project_name])
            cur.execute("""
                SELECT * FROM staff
                WHERE company_id=%s AND (
                       LOWER(COALESCE(name,''))=LOWER(%s)
                   OR (%s<>'' AND COALESCE(phone,'')=%s)
                   OR (%s<>'' AND LOWER(COALESCE(email_personal,''))=LOWER(%s))
                )
                ORDER BY id LIMIT 1
            """, (owner["companyId"], lead["name"], lead["phone"], lead["phone"], lead["email"], lead["email"]))
            staff = cur.fetchone()
            if not staff:
                cur.execute("""
                    INSERT INTO staff (
                        company_id,name,role,phone,salary,project,pay_type,email_personal,address,
                        inn,specialization,category,employment_type,status,bank_account,bank_name,
                        bank_bik,bank_corr,notes
                    ) VALUES (%s,%s,%s,%s,0,%s,'сдельная',%s,%s,%s,%s,%s,%s,'На проверке',%s,%s,%s,%s,%s)
                    RETURNING *
                """, (
                    owner["companyId"], lead["name"], role, lead["phone"], worker_project_name,
                    lead["email"], lead.get("address"), lead.get("inn"), lead.get("workType"),
                    lead.get("counterpartyType"), lead.get("legalForm"), lead.get("bankAccount"),
                    lead.get("bank"), lead.get("bik"), lead.get("corrAccount"),
                    ("Создан из CRM-заявки #" + str(lead_id) + "\n\n" + (lead.get("notes") or ""))[:4000],
                ))
                staff = cur.fetchone()
            cur.execute("""
                UPDATE crm_leads
                   SET lead_type=%s, review_status='Одобрен как исполнитель', stage='Одобрен как исполнитель'
                 WHERE id=%s AND company_id=%s AND project_id IS NOT DISTINCT FROM %s
            """, (
                "Бригадир" if role == "бригадир" else ("Субподрядчик" if role == "субподрядчик" else "Мастер"),
                lead_id, owner["companyId"], owner["projectId"],
            ))
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="CRM-заявка не найдена")
            conn.commit()
            if log_audit:
                log_audit(current_user.get("name", ""), current_user.get("role", ""), "create", "staff", staff["id"], "Исполнитель создан/связан из CRM-заявки #" + str(lead_id), staff.get("project") or "")
            return {"ok": True, "staff": dict(staff), "nextAction": "send_worker_invite"}
        except HTTPException:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=400, detail=str(e))
        finally:
            cur.close()
            conn.close()

    @app.post("/crm/leads/{lead_id}/create-invite")
    def crm_create_invite(
        lead_id: int,
        data: dict = None,
        x_company_id: str = Header(default=None, alias="X-Company-Id"),
        x_company_mode: str = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(crm_access),
    ):
        data = data or {}
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            lead = fetch_lead(cur, lead_id, for_update=True)
            owner = child_owner(cur, current_user, lead, "update", x_company_id, x_company_mode)
            platform_account_id = company_platform_account_id(cur, owner["companyId"])
            role = invite_role_for_lead(lead, data)
            if role not in ("поставщик", "мастер", "бригадир", "субподрядчик", "заказчик"):
                raise HTTPException(status_code=400, detail="Для этой заявки нельзя создать приглашение без роли")
            project_name = _text(data.get("projectName") or data.get("project_name") or "", 255)
            assigned_projects = data.get("assignedProjects") or ([project_name] if project_name else [])
            assigned_packages = data.get("assignedPackages") or []
            if prepare_user_access_scope:
                assigned_projects, assigned_packages = prepare_user_access_scope(
                    cur, role, project_name, assigned_projects, assigned_packages,
                )
            validate_company_projects(
                cur,
                owner["companyId"],
                [project_name, *assigned_projects],
            )
            supplier_id = supplier_id_for_lead(cur, lead, data) if role == "поставщик" else None
            expires_in_days = int(data.get("expiresInDays") or 14)
            expires_at = dt.datetime.now() + dt.timedelta(days=expires_in_days)
            code = str(uuid.uuid4())[:8].upper()
            cur.execute("""
                INSERT INTO invite_codes (
                    code,role,supplier_id,preset_name,preset_category,created_by,expires_at,
                    project_name,assigned_projects,assigned_packages,company_id,platform_account_id
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s)
                RETURNING *
            """, (
                code, role, supplier_id, lead.get("name") or "",
                data.get("presetCategory") or lead.get("counterpartyType") or lead.get("workType") or "",
                current_user.get("name") or "", expires_at, project_name,
                json.dumps(assigned_projects, ensure_ascii=False),
                json.dumps(assigned_packages, ensure_ascii=False),
                owner["companyId"], platform_account_id,
            ))
            invite = dict(cur.fetchone())
            cur.execute("""
                UPDATE crm_leads
                   SET review_status=%s,
                       notes=LEFT(COALESCE(notes,'') || %s, 4000)
                 WHERE id=%s AND company_id=%s AND project_id IS NOT DISTINCT FROM %s
            """, (
                "Приглашение создано",
                "\n\nСоздано приглашение " + role + ": " + code,
                lead_id, owner["companyId"], owner["projectId"],
            ))
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="CRM-заявка не найдена")
            conn.commit()
            link = (app_public_url or "").rstrip("/") + "/?invite=" + code if app_public_url else "/?invite=" + code
            if log_audit:
                log_audit(current_user.get("name", ""), current_user.get("role", ""), "create", "invite_code", invite["id"], "Создано приглашение из CRM-заявки #" + str(lead_id), project_name)
            return {"ok": True, "invite": invite, "link": link}
        except HTTPException:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=400, detail=str(e))
        finally:
            cur.close()
            conn.close()

    @app.post("/crm/leads/{lead_id}/transfer-documents-to-project")
    def crm_transfer_documents_to_project(
        lead_id: int,
        data: dict = None,
        x_company_id: str = Header(default=None, alias="X-Company-Id"),
        x_company_mode: str = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(crm_access),
    ):
        data = data or {}
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            lead = fetch_lead(cur, lead_id, for_update=True)
            owner = child_owner(cur, current_user, lead, "update", x_company_id, x_company_mode)
            project_name = _text(data.get("projectName"), 255)
            if project_name:
                cur.execute(
                    "SELECT id,name,company_id FROM projects WHERE name=%s AND company_id=%s LIMIT 1",
                    (project_name, owner["companyId"]),
                )
            elif lead.get("projectId"):
                cur.execute(
                    "SELECT id,name,company_id FROM projects WHERE id=%s AND company_id=%s LIMIT 1",
                    (lead.get("projectId"), owner["companyId"]),
                )
            else:
                raise HTTPException(status_code=400, detail="Сначала укажите или создайте объект")
            project = cur.fetchone()
            if not project:
                raise HTTPException(status_code=404, detail="Объект не найден")
            project_name = project.get("name") or ""
            raw_doc_ids = data.get("documentIds")
            if raw_doc_ids is not None and not isinstance(raw_doc_ids, list):
                raise HTTPException(status_code=400, detail="documentIds должен быть списком")
            doc_ids = raw_doc_ids or []
            normalized_doc_ids = []
            for raw_id in doc_ids:
                try:
                    doc_id = int(raw_id)
                except (TypeError, ValueError):
                    raise HTTPException(status_code=400, detail="documentIds должен содержать целые положительные ID")
                if doc_id <= 0:
                    raise HTTPException(status_code=400, detail="documentIds должен содержать целые положительные ID")
                if doc_id not in normalized_doc_ids:
                    normalized_doc_ids.append(doc_id)
            params = [lead_id, owner["companyId"], owner["projectId"]]
            where = "lead_id=%s AND company_id=%s AND project_id IS NOT DISTINCT FROM %s"
            if doc_ids:
                where += " AND id = ANY(%s)"
                params.append(normalized_doc_ids)
            cur.execute("SELECT * FROM crm_lead_documents WHERE " + where + " ORDER BY id FOR UPDATE", tuple(params))
            docs = cur.fetchall()
            if normalized_doc_ids and {int(doc.get("id") or 0) for doc in docs} != set(normalized_doc_ids):
                raise HTTPException(status_code=404, detail="Один из документов не найден в CRM-заявке")
            created = []
            skipped = []
            side = data.get("side") or ("customer" if lead.get("leadType") == "Клиент" else "contractor")
            for doc in docs:
                file_url = doc.get("file_url") or ""
                doc_type = doc.get("doc_type") or ""
                cur.execute("""
                    SELECT id FROM project_documents
                    WHERE project_name=%s AND COALESCE(scan_url,'')=%s AND COALESCE(doc_type,'')=%s
                    LIMIT 1
                """, (project_name, file_url, doc_type))
                existing = cur.fetchone()
                if existing:
                    skipped.append(existing.get("id"))
                    continue
                cur.execute("""
                    INSERT INTO project_documents (
                        project_name,side,doc_type,number,doc_date,counterparty,sign_status,scan_url,amount,notes,uploaded_by
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
                """, (
                    project_name, side, doc_type, doc.get("number") or "",
                    doc.get("doc_date") or None, lead.get("name") or "",
                    doc.get("status") or "Загружен", file_url, lead.get("budget") or 0,
                    ("Передано из CRM-заявки #" + str(lead_id) + ". " + (doc.get("notes") or ""))[:4000],
                    current_user.get("name") or "",
                ))
                project_doc_id = cur.fetchone()["id"]
                created.append(project_doc_id)
                cur.execute(
                    """UPDATE crm_lead_documents SET status='Передан в объект'
                        WHERE id=%s AND lead_id=%s AND company_id=%s AND project_id IS NOT DISTINCT FROM %s""",
                    (doc.get("id"), lead_id, owner["companyId"], owner["projectId"]),
                )
                if cur.rowcount == 0:
                    raise HTTPException(status_code=404, detail="Документ CRM не найден")
            cur.execute("""
                UPDATE crm_leads SET document_status=%s
                 WHERE id=%s AND company_id=%s AND project_id IS NOT DISTINCT FROM %s
            """, (
                "Переданы в объект" if created else lead.get("documentStatus") or "Есть документы",
                lead_id, owner["companyId"], owner["projectId"],
            ))
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="CRM-заявка не найдена")
            conn.commit()
            if log_audit:
                log_audit(current_user.get("name", ""), current_user.get("role", ""), "create", "project_document", created[0] if created else None, "CRM-документы переданы в объект из заявки #" + str(lead_id), project_name)
            return {"ok": True, "created": created, "skipped": skipped, "projectName": project_name}
        except HTTPException:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=400, detail=str(e))
        finally:
            cur.close()
            conn.close()
