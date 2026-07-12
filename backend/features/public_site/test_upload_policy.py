import unittest

from fastapi import HTTPException

from backend.features.public_site.upload_policy import (
    MAX_PUBLIC_LEAD_FILE_BYTES,
    public_upload_rate_exceeded,
    validate_public_lead_file,
)


class PublicLeadUploadPolicyTests(unittest.TestCase):
    def test_accepts_pdf_with_matching_signature(self):
        result = validate_public_lead_file(
            filename="plan.pdf",
            content_type="application/pdf",
            content=b"%PDF-1.7\nexample",
        )

        self.assertEqual(result["filename"], "plan.pdf")
        self.assertEqual(result["contentType"], "application/pdf")

    def test_rejects_executable_renamed_as_pdf(self):
        with self.assertRaises(HTTPException) as error:
            validate_public_lead_file(
                filename="plan.pdf",
                content_type="application/pdf",
                content=b"MZ\x90\x00executable",
            )

        self.assertEqual(error.exception.status_code, 415)

    def test_rejects_disallowed_extension(self):
        with self.assertRaises(HTTPException) as error:
            validate_public_lead_file(
                filename="estimate.xlsx",
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                content=b"PK\x03\x04example",
            )

        self.assertEqual(error.exception.status_code, 415)

    def test_rejects_oversized_file(self):
        with self.assertRaises(HTTPException) as error:
            validate_public_lead_file(
                filename="photo.jpg",
                content_type="image/jpeg",
                content=b"\xff\xd8\xff" + b"0" * MAX_PUBLIC_LEAD_FILE_BYTES,
            )

        self.assertEqual(error.exception.status_code, 413)

    def test_strips_path_from_filename(self):
        result = validate_public_lead_file(
            filename="../../house.png",
            content_type="image/png",
            content=b"\x89PNG\r\n\x1a\ncontent",
        )

        self.assertEqual(result["filename"], "house.png")

    def test_upload_rate_is_limited_to_ten_files_per_hour(self):
        self.assertFalse(public_upload_rate_exceeded(9))
        self.assertTrue(public_upload_rate_exceeded(10))


if __name__ == "__main__":
    unittest.main()
