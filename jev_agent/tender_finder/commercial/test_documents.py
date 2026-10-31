"""Synthetic originals; pure parser tests do NOT establish sandbox availability."""
from dataclasses import replace
import hashlib
import io
import zipfile
import unittest
from unittest.mock import Mock,patch

from .document_worker import extract
from .documents import Attachment,Download,read_attachment,extract_isolated,sandbox_command
from .model import Fact,Document
from .policy import assess
from .terms import DirectReview,apply_review,enrich,valid_inn
from .test_commercial import NOW,SCOPE,HOSTS,candidate

URL='https://www.b2b-center.ru/documents/synthetic-contract.docx'
TEXT='''Условия оплаты: Постоплата 30 дней после приёмки
Банковская гарантия: 10% цены договора
Удержания: 5% до завершения гарантийного срока
Строительная СРО: Требуется
Проектная СРО: Требуется
Лицензия МЧС: Не требуется
'''


def docx(text,extra=None):
    from xml.sax.saxutils import escape
    xml='<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
    xml+=''.join('<w:p><w:r><w:t>'+escape(line)+'</w:t></w:r></w:p>' for line in text.splitlines())
    xml+='</w:body></w:document>'
    output=io.BytesIO()
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
        for key,value in [('word/document.xml',xml),*sorted((extra or {}).items())]:
            info=zipfile.ZipInfo(key,date_time=(2026,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
            archive.writestr(info,value)
    return output.getvalue()


def linked():
    item=candidate()
    card=replace(item.documents[0],text=item.documents[0].text+'\nПроект договора: '+URL)
    return replace(item,documents=(card,))


def reference():return Attachment('contract','b2b',URL,'Проект договора','contract','.docx','card','Проект договора: '+URL)


class WorkerTests(unittest.TestCase):
    def test_real_docx_parser_extracts_paragraphs_and_never_executes_hyperlinks(self):
        result=extract(docx(TEXT,{'word/_rels/document.xml.rels':'<external href="file:///etc/passwd"/>'}),'.docx')
        self.assertTrue(result['complete'])
        self.assertEqual(result['blocks'][0]['locator'],'абз. 1')
        self.assertIn('Постоплата',result['blocks'][0]['text'])
        self.assertNotIn('root:',str(result))

    def test_pdf_text_pages_and_image_only_pages(self):
        from reportlab.pdfgen.canvas import Canvas
        raw=io.BytesIO();canvas=Canvas(raw);canvas.drawString(20,700,'Payment: 30 days');canvas.save()
        result=extract(raw.getvalue(),'.pdf')
        self.assertTrue(result['complete']);self.assertEqual(result['blocks'][0]['locator'],'стр. 1')
        self.assertIn('Payment: 30 days',result['blocks'][0]['text'])
        from pypdf import PdfWriter
        empty=io.BytesIO();writer=PdfWriter();writer.add_blank_page(100,100);writer.write(empty)
        result=extract(empty.getvalue(),'.pdf')
        self.assertFalse(result['complete']);self.assertEqual(result['status'],'needs_review_or_ocr')

    def test_encrypted_pdf_is_not_silently_opened(self):
        from pypdf import PdfWriter
        raw=io.BytesIO();writer=PdfWriter();writer.add_blank_page(100,100);writer.encrypt('fixture-password');writer.write(raw)
        result=extract(raw.getvalue(),'.pdf')
        self.assertEqual(result['status'],'encrypted');self.assertFalse(result['complete'])

    def test_entities_active_office_content_and_bad_magic_rejected(self):
        for raw,extension in ((b'not pdf','.pdf'),(docx(TEXT,{'word/vbaProject.bin':b'fixture'}),'.docx'),
                              (b'x'*(8*1024*1024+1),'.txt')):
            with self.assertRaises(ValueError):extract(raw,extension)
        output=io.BytesIO()
        with zipfile.ZipFile(output,'w') as z:z.writestr('word/document.xml','<!DOCTYPE x [<!ENTITY e "BOOM">]><x>&e;</x>')
        with self.assertRaises(ValueError):extract(output.getvalue(),'.docx')

    def test_headers_and_track_changes_are_not_full_read(self):
        result=extract(docx(TEXT,{'word/header1.xml':'<header>fixture</header>'}),'.docx')
        self.assertFalse(result['complete'])

    def test_missing_sandbox_has_no_in_process_fallback(self):
        with patch('shutil.which',return_value=None),self.assertRaises(ValueError):
            extract_isolated(b'fixture','.txt')


class AttachmentTests(unittest.TestCase):
    def read(self,**kwargs):
        return read_attachment(reference(),linked().documents[0],hosts=HOSTS,clock=lambda:NOW,
             fetch=kwargs.get('fetch',lambda *_:Download(URL,'ok',NOW,docx(TEXT))),extract=kwargs.get('extract',extract))

    def test_binary_revision_hash_and_readable_original_are_bound(self):
        result=self.read();self.assertEqual(result.status,'text')
        self.assertEqual(result.document.raw_sha256,hashlib.sha256(docx(TEXT)).hexdigest())
        self.assertEqual(result.document.sha256,result.document.raw_sha256)
        self.assertIn('[абз. 1]',result.document.text)

    def test_same_text_new_original_is_a_distinct_revision(self):
        before=self.read().document
        after=self.read(fetch=lambda *_:Download(URL,'ok',NOW,docx(TEXT,{'docProps/core.xml':'<revision>2</revision>'}))).document
        self.assertEqual(before.text,after.text)
        self.assertNotEqual(before.sha256,after.sha256)

    def test_no_link_foreign_host_or_model_reference_never_fetches(self):
        fetch=Mock()
        for ref,card in ((reference(),candidate().documents[0]),
                         (replace(reference(),url='https://other.example/file.docx'),linked().documents[0])):
            with self.assertRaises(ValueError):read_attachment(ref,card,hosts=HOSTS,fetch=fetch,clock=lambda:NOW)
        fetch.assert_not_called()

    def test_redirect_login_captcha_failure_never_means_no_document(self):
        for status in ('login_required','captcha','unavailable'):
            self.assertEqual(self.read(fetch=lambda *_:Download(URL,status,NOW)).status,status)
        result=self.read(fetch=lambda *_:Download('https://attacker.example/file','ok',NOW,b'private'))
        self.assertEqual(result.status,'not_verified');self.assertIsNone(result.document)

    def test_extractor_error_never_leaks_secret_or_claims_document_absent(self):
        result=self.read(extract=Mock(side_effect=RuntimeError('PRIVATE_TOKEN')))
        self.assertEqual(result.status,'not_verified');self.assertNotIn('PRIVATE_TOKEN',str(result))

    def test_card_advance_and_contract_postpayment_conflict_retained(self):
        result=enrich(linked(),(reference(),),SCOPE,hosts=HOSTS,fetch=lambda *_:Download(URL,'ok',NOW,docx(TEXT)),
                      clock=lambda:NOW,extract=extract)
        row=assess(result.candidate,NOW,HOSTS)
        self.assertIn('payment',row['conflicts']);self.assertEqual(row['bucket'],'unconfirmed')
        self.assertEqual(row['values']['guarantee'],'10% цены договора')
        self.assertEqual(row['values']['design_sro'],'required')
        self.assertTrue(any('абз.' in entry.get('locator','') for entry in row['evidence']['payment']))

    def test_partial_document_visible_but_not_authoritative(self):
        raw=docx(TEXT,{'word/header1.xml':'<header>fixture</header>'})
        result=enrich(linked(),(reference(),),SCOPE,hosts=HOSTS,fetch=lambda *_:Download(URL,'ok',NOW,raw),clock=lambda:NOW,extract=extract)
        row=assess(result.candidate,NOW,HOSTS)
        self.assertNotIn('payment',row['conflicts'])
        self.assertNotIn('guarantee',row['values'])
        self.assertTrue(any(entry.get('complete') is False for entry in row['evidence']['payment']))
        self.assertEqual(row['bucket'],'unconfirmed')

    def test_unreadable_contract_cannot_leave_positive_card_in_priority(self):
        result=enrich(linked(),(reference(),),SCOPE,hosts=HOSTS,
                      fetch=lambda *_:Download(URL,'unavailable',NOW),clock=lambda:NOW,extract=extract)
        row=assess(result.candidate,NOW,HOSTS)
        self.assertEqual(row['bucket'],'unconfirmed')
        self.assertIn('Документ с условиями не удалось проверить',row['risks'])

    def test_dom_link_to_b2b_attachment_conditions_and_report(self):
        from functools import partial
        from .b2b import B2BReader
        from .test_b2b import ReaderTests,URL as CARD_URL,TEXT as CARD_TEXT
        from .runner import run
        from .sources import source_registry
        import tempfile
        read,_=ReaderTests().fixture_reader()
        def observed(url):
            page=read(url)
            if url==CARD_URL:return replace(page,attachment_links=({'url':URL,'name':'Проект договора'},))
            return page
        bound=partial(enrich,scope=SCOPE,hosts=HOSTS,fetch=lambda *_:Download(URL,'ok',NOW,docx(TEXT)),
                      clock=lambda:NOW,extract=extract)
        adapter=B2BReader(read=observed,clock=lambda:NOW,document_enricher=bound)
        with tempfile.TemporaryDirectory() as directory:
            report=run('fixture-attachment-e2e',SCOPE,directory,sources={'b2b':source_registry()['b2b']},
                       adapters={'b2b':adapter},clock=lambda:NOW)
        coverage=report['coverage'][0]
        self.assertEqual(coverage['documents'],1)
        self.assertEqual(coverage['attachments'][0]['status'],'text')
        self.assertIn('document_coverage_incomplete',coverage['limitations'])
        row=report['sections']['unconfirmed'][0]
        self.assertIn('payment',row['conflicts'])


class DirectReviewTests(unittest.TestCase):
    def setUp(self):
        self.item=linked();address=self.item.facts['work_address'][0].value
        text=f'Закупка fixture-1. ООО Пример, ИНН 1234567894. Объект: {address}. Собственник объекта ООО Пример.'
        self.doc=Document('authority','b2b',URL,'Подтверждение стороны и объекта','authority',NOW,text)
        self.item=replace(self.item,documents=(*self.item.documents,self.doc),
                          facts={**self.item.facts,'counterparty':()})
        # Empty fact lists are not a valid candidate; omitted field is unknown.
        self.item=replace(self.item,facts={key:value for key,value in self.item.facts.items() if value})
        def fact(value):return Fact(value,'authority',text,'п. 1')
        self.review=DirectReview(SCOPE.key(),'fixture-specialist',NOW,fact('fixture-1'),fact('ООО Пример'),
            fact('1234567894'),fact(address),fact('owner'),None,(('authority',self.doc.sha256),))

    def test_protected_review_binds_exact_party_object_procedure_and_original(self):
        result=apply_review(self.item,self.review,SCOPE,now=NOW,hosts=HOSTS)
        row=assess(result,NOW,HOSTS)
        self.assertTrue(row['direct_contract_confirmed']);self.assertEqual(row['bucket'],'priority')

    def test_other_company_changed_original_or_object_rejected(self):
        for review in (replace(self.review,scope_key='other'),
                       replace(self.review,document_hashes=(('authority','0'*64),)),
                       replace(self.review,object_address=replace(self.review.object_address,value='OTHER'))):
            with self.assertRaises(ValueError):apply_review(self.item,review,SCOPE,now=NOW,hosts=HOSTS)

    def test_operator_requires_separate_confirmed_authority(self):
        review=replace(self.review,role=replace(self.review.role,value='authorized_operator'))
        with self.assertRaises(ValueError):apply_review(self.item,review,SCOPE,now=NOW,hosts=HOSTS)

    def test_partial_document_cannot_establish_direct_role(self):
        item=replace(self.item,documents=(*self.item.documents[:1],replace(self.doc,complete=False)))
        with self.assertRaises(ValueError):apply_review(item,self.review,SCOPE,now=NOW,hosts=HOSTS)

    def test_inn_checksum_is_not_an_existence_or_ownership_claim(self):
        self.assertTrue(valid_inn('1234567894'))
        self.assertFalse(valid_inn('1234567890'))


if __name__=='__main__':unittest.main()
