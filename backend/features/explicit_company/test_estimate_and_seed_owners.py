import unittest
from pathlib import Path

from fastapi import HTTPException

from backend.features.explicit_company.bootstrap_users import (
    BOOTSTRAP_USERS,
    seed_bootstrap_users,
)
from backend.features.explicit_company.estimate_owner import explicit_estimate_company_id
from backend.features.explicit_company.insert_company_guard import (
    missing_company_inserts_in_sql,
    scan_backend_inserts,
)

ROOT = Path(__file__).resolve().parents[3]


class Cursor:
    def __init__(self, company):
        self.company = company
        self.calls = []
        self._row = None

    def execute(self, sql, params=()):
        text = " ".join(sql.split())
        self.calls.append((text, params))
        if text.startswith("SELECT id"):
            self._row = self.company

    def fetchone(self):
        return self._row


class EstimateOwnerTests(unittest.TestCase):
    def test_generated_estimate_uses_the_caller_company(self):
        self.assertEqual(explicit_estimate_company_id(7), 7)
        self.assertEqual(explicit_estimate_company_id(7, 7), 7)

    def test_generated_estimate_rejects_another_companys_project(self):
        with self.assertRaises(HTTPException) as error:
            explicit_estimate_company_id(7, 8)
        self.assertEqual(error.exception.status_code, 409)
        with self.assertRaises(HTTPException):
            explicit_estimate_company_id(None)

    def test_ai_estimate_insert_stores_company_id(self):
        source = (ROOT / "backend" / "main.py").read_text(encoding="utf-8")
        start = source.index("def ai_generate_estimate")
        end = source.index("def pricelist_from_estimate", start)
        body = source[start:end]
        self.assertIn("(company_id, project_id, project_name, name, version, sections_json, smeta_type, work_package, status)", body)
        self.assertIn("explicit_estimate_company_id", body)
        self.assertNotIn("INSERT INTO estimates\n                   (project_id, project_name", body)


class BootstrapUserTests(unittest.TestCase):
    def test_seed_uses_the_bootstrap_company_and_skips_when_it_is_absent(self):
        absent = Cursor(None)
        result = seed_bootstrap_users(absent, [("Директор", "admin@stroyka.ru", "hash", "директор")])
        self.assertEqual(result["companyId"], None)
        self.assertEqual(len(absent.calls), 1)

        present = Cursor((7, 3))
        users = [
            (name, email, "hash", role)
            for name, email, _password, role in BOOTSTRAP_USERS
        ]
        result = seed_bootstrap_users(present, users)
        self.assertEqual(result["companyId"], 7)
        inserts = [params for sql, params in present.calls if sql.startswith("INSERT INTO users")]
        self.assertEqual(len(inserts), 4)
        for params in inserts:
            self.assertEqual(params[4], 7)
            self.assertIn("company_id", present.calls[1][0])
        updates = [params for sql, params in present.calls if sql.startswith("UPDATE users")]
        self.assertEqual(updates, [(7, email) for _name, email, _password, role in BOOTSTRAP_USERS])
        membership = [params for sql, params in present.calls if sql.startswith("INSERT INTO user_company_roles")]
        self.assertEqual(membership, [([email for _name, email, _password, _role in BOOTSTRAP_USERS], 7)])
        self.assertNotIn("company_id=1", " ".join(sql for sql, _params in present.calls))


class InsertCompanyGuardTests(unittest.TestCase):
    def test_column_list_must_name_company_id(self):
        self.assertEqual(
            missing_company_inserts_in_sql(
                "INSERT INTO estimates (project_id, project_name) VALUES (%s,%s)"
            ),
            ["estimates"],
        )
        self.assertEqual(
            missing_company_inserts_in_sql(
                "INSERT INTO estimates SELECT project_id, project_name FROM projects"
            ),
            ["estimates"],
        )
        self.assertEqual(
            missing_company_inserts_in_sql(
                "INSERT INTO estimates (company_id, project_name) VALUES (%s,%s)"
            ),
            [],
        )
        self.assertEqual(
            missing_company_inserts_in_sql("COPY estimates (project_name) FROM STDIN"),
            ["estimates"],
        )

    def test_production_inserts_name_company_id(self):
        self.assertEqual(scan_backend_inserts(ROOT / "backend"), [])


if __name__ == "__main__":
    unittest.main()
