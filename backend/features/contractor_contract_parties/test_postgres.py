"""Real PostgreSQL proof for exact ownership and immutable contractor contracts."""

import importlib.util
import os
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch


@unittest.skipUnless(os.environ.get("SUPPLY_CHAIN_RUN_POSTGRES") == "1",
                     "Requires fresh explicitly provisioned PostgreSQL")
class ContractorContractPartiesPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from backend.features.supplier_access.test_postgres_chain_support import build_fixture
        from fastapi.testclient import TestClient
        cls.main, cls.f, cleanup = build_fixture()
        cls.addClassCleanup(cleanup)
        cls.client = TestClient(cls.main.app)
        cls.addClassCleanup(cls.client.close)
        path = Path(__file__).resolve().parents[3] / "migrations/versions/0076_contractor_contract_parties.py"
        spec = importlib.util.spec_from_file_location("contractor_contract_test_migration", path)
        migration = importlib.util.module_from_spec(spec)
        alembic = ModuleType("alembic"); alembic.op = None
        with patch.dict(sys.modules, {"alembic": alembic}):
            spec.loader.exec_module(migration)
        conn = cls.main.get_db()
        try:
            with conn, conn.cursor() as cur, patch.object(migration, "op", SimpleNamespace(execute=cur.execute)):
                migration.upgrade()
        finally:
            conn.close()

    def sql(self, statement, params=()):
        conn = self.main.get_db()
        try:
            with conn, conn.cursor() as cur:
                cur.execute(statement, params)
                return cur.fetchall() if cur.description else []
        finally:
            conn.close()

    def setUp(self):
        self.sql("DELETE FROM brigade_contracts")
        self.sql("DELETE FROM file_ownership")
        self.sql("""INSERT INTO company_requisites(company_id,full_name,inn,kpp,ogrn,legal_address,
            director_name,director_position,basis,bank_name,bik,rs,ks)
            VALUES(2,'ООО Заказчик','2611008712','261101001','1234567890123','Ставрополь',
            'Петров П.П.','Директор','Устава','Банк','044525104',%s,%s)
            ON CONFLICT(company_id) DO UPDATE SET full_name=EXCLUDED.full_name,inn=EXCLUDED.inn,
            legal_address=EXCLUDED.legal_address,director_name=EXCLUDED.director_name,
            director_position=EXCLUDED.director_position,basis=EXCLUDED.basis""", ("4"*20, "3"*20))
        worker = self.f["users"]["foreman"]
        self.sql("""INSERT INTO master_profiles(user_id,full_name,passport,inn,contract_type,
            bank_account,bank_name,phone,ogrnip,profile_completed)
            VALUES(%s,%s,'07 01 123456, МВД','263200000001','ИП',%s,'Банк ИП','+79990000000',%s,TRUE)
            ON CONFLICT(user_id) DO UPDATE SET full_name=EXCLUDED.full_name,passport=EXCLUDED.passport,
            inn=EXCLUDED.inn,contract_type=EXCLUDED.contract_type,bank_account=EXCLUDED.bank_account,
            bank_name=EXCLUDED.bank_name,ogrnip=EXCLUDED.ogrnip""",
            (worker["id"], worker["name"], "4"*20, "3"*15))
        self.contract_id = self.sql("""INSERT INTO brigade_contracts(company_id,project_id,project_name,
            brigade_name,contractor_type,contractor_id,status)
            VALUES(2,%s,%s,%s,'ИП',%s,'Черновик') RETURNING id""",
            (self.f["projectId"], self.f["project"], worker["name"], worker["id"]))[0][0]

    def file(self, company_id=2):
        return self.sql("""INSERT INTO file_ownership(company_id,project_id,file_url,storage_key,context,
            original_name,content_type,uploaded_by_id,uploaded_by,deletion_status)
            VALUES(%s,%s,%s,'companies/test/signed.pdf','brigade-contracts','signed.pdf','application/pdf',
            %s,'Director','active') RETURNING id""", (company_id, self.f["projectId"],
            "/uploads/signed-%s.pdf" % company_id, self.f["users"]["director"]["id"]))[0][0]

    def post(self, scan_url, expected=200):
        token = self.main.create_auth_token(self.f["users"]["director"], two_factor_passed=True)
        response = self.client.post("/brigade-contracts/%s/signature" % self.contract_id,
            json={"scanUrl": scan_url}, headers={"Authorization": "Bearer " + token,
            "X-Company-Id": "2", "X-Company-Mode": "company"})
        self.assertEqual(response.status_code, expected, response.text)
        return response.json()

    def test_signing_retains_exact_file_and_database_prevents_party_drift(self):
        file_id = self.file()
        result = self.post("/tenant-files/%s/content" % file_id)
        self.assertEqual(result["partySnapshot"]["contractor"]["userId"], self.f["users"]["foreman"]["id"])
        row = self.sql("""SELECT status,contract_scan_url,party_snapshot_hash,
            party_snapshot_json->'customer'->>'fullName' FROM brigade_contracts WHERE id=%s""",
            (self.contract_id,))[0]
        self.assertEqual(row[0], "Подписан")
        self.assertEqual(row[1], "/tenant-files/%s/content" % file_id)
        self.assertEqual(len(row[2]), 64)
        self.assertEqual(row[3], "ООО Заказчик")
        self.assertTrue(self.sql("SELECT retained_at IS NOT NULL FROM file_ownership WHERE id=%s", (file_id,))[0][0])
        conn = self.main.get_db()
        try:
            with self.assertRaises(Exception), conn.cursor() as cur:
                cur.execute("UPDATE brigade_contracts SET brigade_name='Подмена' WHERE id=%s", (self.contract_id,))
        finally:
            conn.rollback(); conn.close()

    def test_foreign_company_file_is_rejected_without_contract_change(self):
        foreign_file = self.file(company_id=3)
        self.post("/tenant-files/%s/content" % foreign_file, expected=403)
        self.assertEqual(self.sql("SELECT status,party_snapshot_json FROM brigade_contracts WHERE id=%s",
                                  (self.contract_id,)), [("Черновик", None)])


if __name__ == "__main__":
    unittest.main()
