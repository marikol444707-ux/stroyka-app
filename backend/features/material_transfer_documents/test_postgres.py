"""Real PostgreSQL proof for immutable M-15 issue and receipt parties."""

import importlib.util
import os
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch


@unittest.skipUnless(os.environ.get("SUPPLY_CHAIN_RUN_POSTGRES") == "1",
                     "Requires fresh explicitly provisioned PostgreSQL")
class MaterialTransferDocumentsPostgresTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from backend.features.supplier_access.test_postgres_chain_support import build_fixture
        cls.main, cls.fixture, cleanup = build_fixture()
        cls.addClassCleanup(cleanup)
        alembic = ModuleType("alembic")
        alembic.op = None
        path = Path(__file__).resolve().parents[3] / "migrations" / "versions" / "0078_material_transfer_parties.py"
        spec = importlib.util.spec_from_file_location("material_transfer_parties_migration", path)
        migration = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"alembic": alembic}):
            spec.loader.exec_module(migration)
        conn = cls.main.get_db()
        try:
            with conn, conn.cursor() as cur, patch.object(migration, "op", SimpleNamespace(execute=cur.execute)):
                migration.upgrade()
        finally:
            conn.close()

    def sql(self, statement, params=(), *, dict_rows=False):
        from psycopg2.extras import RealDictCursor
        conn = self.main.get_db()
        try:
            with conn, conn.cursor(cursor_factory=RealDictCursor if dict_rows else None) as cur:
                cur.execute(statement, params)
                return cur.fetchall() if cur.description else []
        finally:
            conn.close()

    def setUp(self):
        self.sql("DELETE FROM material_transfers")
        self.sql("""INSERT INTO company_requisites(company_id,full_name,inn,legal_address)
            VALUES(2,'ООО Компания','2611008712','Ставрополь')
            ON CONFLICT(company_id) DO UPDATE SET full_name=EXCLUDED.full_name,inn=EXCLUDED.inn,
            legal_address=EXCLUDED.legal_address""")
        self.receiver_id = self.sql("""INSERT INTO users(name,email,password,role,active,company_id,
            project_id,project_name,assigned_projects,assigned_packages)
            VALUES('Точный мастер','transfer-receiver@test.invalid','x','мастер',TRUE,2,%s,%s,%s,%s)
            RETURNING id""", (self.fixture["projectId"], self.fixture["project"],
                               '["'+self.fixture["project"]+'"]', '["Основная"]'))[0][0]

    def tearDown(self):
        self.sql("DELETE FROM material_transfers")
        self.sql("DELETE FROM users WHERE email='transfer-receiver@test.invalid'")

    def insert_transfer(self):
        return self.sql("""INSERT INTO material_transfers(company_id,project_id,project_name,from_location,
            to_user_id,to_person,to_person_role,work_package,material_name,quantity,unit,transfer_date,
            notes,created_by,status,signed)
            VALUES(2,%s,%s,%s,%s,'Точный мастер','мастер','Основная','Краска',5,'кг',CURRENT_DATE,
            'По заявке','Прораб','Активна',FALSE) RETURNING id""",
            (self.fixture["projectId"], self.fixture["project"], self.fixture["project"], self.receiver_id))[0][0]

    def test_profiles_change_without_changing_signed_m15_and_core_is_immutable(self):
        from backend.features.material_transfer_documents.storage import (
            freeze_material_transfer_issue, freeze_material_transfer_receipt,
        )
        transfer_id = self.insert_transfer()
        conn = self.main.get_db()
        try:
            from psycopg2.extras import RealDictCursor
            with conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
                freeze_material_transfer_issue(cur, transfer_id,
                    {"id": self.fixture["users"]["foreman"]["id"], "name": "Прораб", "role": "прораб"})
                freeze_material_transfer_receipt(cur, transfer_id,
                    {"id": self.receiver_id, "name": "Точный мастер", "role": "мастер"})
        finally:
            conn.close()
        before = self.sql("""SELECT issue_party_snapshot_json,issue_party_snapshot_hash,
            receipt_party_snapshot_json,receipt_party_snapshot_hash,signed
            FROM material_transfers WHERE id=%s""", (transfer_id,))[0]
        self.sql("UPDATE company_requisites SET full_name='Новое имя' WHERE company_id=2")
        self.sql("UPDATE users SET name='Новое имя мастера' WHERE id=%s", (self.receiver_id,))
        self.assertEqual(self.sql("""SELECT issue_party_snapshot_json,issue_party_snapshot_hash,
            receipt_party_snapshot_json,receipt_party_snapshot_hash,signed
            FROM material_transfers WHERE id=%s""", (transfer_id,))[0], before)
        conn = self.main.get_db()
        try:
            with self.assertRaises(Exception), conn.cursor() as cur:
                cur.execute("UPDATE material_transfers SET quantity=99 WHERE id=%s", (transfer_id,))
        finally:
            conn.rollback()
            conn.close()


if __name__ == "__main__":
    unittest.main()
