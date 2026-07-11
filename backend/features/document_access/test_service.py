import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import HTTPException

from backend.features.document_access.service import (
    document_local_path,
    document_project_reference,
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

    def test_project_name_without_exact_id_stays_company_common(self):
        self.assertEqual(document_project_reference(None, "Основной склад"), (None, ""))
        self.assertEqual(document_project_reference(None, "CRM"), (None, ""))
        self.assertEqual(document_project_reference(17, "Лицей"), (17, "Лицей"))

    def test_local_file_path_stays_inside_upload_root(self):
        with TemporaryDirectory() as upload_dir:
            expected = Path(upload_dir) / "company-4" / "invoice.pdf"
            expected.parent.mkdir(parents=True)
            expected.write_bytes(b"pdf")

            actual = document_local_path(upload_dir, "/uploads/company-4/invoice.pdf")

            self.assertEqual(actual, expected.resolve())

    def test_local_file_path_rejects_traversal_and_non_local_urls(self):
        with TemporaryDirectory() as upload_dir:
            for file_url in (
                "/uploads/../secret.txt",
                "/uploads/%2e%2e/secret.txt",
                "https://storage.example/file.pdf",
            ):
                with self.subTest(file_url=file_url), self.assertRaises(HTTPException) as raised:
                    document_local_path(upload_dir, file_url)
                self.assertEqual(raised.exception.status_code, 409)


if __name__ == "__main__":
    unittest.main()
