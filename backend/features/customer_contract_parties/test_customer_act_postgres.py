"""Real PostgreSQL proof for signed KS party and contract snapshots."""

import importlib.util
import os
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch


@unittest.skipUnless(os.environ.get("SUPPLY_CHAIN_RUN_POSTGRES") == "1",
                     "Requires fresh explicitly provisioned PostgreSQL")
class CustomerActPartiesPostgresTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from backend.features.supplier_access.test_postgres_chain_support import build_fixture
        from fastapi.testclient import TestClient
        cls.main, cls.fixture, cleanup = build_fixture()
        cls.addClassCleanup(cleanup)
        cls.client = TestClient(cls.main.app)
        cls.addClassCleanup(cls.client.close)
        alembic = ModuleType("alembic")
        alembic.op = None
        conn = cls.main.get_db()
        try:
            with conn, conn.cursor() as cur:
                # The isolated supply fixture intentionally bootstraps only its own legacy surface.
                cur.execute("""ALTER TABLE project_documents
                    ADD COLUMN IF NOT EXISTS company_id INTEGER,
                    ADD COLUMN IF NOT EXISTS project_id INTEGER,
                    ADD COLUMN IF NOT EXISTS created_by_user_id INTEGER;
                    ALTER TABLE file_ownership ADD COLUMN IF NOT EXISTS retained_at TIMESTAMPTZ""")
            for filename in ("0075_customer_contract_parties.py", "0077_customer_act_contract_basis.py"):
                path = Path(__file__).resolve().parents[3] / "migrations" / "versions" / filename
                spec = importlib.util.spec_from_file_location("customer_act_" + filename[:-3], path)
                migration = importlib.util.module_from_spec(spec)
                with patch.dict(sys.modules, {"alembic": alembic}):
                    spec.loader.exec_module(migration)
                with conn, conn.cursor() as cur, patch.object(
                        migration, "op", SimpleNamespace(execute=cur.execute)):
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
        self.sql("DELETE FROM project_documents")
        self.sql("DELETE FROM file_ownership")
        self.sql("UPDATE projects SET client_id=NULL WHERE company_id=2")
        self.sql("DELETE FROM clients")
        self.sql("""INSERT INTO company_requisites(company_id,full_name,inn,kpp,ogrn,legal_address,
            director_name,director_position,basis,bank_name,bik,rs,ks)
            VALUES(2,'ООО Исполнитель','2611008712','261101001','1234567890123','Ставрополь',
            'Петров П.П.','Директор','Устава','Банк','044525104',%s,%s)
            ON CONFLICT(company_id) DO UPDATE SET full_name=EXCLUDED.full_name,inn=EXCLUDED.inn,
            legal_address=EXCLUDED.legal_address,director_name=EXCLUDED.director_name,
            director_position=EXCLUDED.director_position,basis=EXCLUDED.basis""", ("4" * 20, "3" * 20))
        self.client_id = self.sql("""INSERT INTO clients(company_id,name,inn,kpp,ogrn,legal_address,
            director_name,director_position,basis,bank_name,bik,rs,ks,status)
            VALUES(2,'ООО Заказчик','2632090186','263201001','1092632000001','Пятигорск',
            'Иванов И.И.','Директор','Устава','Банк 2','044525411',%s,%s,'Активный') RETURNING id""",
            ("5" * 20, "6" * 20))[0][0]
        self.sql("UPDATE projects SET client_id=%s WHERE id=%s AND company_id=2",
                 (self.client_id, self.fixture["projectId"]))

    def file(self, suffix):
        return self.sql("""INSERT INTO file_ownership(company_id,project_id,file_url,storage_key,context,
            original_name,content_type,uploaded_by_id,uploaded_by,deletion_status)
            VALUES(2,%s,%s,%s,'project-documents',%s,'application/pdf',%s,'Director','active') RETURNING id""",
            (self.fixture["projectId"], "/uploads/" + suffix + ".pdf", "companies/test/" + suffix + ".pdf",
             suffix + ".pdf", self.fixture["users"]["director"]["id"]))[0][0]

    def post_document(self, payload, expected=200):
        token = self.main.create_auth_token(self.fixture["users"]["director"], two_factor_passed=True)
        response = self.client.post("/project-documents", json={
            "projectId": self.fixture["projectId"], **payload,
        }, headers={"Authorization": "Bearer " + token, "X-Company-Id": "2",
                    "X-Company-Mode": "company"})
        self.assertEqual(response.status_code, expected, response.text)
        return response.json()

    def signed_contract(self):
        file_id = self.file("customer-contract")
        return self.post_document({
            "side": "customer", "docType": "Договор", "number": "15",
            "docDate": "2026-10-01", "counterparty": "ООО Заказчик",
            "signStatus": "Подписан", "scanUrl": f"/tenant-files/{file_id}/content",
        })["id"]

    def test_signed_ks_keeps_exact_contract_parties_after_profiles_change(self):
        contract_id = self.signed_contract()
        act_file = self.file("ks-2")
        act_id = self.post_document({
            "side": "customer", "docType": "Акт КС-2", "number": "2",
            "docDate": "2026-10-01", "counterparty": "ООО Заказчик", "amount": 1200,
            "signStatus": "Подписан", "scanUrl": f"/tenant-files/{act_file}/content",
            "basisContractDocumentId": contract_id,
        })["id"]
        before = self.sql("""SELECT party_snapshot_json,party_snapshot_hash,basis_contract_document_id
            FROM project_documents WHERE id=%s""", (act_id,))[0]
        self.assertEqual(before[0]["customer"]["fullName"], "ООО Заказчик")
        self.assertEqual(before[0]["contractBasis"]["documentId"], contract_id)
        self.assertEqual(before[2], contract_id)
        self.assertTrue(self.sql("SELECT retained_at IS NOT NULL FROM file_ownership WHERE id=%s", (act_file,))[0][0])
        self.sql("UPDATE clients SET name='Новое имя' WHERE id=%s", (self.client_id,))
        self.assertEqual(self.sql("SELECT party_snapshot_json,party_snapshot_hash FROM project_documents WHERE id=%s",
                                  (act_id,))[0], before[:2])
        conn = self.main.get_db()
        try:
            with self.assertRaises(Exception), conn.cursor() as cur:
                cur.execute("UPDATE project_documents SET number='Подмена' WHERE id=%s", (act_id,))
        finally:
            conn.rollback()
            conn.close()

    def test_signed_ks_rejects_missing_basis_without_leaving_a_row(self):
        act_file = self.file("ks-without-contract")
        before = self.sql("SELECT COUNT(*) FROM project_documents")[0][0]
        self.post_document({
            "side": "customer", "docType": "Акт КС-3", "number": "3",
            "signStatus": "Подписан", "scanUrl": f"/tenant-files/{act_file}/content",
        }, expected=409)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM project_documents")[0][0], before)


if __name__ == "__main__":
    unittest.main()
