#!/usr/bin/env python3
import base64
import hashlib
import hmac
import json
import os
import secrets
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import psycopg2
import psycopg2.extras


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / "backend" / ".env"
BASE_URL = os.getenv("BASE_URL", "https://stroyka26.pro").rstrip("/")
RUN_ID = uuid.uuid4().hex[:8]
PREFIX = f"CODEX PLATFORM CRM SMOKE {RUN_ID}"
SYSTEM_EMAIL = f"platform-crm-system-{RUN_ID}@stroyka.local"
CRM_EMAIL = f"platform-crm-manager-{RUN_ID}@stroyka.local"
PLATFORM_ROLE_EMAILS = {
    "platform_admin": f"platform-crm-admin-{RUN_ID}@stroyka.local",
    "platform_support": f"platform-crm-support-{RUN_ID}@stroyka.local",
    "billing_admin": f"platform-crm-billing-{RUN_ID}@stroyka.local",
}
PROJECT_NAME = f"{PREFIX} Project"
PROJECT_CREATE_NAME = f"{PREFIX} Created Project"


def load_env():
    values = {}
    if ENV_PATH.exists():
        for raw in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


ENV = load_env()


def env_value(name, default=""):
    return os.getenv(name) or ENV.get(name, default)


def db_config():
    return {
        "dbname": env_value("DB_NAME", "stroyka"),
        "user": env_value("DB_USER", "stroyka"),
        "password": env_value("DB_PASSWORD", "password123"),
        "host": env_value("DB_HOST", "localhost"),
        "port": env_value("DB_PORT", "5432"),
    }


def db_conn():
    return psycopg2.connect(**db_config())


def hash_password(password):
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 260000).hex()
    return f"pbkdf2_sha256$260000${salt}${digest}"


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def auth_token_for(user: dict) -> str:
    payload = {
        "id": user.get("id"),
        "email": user.get("email") or "",
        "role": user.get("role") or "",
        "name": user.get("name") or "",
        "exp": int(time.time()) + 3600,
    }
    body = b64url(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    secret = env_value("AUTH_SECRET", "change-me")
    sig = hmac.new(secret.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).digest()
    return body + "." + b64url(sig)


def api_json(method, path, token=None, data=None, expected=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data, ensure_ascii=False).encode("utf-8") if data is not None else None
    req = urllib.request.Request(BASE_URL + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=40) as resp:
            status = resp.status
            text = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        status = exc.code
        text = exc.read().decode("utf-8", errors="replace")
    if expected is not None and status != expected:
        raise RuntimeError(f"{method} {path}: got {status}, expected {expected}. Body: {text[:900]}")
    if not text:
        return status, {}
    try:
        return status, json.loads(text)
    except json.JSONDecodeError:
        return status, {"raw": text}


def prepare_user_record(email, role, name):
    password = secrets.token_urlsafe(12)
    conn = db_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("DELETE FROM users WHERE LOWER(email)=LOWER(%s)", (email,))
    cur.execute(
        """
        INSERT INTO users
            (name,email,password,role,project_id,project_name,assigned_projects,assigned_packages,active,two_factor_required,two_factor_enabled,company_id)
        VALUES
            (%s,%s,%s,%s,NULL,'','[]'::jsonb,'[]'::jsonb,TRUE,FALSE,FALSE,1)
        RETURNING id, name, email, role
        """,
        (name, email, hash_password(password), role),
    )
    row = dict(cur.fetchone())
    conn.commit()
    cur.close()
    conn.close()
    row["password"] = password
    row["token"] = auth_token_for(row)
    return row


def prepare_user(email, role, name):
    return prepare_user_record(email, role, name)["password"]


def login(email, password):
    status, body = api_json("POST", "/login", data={"email": email, "password": password}, expected=200)
    token = body.get("authToken") if isinstance(body, dict) else None
    if not token:
        raise RuntimeError(f"login {email}: authToken not returned. status={status} body={body}")
    return token


def cleanup():
    conn = db_conn()
    cur = conn.cursor()
    like_prefix = PREFIX + "%"
    emails = [SYSTEM_EMAIL, CRM_EMAIL, *PLATFORM_ROLE_EMAILS.values()]
    try:
        cur.execute("DELETE FROM project_documents WHERE project_name LIKE %s OR notes LIKE %s", (like_prefix, "%" + PREFIX + "%"))
        cur.execute("DELETE FROM projects WHERE name LIKE %s", (like_prefix,))
        cur.execute("DELETE FROM crm_lead_documents WHERE lead_id IN (SELECT id FROM crm_leads WHERE name LIKE %s)", (like_prefix,))
        cur.execute("DELETE FROM crm_lead_tasks WHERE lead_id IN (SELECT id FROM crm_leads WHERE name LIKE %s)", (like_prefix,))
        cur.execute("DELETE FROM invite_codes WHERE preset_name LIKE %s OR created_by LIKE %s", (like_prefix, like_prefix))
        cur.execute("DELETE FROM crm_leads WHERE name LIKE %s", (like_prefix,))
        cur.execute("DELETE FROM suppliers WHERE name LIKE %s", (like_prefix,))
        cur.execute("DELETE FROM staff WHERE name LIKE %s", (like_prefix,))
        cur.execute("DELETE FROM company_payments WHERE company_id IN (SELECT id FROM companies WHERE name LIKE %s)", (like_prefix,))
        cur.execute("DELETE FROM invite_codes WHERE preset_name IN (SELECT name FROM companies WHERE name LIKE %s)", (like_prefix,))
        cur.execute("""
            DELETE FROM platform_audit_log
            WHERE actor_name LIKE %s
               OR entity_name LIKE %s
               OR COALESCE(details_json,'') LIKE %s
               OR company_id IN (SELECT id FROM companies WHERE name LIKE %s)
               OR platform_account_id IN (SELECT id FROM platform_accounts WHERE name LIKE %s)
        """, (like_prefix, like_prefix, "%" + PREFIX + "%", like_prefix, like_prefix))
        cur.execute("""
            DELETE FROM platform_support_sessions
            WHERE reason LIKE %s
               OR opened_by_name LIKE %s
               OR closed_by_name LIKE %s
               OR company_id IN (SELECT id FROM companies WHERE name LIKE %s)
               OR platform_account_id IN (SELECT id FROM platform_accounts WHERE name LIKE %s)
        """, ("%" + PREFIX + "%", like_prefix, like_prefix, like_prefix, like_prefix))
        cur.execute("DELETE FROM companies WHERE name LIKE %s", (like_prefix,))
        cur.execute("DELETE FROM platform_accounts WHERE name LIKE %s", (like_prefix,))
        cur.execute("DELETE FROM users WHERE LOWER(email)=ANY(%s)", ([email.lower() for email in emails],))
        conn.commit()
    finally:
        cur.close()
        conn.close()


def create_smoke_project():
    conn = db_conn()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM project_documents WHERE project_name=%s", (PROJECT_NAME,))
        cur.execute("DELETE FROM projects WHERE name=%s", (PROJECT_NAME,))
        cur.execute(
            """
            INSERT INTO projects (name,client,status,budget,deadline,progress,tasks,pricelist_id)
            VALUES (%s,%s,'В работе',0,'2026-07-31',0,'{}'::text[],NULL)
            RETURNING id
            """,
            (PROJECT_NAME, f"{PREFIX} Client"),
        )
        project_id = cur.fetchone()[0]
        conn.commit()
        return project_id
    finally:
        cur.close()
        conn.close()


def check_platform(system_token):
    _, dashboard = api_json("GET", "/system/dashboard", token=system_token, expected=200)
    for key in ("activeAccounts", "activeCompanies", "inDemo", "overdue"):
        if key not in dashboard:
            raise RuntimeError(f"system dashboard missing {key}")

    _, tariffs = api_json("GET", "/system/tariffs", token=system_token, expected=200)
    tariff_ids = {item.get("id") for item in tariffs if isinstance(item, dict)}
    for required in ("demo", "starter", "pro", "group", "enterprise"):
        if required not in tariff_ids:
            raise RuntimeError(f"system tariffs missing {required}")

    company_name = f"{PREFIX} Company"
    account_name = f"{PREFIX} Account"
    _, created = api_json(
        "POST",
        "/system/companies",
        token=system_token,
        expected=200,
        data={
            "platformAccountName": account_name,
            "name": company_name,
            "shortName": "CODEX",
            "contactName": "CODEX QA",
            "contactPhone": "+70000000000",
            "contactEmail": f"platform-client-{RUN_ID}@stroyka.local",
            "plan": "demo",
            "trialDays": 14,
            "createdBy": f"{PREFIX} system_owner",
        },
    )
    company_id = created.get("id")
    if not company_id or not created.get("inviteCode"):
        raise RuntimeError(f"system create company returned invalid body: {created}")

    api_json("PUT", f"/system/companies/{company_id}", token=system_token, expected=200, data={"action": "soft_suspend", "reason": "smoke"})
    api_json("PUT", f"/system/companies/{company_id}", token=system_token, expected=200, data={"action": "resume"})
    api_json(
        "POST",
        "/system/payments",
        token=system_token,
        expected=200,
        data={
            "companyId": company_id,
            "amount": 1000,
            "paymentDate": "2026-06-29",
            "method": "smoke",
            "invoiceNumber": f"SMOKE-{RUN_ID}",
            "status": "paid",
            "periodStart": "2026-06-29",
            "periodEnd": "2026-07-29",
            "createdBy": f"{PREFIX} system_owner",
        },
    )
    _, companies = api_json("GET", "/system/companies", token=system_token, expected=200)
    created_company = next((c for c in companies if c.get("id") == company_id), None)
    if not created_company or not created_company.get("billing_state"):
        raise RuntimeError("system companies did not return created company with billing_state")
    _, audit_log = api_json("GET", "/system/audit-log?limit=80", token=system_token, expected=200)
    audit_text = json.dumps(audit_log, ensure_ascii=False)
    for expected_action in ("platform_account_created", "company_created", "company_soft_suspended", "company_resumed", "payment_added"):
        if expected_action not in audit_text:
            raise RuntimeError(f"system audit log missing {expected_action}")

    platform_account_id = created_company.get("platform_account_id")
    _, payment_audit = api_json(
        "GET",
        f"/system/audit-log?limit=80&companyId={company_id}&action=payment_added&search=SMOKE-{RUN_ID}",
        token=system_token,
        expected=200,
    )
    if not payment_audit or any(item.get("action") != "payment_added" or item.get("company_id") != company_id for item in payment_audit):
        raise RuntimeError(f"system audit filters by company/action/search returned invalid rows: {payment_audit}")
    if platform_account_id:
        _, account_audit = api_json(
            "GET",
            f"/system/audit-log?limit=80&platformAccountId={platform_account_id}",
            token=system_token,
            expected=200,
        )
        if not account_audit or any(item.get("platform_account_id") != platform_account_id for item in account_audit):
            raise RuntimeError(f"system audit filter by platform account returned invalid rows: {account_audit}")

    return {"companyId": company_id, "platformAccountId": platform_account_id, "tariffs": sorted(tariff_ids)}


def check_platform_roles(system_token, platform_result):
    _, platform_users = api_json("GET", "/system/platform-users", token=system_token, expected=200)
    if not isinstance(platform_users, list) or not any(item.get("role") == "system_owner" for item in platform_users):
        raise RuntimeError("system platform-users did not return platform owner")

    _, invite = api_json(
        "POST",
        "/system/platform-users/invite",
        token=system_token,
        expected=200,
        data={
            "role": "platform_support",
            "name": f"{PREFIX} Support Invite",
            "email": f"platform-invite-{RUN_ID}@stroyka.local",
            "expiresInDays": 3,
        },
    )
    if invite.get("role") != "platform_support" or not invite.get("code"):
        raise RuntimeError(f"platform support invite returned invalid body: {invite}")

    platform_admin = prepare_user_record(
        PLATFORM_ROLE_EMAILS["platform_admin"],
        "platform_admin",
        f"{PREFIX} Platform Admin",
    )
    platform_support = prepare_user_record(
        PLATFORM_ROLE_EMAILS["platform_support"],
        "platform_support",
        f"{PREFIX} Platform Support",
    )
    billing_admin = prepare_user_record(
        PLATFORM_ROLE_EMAILS["billing_admin"],
        "billing_admin",
        f"{PREFIX} Billing Admin",
    )

    for role_user in (platform_admin, platform_support, billing_admin):
        api_json("GET", "/system/dashboard", token=role_user["token"], expected=200)
        api_json("GET", "/system/companies", token=role_user["token"], expected=200)
        api_json("GET", "/system/audit-log?limit=20", token=role_user["token"], expected=200)
        api_json("GET", "/system/platform-users", token=role_user["token"], expected=403)

    api_json("GET", "/system/payments", token=platform_support["token"], expected=403)
    api_json("GET", "/system/payments", token=billing_admin["token"], expected=200)
    _, billing_payment = api_json(
        "POST",
        "/system/payments",
        token=billing_admin["token"],
        expected=200,
        data={
            "companyId": platform_result["companyId"],
            "amount": 777,
            "paymentDate": "2026-06-29",
            "method": "smoke-billing",
            "invoiceNumber": f"SMOKE-BILLING-{RUN_ID}",
            "status": "paid",
            "periodStart": "2026-07-29",
            "periodEnd": "2026-08-29",
        },
    )
    if not billing_payment.get("ok"):
        raise RuntimeError(f"billing admin payment returned invalid body: {billing_payment}")

    _, opened = api_json(
        "POST",
        "/system/support-sessions",
        token=platform_admin["token"],
        expected=200,
        data={
            "platformAccountId": platform_result.get("platformAccountId"),
            "companyId": platform_result["companyId"],
            "scope": "technical_check",
            "reason": f"{PREFIX} support session",
            "expiresInHours": 2,
        },
    )
    session_id = opened.get("session", {}).get("id")
    if not session_id:
        raise RuntimeError(f"platform admin support-session returned invalid body: {opened}")

    _, sessions = api_json("GET", "/system/support-sessions", token=platform_support["token"], expected=200)
    if not any(item.get("id") == session_id and item.get("status") == "active" for item in sessions):
        raise RuntimeError(f"platform support sessions did not include opened session: {sessions}")
    api_json("PUT", f"/system/support-sessions/{session_id}", token=platform_support["token"], expected=403)
    api_json("PUT", f"/system/support-sessions/{session_id}", token=platform_admin["token"], expected=200, data={"action": "close"})

    _, audit_log = api_json("GET", f"/system/audit-log?limit=80&search={RUN_ID}", token=platform_admin["token"], expected=200)
    audit_text = json.dumps(audit_log, ensure_ascii=False)
    for expected_action in ("platform_user_invited", "support_session_opened", "support_session_closed", "payment_added"):
        if expected_action not in audit_text:
            raise RuntimeError(f"platform role audit log missing {expected_action}")

    return {
        "platformAdmin": platform_admin["email"],
        "platformSupport": platform_support["email"],
        "billingAdmin": billing_admin["email"],
        "supportSessionId": session_id,
    }


def check_crm(crm_token):
    project_id = create_smoke_project()
    supplier_name = f"{PREFIX} Supplier"
    _, supplier_lead = api_json(
        "POST",
        "/crm/leads",
        token=crm_token,
        expected=200,
        data={
            "name": supplier_name,
            "phone": "+70000000001",
            "email": f"supplier-{RUN_ID}@stroyka.local",
            "source": "smoke",
            "leadType": "Поставщик",
            "stage": "На проверке",
            "reviewStatus": "На проверке",
            "workType": "Отделочные материалы",
            "inn": "0000000000",
            "notes": "temporary smoke lead",
        },
    )
    supplier_lead_id = supplier_lead.get("id")
    if not supplier_lead_id:
        raise RuntimeError(f"CRM supplier lead create returned invalid body: {supplier_lead}")

    _, supplier_doc = api_json(
        "POST",
        f"/crm/leads/{supplier_lead_id}/documents",
        token=crm_token,
        expected=200,
        data={
            "docType": "Реквизиты",
            "title": "Smoke requisites",
            "fileUrl": f"/uploads/smoke/{RUN_ID}/requisites.pdf",
            "number": f"REQ-{RUN_ID}",
            "docDate": "2026-06-29",
            "confidential": True,
            "notes": f"{PREFIX} CRM transfer check",
        },
    )
    _, task = api_json(
        "POST",
        f"/crm/leads/{supplier_lead_id}/tasks",
        token=crm_token,
        expected=200,
        data={"title": "Проверить поставщика", "dueDate": "2026-06-30", "assignedTo": "CODEX QA"},
    )
    api_json("PUT", f"/crm/tasks/{task.get('id')}", token=crm_token, expected=200, data={**task, "status": "Закрыта"})
    _, approved_supplier = api_json("POST", f"/crm/leads/{supplier_lead_id}/approve-supplier", token=crm_token, expected=200, data={})
    if not approved_supplier.get("supplier", {}).get("id"):
        raise RuntimeError(f"approve supplier returned invalid body: {approved_supplier}")
    _, invite = api_json("POST", f"/crm/leads/{supplier_lead_id}/create-invite", token=crm_token, expected=200, data={"role": "поставщик"})
    if not invite.get("link"):
        raise RuntimeError(f"CRM invite returned invalid body: {invite}")
    _, transfer = api_json(
        "POST",
        f"/crm/leads/{supplier_lead_id}/transfer-documents-to-project",
        token=crm_token,
        expected=200,
        data={"projectName": PROJECT_NAME, "documentIds": [supplier_doc.get("id")], "side": "contractor"},
    )
    if not transfer.get("created"):
        raise RuntimeError(f"CRM document transfer returned invalid body: {transfer}")

    worker_name = f"{PREFIX} Worker"
    _, worker_lead = api_json(
        "POST",
        "/crm/leads",
        token=crm_token,
        expected=200,
        data={
            "name": worker_name,
            "phone": "+70000000002",
            "email": f"worker-{RUN_ID}@stroyka.local",
            "source": "smoke",
            "leadType": "Мастер",
            "stage": "На проверке",
            "reviewStatus": "На проверке",
            "workType": "Отделка",
            "legalForm": "Самозанятый",
        },
    )
    worker_lead_id = worker_lead.get("id")
    api_json("POST", f"/crm/leads/{worker_lead_id}/approve-worker", token=crm_token, expected=200, data={"role": "мастер"})

    client_name = f"{PREFIX} Client Lead"
    _, client_lead = api_json(
        "POST",
        "/crm/leads",
        token=crm_token,
        expected=200,
        data={
            "name": client_name,
            "phone": "+70000000003",
            "email": f"client-{RUN_ID}@stroyka.local",
            "source": "smoke",
            "leadType": "Клиент",
            "stage": "Договор",
            "budget": 250000,
            "reviewStatus": "На проверке",
        },
    )
    client_lead_id = client_lead.get("id")
    _, project_created = api_json(
        "POST",
        f"/crm/leads/{client_lead_id}/create-project",
        token=crm_token,
        expected=200,
        data={"projectName": PROJECT_CREATE_NAME, "budget": 250000},
    )
    created_project_id = project_created.get("project", {}).get("id")
    if not created_project_id:
        raise RuntimeError(f"CRM create-project returned invalid body: {project_created}")

    _, details = api_json("GET", f"/crm/leads/{supplier_lead_id}/details", token=crm_token, expected=200)
    if not details.get("documents") or not details.get("tasks"):
        raise RuntimeError("CRM details did not return documents and tasks")
    _, summaries = api_json("GET", "/crm/lead-summaries", token=crm_token, expected=200)
    if not any(item.get("id") == supplier_lead_id for item in summaries):
        raise RuntimeError("CRM summaries did not include created lead")
    return {
        "supplierLeadId": supplier_lead_id,
        "workerLeadId": worker_lead_id,
        "clientLeadId": client_lead_id,
        "projectId": project_id,
        "createdProjectId": created_project_id,
        "transferredProjectDocumentIds": transfer.get("created", []),
    }


def main():
    cleanup()
    system_user = prepare_user_record(SYSTEM_EMAIL, "system_owner", f"{PREFIX} System Owner")
    crm_password = prepare_user(CRM_EMAIL, "менеджер_crm", f"{PREFIX} CRM Manager")
    try:
        system_token = system_user["token"]
        crm_token = login(CRM_EMAIL, crm_password)
        platform_result = check_platform(system_token)
        platform_roles_result = check_platform_roles(system_token, platform_result)
        crm_result = check_crm(crm_token)
        summary = {
            "ok": True,
            "baseUrl": BASE_URL,
            "checked": [
                "system dashboard",
                "system tariffs",
                "platform account company creation",
                "soft suspend and resume",
                "platform payment",
                "platform audit log",
                "platform audit filters",
                "platform team invite",
                "platform staff role access",
                "platform support sessions",
                "platform billing role",
                "crm lead summaries and details",
                "crm documents and tasks",
                "supplier approval",
                "worker approval",
                "crm invite creation",
                "crm lead to project",
                "crm document transfer to project documents",
            ],
            "platform": platform_result,
            "platformRoles": platform_roles_result,
            "crm": crm_result,
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    finally:
        cleanup()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc), "baseUrl": BASE_URL}, ensure_ascii=False, indent=2), file=sys.stderr)
        try:
            cleanup()
        except Exception as cleanup_exc:
            print(f"cleanup warning: {cleanup_exc}", file=sys.stderr)
        sys.exit(1)
