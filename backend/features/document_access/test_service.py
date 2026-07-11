import unittest

from fastapi import HTTPException

from backend.features.document_access.service import (
    document_storage_namespace,
    require_document_parent_company,
    require_document_upload_actor,
)


class DocumentAccessTests(unittest.TestCase):
    def test_upload_requires_one_concrete_company(self):
        actor = require_document_upload_actor([{"company_id": "4", "role": "прораб"}])
        self.assertEqual(actor["companyId"], 4)

        for actors in ([], [{"companyId": 1}, {"companyId": 2}]):
            with self.subTest(actors=actors), self.assertRaises(HTTPException) as raised:
                require_document_upload_actor(actors)
            self.assertEqual(raised.exception.status_code, 409)

    def test_document_must_match_parent_company(self):
        self.assertEqual(require_document_parent_company(3, 3), 3)
        with self.assertRaises(HTTPException) as raised:
            require_document_parent_company(3, 4)
        self.assertEqual(raised.exception.status_code, 409)

    def test_storage_namespace_uses_ids_not_project_name(self):
        self.assertEqual(
            document_storage_namespace(2, 17, "Одинаковое имя", "invoice scan"),
            "company-2-project-17-invoice-scan",
        )
        self.assertEqual(
            document_storage_namespace(2, None, "", "general"),
            "company-2-common-general",
        )


if __name__ == "__main__":
    unittest.main()
