"""Give the demo accounts the company created during startup.

init_db inserts the bootstrap company before these accounts. They take that
company's id. When the company row is missing, nothing is inserted. An
account that already has a company keeps it.
"""

BOOTSTRAP_COMPANY_NAME = "СтройКа"
BOOTSTRAP_USERS = (
    ("Директор", "admin@stroyka.ru", "admin123", "директор"),
    ("Бухгалтер", "buh@stroyka.ru", "buh123", "бухгалтер"),
    ("Прораб", "prorab@stroyka.ru", "prorab123", "прораб"),
    ("Мастер", "master@stroyka.ru", "master123", "мастер"),
)


def _company_id(row):
    if not row:
        return None
    if isinstance(row, dict):
        value = row.get("id")
    else:
        value = row[0]
    try:
        company_id = int(value)
    except (TypeError, ValueError):
        return None
    return company_id if company_id > 0 else None


def seed_bootstrap_users(cur, users):
    """Insert demo users for the bootstrap company, or skip when it is absent."""
    cur.execute(
        "SELECT id, platform_account_id FROM companies WHERE name=%s ORDER BY id LIMIT 1",
        (BOOTSTRAP_COMPANY_NAME,),
    )
    company_id = _company_id(cur.fetchone())
    if not company_id:
        return {"companyId": None, "emails": []}
    emails = []
    for name, email, password_hash, role in users or ():
        emails.append(email)
        cur.execute(
            """INSERT INTO users (name, email, password, role, company_id)
               VALUES (%s,%s,%s,%s,%s)
               ON CONFLICT (email) DO NOTHING""",
            (name, email, password_hash, role, company_id),
        )
        cur.execute(
            """UPDATE users SET company_id=%s
                WHERE email=%s AND company_id IS NULL""",
            (company_id, email),
        )
    cur.execute(
        """INSERT INTO user_company_roles
               (user_id, platform_account_id, company_id, role,
                assigned_projects, assigned_packages, active, is_default)
           SELECT u.id, c.platform_account_id, u.company_id, u.role,
                  COALESCE(u.assigned_projects, '[]'::jsonb),
                  COALESCE(u.assigned_packages, '[]'::jsonb),
                  TRUE, TRUE
             FROM users u
             JOIN companies c ON c.id=u.company_id
            WHERE u.email = ANY(%s)
              AND u.company_id=%s
              AND COALESCE(u.role, '') <> ''
           ON CONFLICT (user_id, company_id, role) DO NOTHING""",
        (emails, company_id),
    )
    return {"companyId": company_id, "emails": emails}
