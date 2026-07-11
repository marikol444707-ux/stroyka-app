import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import HTTPException

from backend.features.document_access.service import (
    delete_document_local_file,
    document_local_path,
    open_document_local_file,
    document_project_reference,
    document_response_policy,
    document_storage_namespace,
    require_document_storage_identity,
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

    def test_local_file_is_opened_once_with_size_limit(self):
        with TemporaryDirectory() as upload_dir:
            expected = Path(upload_dir) / "company-4-common-general" / "general" / "file.png"
            expected.parent.mkdir(parents=True)
            expected.write_bytes(b"png-content")

            stream, size = open_document_local_file(
                upload_dir,
                "/uploads/company-4-common-general/general/file.png",
                1024,
            )
            try:
                self.assertEqual(size, len(b"png-content"))
                self.assertEqual(stream.read(), b"png-content")
            finally:
                stream.close()

            with self.assertRaises(HTTPException) as error:
                open_document_local_file(
                    upload_dir,
                    "/uploads/company-4-common-general/general/file.png",
                    2,
                )
            self.assertEqual(error.exception.status_code, 413)

    def test_local_file_open_rejects_symlink_target(self):
        with TemporaryDirectory() as upload_dir, TemporaryDirectory() as outside_dir:
            outside = Path(outside_dir) / "secret.txt"
            outside.write_text("secret", encoding="utf-8")
            link = Path(upload_dir) / "company-4-common-general" / "general" / "file.png"
            link.parent.mkdir(parents=True)
            link.symlink_to(outside)

            with self.assertRaises(HTTPException) as error:
                open_document_local_file(
                    upload_dir,
                    "/uploads/company-4-common-general/general/file.png",
                    1024,
                )
            self.assertEqual(error.exception.status_code, 409)

    def test_local_delete_uses_no_follow_parent_descriptor(self):
        with TemporaryDirectory() as upload_dir:
            target = Path(upload_dir) / "company-4-common-general" / "general" / "file.png"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"png")
            self.assertTrue(delete_document_local_file(
                upload_dir,
                "/uploads/company-4-common-general/general/file.png",
            ))
            self.assertFalse(target.exists())

        with TemporaryDirectory() as upload_dir, TemporaryDirectory() as outside_dir:
            outside = Path(outside_dir) / "general" / "file.png"
            outside.parent.mkdir(parents=True)
            outside.write_bytes(b"secret")
            link = Path(upload_dir) / "company-4-common-general"
            link.symlink_to(Path(outside_dir), target_is_directory=True)

            with self.assertRaises(HTTPException) as error:
                delete_document_local_file(
                    upload_dir,
                    "/uploads/company-4-common-general/general/file.png",
                )
            self.assertEqual(error.exception.status_code, 409)
            self.assertTrue(outside.exists())

    def test_response_policy_only_opens_safe_raster_images_and_pdf_inline(self):
        self.assertEqual(
            document_response_policy("photo.png"),
            ("photo.png", "image/png", "inline"),
        )
        self.assertEqual(
            document_response_policy("report.pdf"),
            ("report.pdf", "application/pdf", "inline"),
        )
        self.assertEqual(
            document_response_policy("../attack.html"),
            ("attack.html", "application/octet-stream", "attachment"),
        )
        self.assertEqual(
            document_response_policy("vector.svg"),
            ("vector.svg", "application/octet-stream", "attachment"),
        )

    def test_storage_identity_must_match_registered_tenant_namespace(self):
        self.assertEqual(
            require_document_storage_identity(
                4,
                17,
                "smoke tenant files",
                "/uploads/company-4-project-17-smoke-tenant-files/smoke-tenant-files/2026/07/11/file.png",
                "",
            ),
            "company-4-project-17-smoke-tenant-files",
        )
        self.assertEqual(
            require_document_storage_identity(
                4,
                17,
                "smoke tenant files",
                "https://storage.example/file.png",
                "archive/company-4-project-17-smoke-tenant-files/smoke-tenant-files/file.png",
                s3_prefix=("uploads", "archive"),
                expected_s3_urls=("https://storage.example/file.png",),
            ),
            "company-4-project-17-smoke-tenant-files",
        )
        self.assertEqual(
            require_document_storage_identity(
                4,
                17,
                "smoke tenant files",
                "https://storage.example/file.png",
                "uploads/company-4-project-17-smoke-tenant-files/smoke-tenant-files/2026/07/11/file.png",
                s3_prefix="uploads",
                expected_s3_urls=("https://storage.example/file.png",),
            ),
            "company-4-project-17-smoke-tenant-files",
        )

    def test_storage_identity_rejects_another_company_namespace(self):
        for file_url, storage_key in (
            (
                "/uploads/company-5-project-17-smoke-tenant-files/smoke-tenant-files/file.png",
                "",
            ),
            (
                "https://storage.example/file.png",
                "uploads/company-5-project-17-smoke-tenant-files/smoke-tenant-files/file.png",
            ),
            (
                "/uploads/company-4-project-17-smoke-tenant-files/%2e%2e/company-5/file.png",
                "",
            ),
            (
                "https://storage.example/file.png",
                "uploads/company-4-project-17-smoke-tenant-files/../company-5/file.png",
            ),
            (
                "https://other.example/file.png",
                "uploads/company-4-project-17-smoke-tenant-files/smoke-tenant-files/file.png",
            ),
            (
                "https://storage.example/file.png",
                "archive/company-4-project-17-smoke-tenant-files/smoke-tenant-files/file.png",
            ),
            (
                "/uploads/company-4-project-17-smoke-tenant-files/smoke-tenant-files/file.png?download=1",
                "",
            ),
        ):
            with self.subTest(storage_key=storage_key), self.assertRaises(HTTPException) as error:
                require_document_storage_identity(
                    4,
                    17,
                    "smoke tenant files",
                    file_url,
                    storage_key,
                    s3_prefix="uploads",
                    expected_s3_urls=("https://storage.example/file.png",) if storage_key else (),
                )
            self.assertEqual(error.exception.status_code, 409)


if __name__ == "__main__":
    unittest.main()
