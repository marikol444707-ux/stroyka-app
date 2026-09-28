import io
import unittest
import zipfile
from fastapi import HTTPException
from .contract_document import extract_document_text

class ContractDocumentTests(unittest.TestCase):
    def docx(self, content):
        out=io.BytesIO()
        with zipfile.ZipFile(out,'w') as z:z.writestr('word/document.xml',content)
        return out.getvalue()
    def test_docx_preserves_paragraphs_and_unicode(self):
        data=self.docx('<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Поставщик</w:t></w:r></w:p><w:p><w:r><w:t>ИНН: 7701234567</w:t></w:r></w:p></w:body></w:document>')
        self.assertEqual(extract_document_text(data,'.docx'),'Поставщик\nИНН: 7701234567')
    def test_docx_embedded_images_not_silently_omitted(self):
        data=self.docx('<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:drawing/></w:document>')
        with self.assertRaises(HTTPException):extract_document_text(data,'.docx')
    def test_disguised_and_unsupported_files_fail(self):
        for suffix in ('.jpg','.png','.doc','.docx','.exe'):
            with self.subTest(suffix=suffix),self.assertRaises(HTTPException):extract_document_text(b'not a document',suffix)

    def test_scanner_pdf_duplicate_metadata_can_still_be_read(self):
        import re
        from .test_contract_pdf import synthetic_pdf
        data=synthetic_pdf(['Договор тест'])
        data,count=re.subn(rb'/Info\s+\d+\s+0\s+R',lambda m:m[0]+b' '+m[0],data,count=1)
        self.assertEqual(count,1)
        self.assertIn('Договор тест',extract_document_text(data,'.pdf'))
