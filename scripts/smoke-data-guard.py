#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

import psycopg2
import psycopg2.extras


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / "backend" / ".env"
PROJECT_NAME = os.getenv("DATA_GUARD_PROJECT", "Кисловодск Лицей 4")
MIN_ACTIVE_CUSTOMER_ESTIMATES = int(os.getenv("DATA_GUARD_MIN_ACTIVE_CUSTOMER_ESTIMATES", "1"))
WARN_ACTIVE_CUSTOMER_ESTIMATES = int(os.getenv("DATA_GUARD_WARN_ACTIVE_CUSTOMER_ESTIMATES", "9"))
MIN_ACTIVE_USERS = int(os.getenv("DATA_GUARD_MIN_ACTIVE_USERS", "1"))
MIN_STAFF = int(os.getenv("DATA_GUARD_MIN_STAFF", "1"))


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


def env_value(name, default=""):
    env = load_env()
    return os.getenv(name) or env.get(name, default)


def connect_db():
    return psycopg2.connect(
        dbname=env_value("DB_NAME", "stroyka"),
        user=env_value("DB_USER", "stroyka"),
        password=env_value("DB_PASSWORD", "password123"),
        host=env_value("DB_HOST", "localhost"),
        port=env_value("DB_PORT", "5432"),
    )


def scalar(cur, query, params=()):
    cur.execute(query, params)
    row = cur.fetchone()
    return next(iter(row.values())) if row else None


def main():
    failures = []
    warnings = []

    conn = connect_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute(
        """
        SELECT id, name, client, status, budget, COALESCE(archived, FALSE) AS archived
          FROM projects
         WHERE name=%s
         LIMIT 1
        """,
        (PROJECT_NAME,),
    )
    project = cur.fetchone()
    if not project:
        failures.append(f"Живой объект не найден: {PROJECT_NAME}")
    elif project["archived"]:
        failures.append(f"Живой объект в архиве: {PROJECT_NAME}")

    active_projects = scalar(cur, "SELECT COUNT(*) FROM projects WHERE COALESCE(archived, FALSE)=FALSE") or 0
    active_users = scalar(cur, "SELECT COUNT(*) FROM users WHERE COALESCE(active, TRUE)=TRUE") or 0
    directors = scalar(cur, "SELECT COUNT(*) FROM users WHERE COALESCE(active, TRUE)=TRUE AND role='директор'") or 0
    staff_total = scalar(cur, "SELECT COUNT(*) FROM staff") or 0
    estimates_total = scalar(cur, "SELECT COUNT(*) FROM estimates WHERE project_name=%s", (PROJECT_NAME,)) or 0
    active_customer_estimates = scalar(
        cur,
        """
        SELECT COUNT(*)
          FROM estimates
         WHERE project_name=%s
           AND COALESCE(smeta_type, '')='Заказчик'
           AND COALESCE(status, '')='Активная'
        """,
        (PROJECT_NAME,),
    ) or 0
    active_customer_with_sections = scalar(
        cur,
        """
        SELECT COUNT(*)
          FROM estimates
         WHERE project_name=%s
           AND COALESCE(smeta_type, '')='Заказчик'
           AND COALESCE(status, '')='Активная'
           AND COALESCE(sections_json, '') NOT IN ('', '[]')
        """,
        (PROJECT_NAME,),
    ) or 0
    codex_active_estimates = scalar(
        cur,
        """
        SELECT COUNT(*)
          FROM estimates
         WHERE COALESCE(status, '')='Активная'
           AND (name ILIKE '%%CODEX%%' OR COALESCE(work_package, '') ILIKE '%%CODEX%%')
        """,
    ) or 0
    local_test_users = scalar(
        cur,
        """
        SELECT COUNT(*)
          FROM users
         WHERE COALESCE(active, TRUE)=TRUE
           AND (LOWER(email) LIKE '%%stroyka.local%%' OR LOWER(name) LIKE '%%codex%%' OR LOWER(email) LIKE '%%codex%%')
        """,
    ) or 0

    cur.execute(
        """
        SELECT work_package, COUNT(*) AS count
          FROM estimates
         WHERE project_name=%s
           AND COALESCE(smeta_type, '')='Заказчик'
           AND COALESCE(status, '')='Активная'
         GROUP BY work_package
         ORDER BY work_package
        """,
        (PROJECT_NAME,),
    )
    packages = [dict(row) for row in cur.fetchall()]

    cur.close()
    conn.close()

    if active_projects <= 0:
        failures.append("Нет активных объектов")
    if active_users < MIN_ACTIVE_USERS:
        failures.append(f"Активных пользователей меньше лимита: {active_users} < {MIN_ACTIVE_USERS}")
    if directors <= 0:
        failures.append("Нет активного директора")
    if staff_total < MIN_STAFF:
        failures.append(f"Сотрудников меньше лимита: {staff_total} < {MIN_STAFF}")
    if active_customer_estimates < MIN_ACTIVE_CUSTOMER_ESTIMATES:
        failures.append(
            f"Активных смет заказчика по объекту меньше лимита: "
            f"{active_customer_estimates} < {MIN_ACTIVE_CUSTOMER_ESTIMATES}"
        )
    if active_customer_estimates < WARN_ACTIVE_CUSTOMER_ESTIMATES:
        warnings.append(
            f"Активных смет заказчика по объекту меньше ожидаемого живого набора: "
            f"{active_customer_estimates} < {WARN_ACTIVE_CUSTOMER_ESTIMATES}"
        )
    if active_customer_with_sections < active_customer_estimates:
        warnings.append(
            f"Есть активные сметы заказчика без sections_json: "
            f"{active_customer_estimates - active_customer_with_sections}"
        )
    if codex_active_estimates:
        warnings.append(f"Есть активные тестовые CODEX-сметы: {codex_active_estimates}")

    summary = {
        "ok": not failures,
        "projectName": PROJECT_NAME,
        "checks": {
            "activeProjects": active_projects,
            "activeUsers": active_users,
            "directors": directors,
            "staff": staff_total,
            "projectEstimates": estimates_total,
            "activeCustomerEstimates": active_customer_estimates,
            "activeCustomerEstimatesWithSections": active_customer_with_sections,
            "activeCodexEstimates": codex_active_estimates,
            "activeLocalTestUsers": local_test_users,
        },
        "packages": packages,
        "failures": failures,
        "warnings": warnings,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
