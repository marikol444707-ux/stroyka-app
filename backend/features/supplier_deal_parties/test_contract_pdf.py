"""Synthetic PDFs exercise the real worker process, never customer documents."""
import io
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from pypdf import PdfReader, PdfWriter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from .contract_pdf import extract_pdf_text
from .contract_extraction import extract_contract_parties
from .test_contract_extraction import TEXT, IDENTITIES


def synthetic_pdf(pages=None, encrypted=False):
    output = io.BytesIO()
    fonts = [Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'),
             Path('/System/Library/Fonts/Supplemental/Arial.ttf')]
    font = next((path for path in fonts if path.is_file()), None)
    if font is None:
        raise RuntimeError('Synthetic Cyrillic PDF tests require DejaVu Sans or Arial')
    pdfmetrics.registerFont(TTFont('ContractTest', str(font)))
    document = canvas.Canvas(output)
    for text in pages if pages is not None else [TEXT]:
        document.setFillColorRGB(1, 1, 1)
        document.rect(0, 0, 595.28, 841.89, fill=1, stroke=0)
        document.setFillColorRGB(0, 0, 0)
        block = document.beginText(40, 800)
        block.setFont('ContractTest', 10)
        for line in text.splitlines():
            block.textLine(line)
        document.drawText(block)
        document.showPage()
    document.save()
    if encrypted:
        writer = PdfWriter()
        writer.append(PdfReader(io.BytesIO(output.getvalue())))
        writer.encrypt('test-only')
        output = io.BytesIO()
        writer.write(output)
    return output.getvalue()


class ContractPdfTest(unittest.TestCase):
    def assert_error(self, content, status):
        with self.assertRaises(HTTPException) as caught:
            extract_pdf_text(content)
        self.assertEqual(caught.exception.status_code, status)

    def test_real_cyrillic_pdf_keeps_three_party_accounts_separate(self):
        text = extract_pdf_text(synthetic_pdf())
        result = extract_contract_parties(text, IDENTITIES)
        self.assertEqual(result['parties']['buyer']['fields']['fullName']['value'], 'ООО «Заказчик»')
        for side, ending in [('buyer', '1'), ('payer', '2'), ('supplier', '3')]:
            self.assertTrue(result['parties'][side]['fields']['rs']['value'].endswith(ending))

    def test_pdf_without_text_requires_ocr(self):
        self.assert_error(synthetic_pdf(['']), 422)

    def test_partly_unreadable_pdf_does_not_return_partial_result(self):
        self.assert_error(synthetic_pdf([TEXT, '']), 422)

    def test_encrypted_pdf_is_not_decrypted_or_guessed(self):
        self.assert_error(synthetic_pdf(encrypted=True), 422)

    def test_page_limit_rejects_whole_document(self):
        self.assert_error(synthetic_pdf(['page'] * 31), 413)

    def test_invalid_signature_and_damaged_pdf_rejected(self):
        self.assert_error(b'not a pdf', 422)
        self.assert_error(b'%PDF-1.7\nbroken', 422)

    def test_input_size_limit_before_worker(self):
        with patch('backend.features.supplier_deal_parties.contract_pdf.subprocess.run') as run:
            self.assert_error(b'%PDF-' + b'x' * (10 * 1024 * 1024), 413)
            run.assert_not_called()

    def test_timeout_is_sanitized(self):
        with patch('backend.features.supplier_deal_parties.contract_pdf.subprocess.run',
                   side_effect=subprocess.TimeoutExpired('private path', 10)):
            self.assert_error(b'%PDF-1.7', 504)

    def test_missing_worker_dependency_is_not_empty_success(self):
        with patch('backend.features.supplier_deal_parties.contract_pdf.subprocess.run',
                   return_value=subprocess.CompletedProcess([], 3, b'')):
            self.assert_error(b'%PDF-1.7', 503)

    def test_corrupt_text_mapping_is_not_accepted(self):
        with patch('backend.features.supplier_deal_parties.contract_pdf.subprocess.run',
                   return_value=subprocess.CompletedProcess([], 0, b'\x00\x00: 123')):
            self.assert_error(b'%PDF-1.7', 422)
