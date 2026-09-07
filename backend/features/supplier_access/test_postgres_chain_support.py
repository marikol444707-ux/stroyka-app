"""Test-only, opt-in support for the authenticated supply chain test.

The test_ prefix keeps synthetic seed writers out of runtime writer inventories.
Production modules must not import this helper.

build_fixture() returns (real_main, fixture, cleanup). Cleanup restores process
patches, not database rows; provision a fresh supply_chain_test_* DB per run.
Only explicit Unix-socket settings are accepted, always as chain_test without a
password. Ambient config/.env is never loaded and outbound TCP is blocked.
"""

import __future__
import ast
from contextlib import ExitStack
import importlib
import json
import os
from pathlib import Path
import re
import socket
import sys
import tempfile
import types
from unittest.mock import patch


def connection_settings(environ):
    if environ.get("SUPPLY_CHAIN_RUN_POSTGRES") != "1":
        raise RuntimeError("Explicit SUPPLY_CHAIN_RUN_POSTGRES=1 is required")
    host = environ.get("SUPPLY_CHAIN_TEST_DB_HOST", "")
    port = environ.get("SUPPLY_CHAIN_TEST_DB_PORT", "")
    name = environ.get("SUPPLY_CHAIN_TEST_DB_NAME", "")
    if not host.startswith("/") or "," in host or "\x00" in host:
        raise RuntimeError("Explicit Unix socket SUPPLY_CHAIN_TEST_DB_HOST required")
    if not port.isdecimal() or not 1 <= int(port) <= 65535:
        raise RuntimeError("Explicit valid SUPPLY_CHAIN_TEST_DB_PORT required")
    if not re.fullmatch(r"supply_chain_test_[a-z0-9_]+", name):
        raise RuntimeError("Dedicated supply_chain_test_* database required")
    return {"host": host, "port": port, "dbname": name, "user": "chain_test", "password": ""}


def build_fixture():
    settings = connection_settings(os.environ)
    return _build_isolated_fixture(settings)


def guarded_connector(settings, connect):
    def guarded(*args, **kwargs):
        # Reject DSNs, service files and hostaddr overrides, not just DB names.
        if args or set(kwargs) != set(settings) or any(
            str(kwargs[key]) != value for key, value in settings.items()
        ):
            raise RuntimeError("Non-isolated PostgreSQL connection refused")
        return connect(**kwargs)
    return guarded


def _assert_empty_database(conn, settings):
    with conn.cursor() as cur:
        cur.execute("SELECT current_database(),current_user,inet_server_addr(),inet_server_port()")
        if cur.fetchone() != (settings["dbname"], "chain_test", None, None):
            raise RuntimeError("PostgreSQL server identity mismatch")
        cur.execute("SELECT EXISTS(SELECT 1 FROM pg_tables WHERE schemaname='public')")
        if cur.fetchone()[0]:
            raise RuntimeError("Supply chain fixture requires an empty dedicated database")


def _module_from_source(name, path, stack, *, omit_calls=(), before_call=None):
    # Python 3.9/Pydantic evaluates int | None despite future annotations.
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source.replace("int | None", "Optional[int]"), filename=str(path))
    selected = []
    for node in tree.body:
        call = (node.value.func.id if isinstance(node, ast.Expr)
                and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name) else None)
        if call == before_call and before_call is not None:
            break
        if call not in omit_calls:
            selected.append(node)
    tree.body = selected
    module = types.ModuleType(name)
    module.__file__, module.__package__ = str(path), name.rpartition(".")[0]
    stack.enter_context(patch.dict(sys.modules, {name: module}))
    exec(compile(tree, str(path), "exec", flags=__future__.annotations.compiler_flag), module.__dict__)
    return module


def _initialize_schema(runtime, source):
    # Legacy init_db ALTERs these five before their CREATEs on a blank database.
    # Execute only their exact existing declarations, then rerun real init_db.
    allowed = {"estimates", "warehouse_main", "work_journal", "interim_acts", "hidden_works_acts"}
    prerequisites = []
    import psycopg2
    for _ in range(len(allowed) + 1):
        try:
            runtime.init_db()
            runtime.ensure_agent_jobs_schema(runtime.get_db)
            return prerequisites
        except psycopg2.errors.UndefinedTable as exc:
            missing = re.search(r'relation "([a-z_]+)" does not exist', str(exc))
            table = missing.group(1) if missing else ""
            if table not in allowed or table in prerequisites:
                raise
            ddl = re.search(r"CREATE TABLE IF NOT EXISTS " + table + r"\s*\(.*?\n        \);", source, re.S)
            if not ddl:
                raise RuntimeError("Missing exact legacy prerequisite DDL") from exc
            conn = runtime.get_db()
            try:
                with conn.cursor() as cur:
                    cur.execute(ddl.group(0))
            finally:
                conn.close()
            prerequisites.append(table)
    raise RuntimeError("Unexpected bootstrap retry limit")


def _seed(runtime):
    from psycopg2.extras import Json, RealDictCursor
    project, material, package = "SUPPLY CHAIN synthetic object", "SUPPLY CHAIN exact resource", "Основная"
    roles = {"director": "директор", "foreman": "прораб", "accountant": "бухгалтер",
             "supplier": "поставщик", "stranger_supplier": "поставщик", "stranger": "директор"}
    users = {}
    conn = runtime.get_db()
    conn.autocommit = False
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            for company_id in (2, 3):
                cur.execute("""INSERT INTO companies(id,name,short_name,plan,active,payment_status)
                               VALUES(%s,%s,%s,'pro',TRUE,'active')""",
                            (company_id, "SUPPLY CHAIN company " + str(company_id), "CHAIN"))
            cur.execute("SELECT setval(pg_get_serial_sequence('companies','id'),3,true)")
            cur.execute("""INSERT INTO projects(name,company_id,status,budget,archived)
                           VALUES(%s,2,'В работе',100000,FALSE) RETURNING id""", (project,))
            project_id = cur.fetchone()["id"]
            for key, role in roles.items():
                company_id = None if role == "поставщик" else 3 if key == "stranger" else 2
                assigned = [project] if company_id == 2 else []
                packages = [package] if company_id == 2 else []
                cur.execute("""INSERT INTO users(name,email,password,role,active,company_id,
                    project_id,project_name,assigned_projects,assigned_packages,two_factor_required,two_factor_enabled)
                    VALUES(%s,%s,%s,%s,TRUE,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
                    ("SUPPLY CHAIN " + key, key + "@supply-chain.invalid",
                     runtime.hash_password("Synthetic-local-only!2026"), role, company_id,
                     project_id if company_id == 2 else None, project if company_id == 2 else "",
                     Json(assigned), Json(packages), role in ("директор", "бухгалтер"),
                     role in ("директор", "бухгалтер")))
                users[key] = dict(cur.fetchone())
                if company_id:
                    cur.execute("""INSERT INTO user_company_roles(user_id,company_id,platform_account_id,
                        role,assigned_projects,assigned_packages,active,is_default)
                        VALUES(%s,%s,1,%s,%s,%s,TRUE,TRUE)""",
                        (users[key]["id"], company_id, role, Json(assigned), Json(packages)))
            for key, inn in (("supplier", "7701234567"), ("stranger_supplier", "7809876543")):
                cur.execute("""INSERT INTO suppliers(name,email,inn,status,user_id,registered_at)
                    VALUES(%s,%s,%s,'Активный',%s,NOW()) RETURNING id""",
                    ("SUPPLY CHAIN legal " + key, users[key]["email"], inn, users[key]["id"]))
                if key == "supplier":
                    supplier_id = cur.fetchone()["id"]
            sections = [{"name": package, "items": [{"id": "chain-material-1", "name": material,
                "type": "material", "itemType": "material", "unit": "шт", "quantity": 2,
                "price": 100, "priceMaterial": 100, "lineTotal": 200, "workPackage": package}]}]
            cur.execute("""INSERT INTO estimates(company_id,project_id,project_name,name,version,
                sections_json,status,is_template,smeta_type,work_package)
                VALUES(2,%s,%s,'CHAIN active estimate','1',%s,'Активная',FALSE,'Заказчик',%s) RETURNING id""",
                (project_id, project, json.dumps(sections, ensure_ascii=False), package))
            estimate_id = cur.fetchone()["id"]
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return {"companyId": 2, "projectId": project_id, "project": project, "estimateId": estimate_id,
            "supplierId": supplier_id, "users": users, "materialName": material,
            "quantity": 2, "unit": "шт", "workPackage": package}


def _build_isolated_fixture(settings):
    import psycopg2
    stack = ExitStack()
    connections = []
    try:
        temporary_directory = stack.enter_context(tempfile.TemporaryDirectory(prefix="supply-chain-fixture-"))
        env = {"DB_HOST": settings["host"], "DB_PORT": settings["port"], "DB_NAME": settings["dbname"],
               "DB_USER": "chain_test", "DB_PASSWORD": "", "APP_PUBLIC_URL": "http://localhost",
               "PGPASSFILE": os.path.join(temporary_directory, "no-password-file"),
               "AUTH_SECRET": "Supply-Chain-Test-Only-6vN8qP3xR5tZ9cD1"}
        stack.enter_context(patch.dict(os.environ, env, clear=True))
        original_connect = psycopg2.connect
        def tracked_connect(**kwargs):
            conn = original_connect(**kwargs)
            connections.append(conn)
            return conn
        stack.enter_context(patch.object(psycopg2, "connect", guarded_connector(settings, tracked_connect)))
        def no_network(*_args, **_kwargs):
            raise RuntimeError("Outbound network disabled in supply chain fixture")
        original_socket_connect = socket.socket.connect
        def unix_only(sock, address):
            return original_socket_connect(sock, address) if sock.family == socket.AF_UNIX else no_network()
        stack.enter_context(patch.object(socket, "create_connection", no_network))
        stack.enter_context(patch.object(socket.socket, "connect", unix_only))
        stack.enter_context(patch.object(socket.socket, "connect_ex", no_network))
        conn = psycopg2.connect(**settings)
        try:
            _assert_empty_database(conn, settings)
        finally:
            conn.close()
        root = Path(__file__).resolve().parents[2]
        previous_directory = os.getcwd()
        os.chdir(temporary_directory)
        stack.callback(os.chdir, previous_directory)
        # Bypass only config's .env loading, never credential/auth/tenant logic.
        import backend
        for name in ("config", "db", "auth"):
            existed, previous = name in vars(backend), getattr(backend, name, None)
            def restore_parent_attribute(name=name, existed=existed, previous=previous):
                if existed:
                    setattr(backend, name, previous)
                else:
                    vars(backend).pop(name, None)
            stack.callback(restore_parent_attribute)
        config = _module_from_source("backend.config", root / "config.py", stack, omit_calls=("load_env_file",))
        stack.enter_context(patch.object(backend, "config", config, create=True))
        db = importlib.import_module("backend.db")
        stack.enter_context(patch.dict(db.DB_CONFIG, settings, clear=True))
        auth = importlib.import_module("backend.auth")
        stack.enter_context(patch.object(auth, "AUTH_SECRET", config.AUTH_SECRET))
        stack.enter_context(patch.object(auth, "AUTH_TOKEN_TTL_SECONDS", config.AUTH_TOKEN_TTL_SECONDS))
        stack.enter_context(patch.object(auth, "APP_PUBLIC_URL", config.APP_PUBLIC_URL))
        if sys.version_info < (3, 10):
            marketing = importlib.import_module("backend.features.marketing")
            compat = _module_from_source("backend.features.marketing.routes",
                root / "features/marketing/routes.py", stack)
            stack.enter_context(patch.object(marketing, "register_marketing_module", compat.register_marketing_module))
        main_path = root / "main.py"
        schema_runtime = _module_from_source("backend._supply_chain_schema", main_path, stack, before_call="init_db")
        prerequisites = _initialize_schema(schema_runtime, main_path.read_text(encoding="utf-8"))
        main = _module_from_source("backend._supply_chain_test_runtime", main_path, stack,
                                   omit_calls=("init_db", "ensure_agent_jobs_schema"))
        fixture = _seed(main)
        fixture["bootstrapPrerequisites"] = prerequisites
        def cleanup():
            for connection in connections:
                if not connection.closed:
                    connection.close()
            stack.close()
        return main, fixture, cleanup
    except BaseException:
        for connection in connections:
            if not connection.closed:
                connection.close()
        stack.close()
        raise
