#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import secrets
from pathlib import Path

import psycopg2
import psycopg2.extras


PASSWORD_HASH_PREFIX = "pbkdf2_sha256"
PASSWORD_HASH_ITERATIONS = 260000


def load_env():
    root = Path(__file__).resolve().parents[1]
    env_path = root / "backend" / ".env"
    values = {}
    if env_path.exists():
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def get_db_config():
    env = load_env()
    return {
        "dbname": env.get("DB_NAME", os.getenv("DB_NAME", "stroyka")),
        "user": env.get("DB_USER", os.getenv("DB_USER", "stroyka")),
        "password": env.get("DB_PASSWORD", os.getenv("DB_PASSWORD", "password123")),
        "host": env.get("DB_HOST", os.getenv("DB_HOST", "localhost")),
        "port": env.get("DB_PORT", os.getenv("DB_PORT", "5432")),
    }


def connect_db():
    return psycopg2.connect(**get_db_config())


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PASSWORD_HASH_ITERATIONS,
    ).hex()
    return f"{PASSWORD_HASH_PREFIX}${PASSWORD_HASH_ITERATIONS}${salt}${digest}"


def resolve_project(cur, project_name: str):
    clean = (project_name or "").strip()
    if not clean:
        return None, ""
    cur.execute("SELECT id, name FROM projects WHERE name=%s LIMIT 1", (clean,))
    row = cur.fetchone()
    if not row:
        raise SystemExit(f"Проект не найден: {clean}")
    return row["id"], row["name"]


def create_or_update_user(args):
    conn = connect_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    email = args.email.strip().lower()
    project_id, project_name = resolve_project(cur, args.project or "")
    assigned_projects = [project_name] if project_name else []
    password_hash = hash_password(args.password)
    cur.execute("SELECT id, email FROM users WHERE LOWER(email)=LOWER(%s) LIMIT 1", (email,))
    existing = cur.fetchone()
    if existing:
        cur.execute(
            """
            UPDATE users
               SET name=%s,
                   email=%s,
                   password=%s,
                   role=%s,
                   project_id=%s,
                   project_name=%s,
                   assigned_projects=%s::jsonb,
                   active=TRUE,
                   failed_login_count=0,
                   locked_until=NULL,
                   reset_token=NULL,
                   reset_token_expires=NULL
             WHERE id=%s
         RETURNING id, name, email, role, project_name, active
            """,
            (
                args.name,
                email,
                password_hash,
                args.role,
                project_id,
                project_name,
                json.dumps(assigned_projects, ensure_ascii=False),
                existing["id"],
            ),
        )
        row = cur.fetchone()
        action = "updated"
    else:
        cur.execute(
            """
            INSERT INTO users
                (name, email, password, role, project_id, project_name, assigned_projects, active)
            VALUES
                (%s, %s, %s, %s, %s, %s, %s::jsonb, TRUE)
            RETURNING id, name, email, role, project_name, active
            """,
            (
                args.name,
                email,
                password_hash,
                args.role,
                project_id,
                project_name,
                json.dumps(assigned_projects, ensure_ascii=False),
            ),
        )
        row = cur.fetchone()
        action = "created"
    conn.commit()
    cur.close()
    conn.close()
    print(json.dumps({"ok": True, "action": action, "user": dict(row)}, ensure_ascii=False, indent=2))


def disable_user(args):
    conn = connect_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    email = args.email.strip().lower()
    cur.execute(
        """
        UPDATE users
           SET active=FALSE,
               locked_until=NULL
         WHERE LOWER(email)=LOWER(%s)
     RETURNING id, name, email, role, active
        """,
        (email,),
    )
    row = cur.fetchone()
    if not row:
        cur.close()
        conn.close()
        raise SystemExit(f"Пользователь не найден: {email}")
    conn.commit()
    cur.close()
    conn.close()
    print(json.dumps({"ok": True, "action": "disabled", "user": dict(row)}, ensure_ascii=False, indent=2))


def show_user(args):
    conn = connect_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    email = args.email.strip().lower()
    cur.execute(
        """
        SELECT id, name, email, role, project_name, assigned_projects, active, failed_login_count, locked_until
          FROM users
         WHERE LOWER(email)=LOWER(%s)
         LIMIT 1
        """,
        (email,),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        raise SystemExit(f"Пользователь не найден: {email}")
    print(json.dumps(dict(row), ensure_ascii=False, indent=2, default=str))


def build_parser():
    parser = argparse.ArgumentParser(description="Управление временным пользователем для smoke-проверок ролей")
    sub = parser.add_subparsers(dest="command", required=True)

    create_cmd = sub.add_parser("create", help="Создать или обновить пользователя")
    create_cmd.add_argument("--email", required=True, help="Email пользователя")
    create_cmd.add_argument("--name", default="Временный зам директора", help="Имя пользователя")
    create_cmd.add_argument("--password", required=True, help="Пароль")
    create_cmd.add_argument("--role", default="зам_директора", help="Системная роль")
    create_cmd.add_argument("--project", default="", help="Имя проекта для привязки")
    create_cmd.set_defaults(func=create_or_update_user)

    disable_cmd = sub.add_parser("disable", help="Отключить пользователя")
    disable_cmd.add_argument("--email", required=True, help="Email пользователя")
    disable_cmd.set_defaults(func=disable_user)

    show_cmd = sub.add_parser("show", help="Показать состояние пользователя")
    show_cmd.add_argument("--email", required=True, help="Email пользователя")
    show_cmd.set_defaults(func=show_user)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
