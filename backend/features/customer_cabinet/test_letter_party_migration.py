import ast
import importlib.util
import json
import os
from pathlib import Path
import unittest

import psycopg2


class OutgoingLetterPartyMigrationTest(unittest.TestCase):
    def test_migration_follows_current_head_and_guards_history(self):
        path = Path(__file__).resolve().parents[3] / "migrations/versions/0080_outgoing_letter_parties.py"
        source = path.read_text()
        tree = ast.parse(source)
        values = {node.targets[0].id: ast.literal_eval(node.value) for node in tree.body
                  if isinstance(node, ast.Assign) and len(node.targets) == 1
                  and isinstance(node.targets[0], ast.Name) and node.targets[0].id in {"revision", "down_revision"}}
        self.assertEqual(values, {"revision": "0080_outgoing_letter_parties",
                                  "down_revision": "0079_warehouse_movement_document"})
        self.assertIn("party_snapshot_json JSONB", source)
        self.assertIn("project_letter_party_snapshot_guard", source)
        self.assertIn("Cannot discard frozen outgoing letter parties", source)


@unittest.skipUnless(os.getenv("RUN_SUPPLIER_DEAL_PG_TESTS") == "1", "local PostgreSQL opt-in")
class OutgoingLetterPartyMigrationPostgresTest(unittest.TestCase):
    def test_frozen_letter_cannot_be_rewritten(self):
        from backend.db import DB_CONFIG
        self.assertIn(DB_CONFIG.get("host"), ("localhost", "127.0.0.1", "::1"))
        path = Path(__file__).resolve().parents[3] / "migrations/versions/0080_outgoing_letter_parties.py"
        spec = importlib.util.spec_from_file_location("letter_party_migration", path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        with psycopg2.connect(**DB_CONFIG) as connection:
            with connection.cursor() as cur:
                cur.execute("SET search_path TO pg_temp")
                cur.execute("""CREATE TEMP TABLE project_letters(
                    id SERIAL PRIMARY KEY,project_name TEXT,company_id INT,project_id INT,
                    created_by_user_id INT,side TEXT,direction TEXT,subject TEXT,body TEXT,
                    counterparty TEXT,letter_date DATE,file_url TEXT,author TEXT,status TEXT,
                    delivery_status TEXT,published_at TIMESTAMPTZ,published_by_id INT,
                    published_by_name TEXT,client_request_id UUID)""")
                cur.execute(migration.UPGRADE_SQL.replace("public.", "pg_temp."))
                snapshot = {"schemaVersion": 1, "sender": {"companyId": 12},
                            "recipient": {"clientId": 21}, "project": {"id": 1}}
                encoded = json.dumps(snapshot)
                from .letter_party_snapshot import snapshot_digest
                cur.execute("""INSERT INTO project_letters(project_name,company_id,project_id,
                    created_by_user_id,side,direction,subject,status,delivery_status,published_at,
                    party_snapshot_json,party_snapshot_hash,party_snapshot_frozen_at,customer_client_id)
                    VALUES('Лицей',12,1,3,'customer','outgoing','Письмо','Активно','sent',NOW(),
                           %s::jsonb,%s,NOW(),21) RETURNING id""", (encoded, snapshot_digest(snapshot)))
                letter_id = cur.fetchone()[0]
                with self.assertRaises(psycopg2.errors.CheckViolation):
                    cur.execute("UPDATE project_letters SET subject='Подмена' WHERE id=%s", (letter_id,))
