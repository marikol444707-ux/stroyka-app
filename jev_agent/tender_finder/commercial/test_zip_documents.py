"""Synthetic bundles and scoped STEP flow; live originals are not unit fixtures."""
from dataclasses import replace
import hashlib
import io
import stat
import zipfile
from unittest import TestCase
from unittest.mock import Mock,patch

from .access import Decision
from .document_worker import extract
from .documents import Attachment, Download,read_attachment
from .model import Profile
from .owner_step import document_url, adapter, SOURCE, LISTING
from .policy import assess
from .terms import enrich
from .test_commercial import NOW, SCOPE, candidate
from .test_documents import docx, TEXT
from .test_owner_step import CARD, BODY, LIST


def bundle(entries, compression=zipfile.ZIP_DEFLATED):
    output=io.BytesIO()
    with zipfile.ZipFile(output,'w',compression) as archive:
        for name,data in entries:archive.writestr(name,data)
    return output.getvalue()


class BundleTests(TestCase):
    def test_supported_files_keep_distinct_file_and_paragraph_locations(self):
        data=bundle([('contract.docx',docx(TEXT)),('readme.txt',b'Other public text')])
        result=extract(data,'.zip')
        self.assertTrue(result['complete'])
        self.assertIn('contract.docx; абз. 1',result['blocks'][0]['locator'])
        self.assertIn('readme.txt',result['blocks'][-1]['locator'])

    def test_unknown_formats_and_nested_archives_are_visible_and_incomplete(self):
        for extension in ('.doc','.xls','.xlsx','.zip','.exe'):
            with self.subTest(extension=extension):
                result=extract(bundle([('terms.txt','Условия оплаты: Аванс 30%'.encode()),('extra'+extension,b'not read')]),'.zip')
                self.assertFalse(result['complete'])
                self.assertIn('неподдерживаемый формат',result['blocks'][-1]['text'])

    def test_unreadable_supported_child_does_not_disappear(self):
        result=extract(bundle([('broken.pdf',b'not PDF')]),'.zip')
        self.assertFalse(result['complete'])
        self.assertIn('Файл не прочитан',result['blocks'][0]['text'])

    def test_paths_symlinks_duplicates_and_unsupported_compression_rejected(self):
        for name in ('../escape.txt','/etc/passwd','C:/escape.txt','dir\\escape.txt','a/../b.txt','a/./b.txt','bad\nname.txt'):
            with self.subTest(name=name),self.assertRaises(ValueError):extract(bundle([(name,b'x')]),'.zip')
        info=zipfile.ZipInfo('link.txt');info.create_system=3;info.external_attr=(stat.S_IFLNK|0o777)<<16
        with self.assertRaises(ValueError):extract(bundle([(info,b'/etc/passwd')]),'.zip')
        with self.assertRaises(ValueError):extract(bundle([('a.txt',b'a'),('A.txt',b'b')]),'.zip')
        with self.assertRaises(ValueError):extract(bundle([('a.txt',b'a')],zipfile.ZIP_BZIP2),'.zip')
        raw=bundle([('file.txtX',b'fixture')]).replace(b'file.txtX',b'file.txt\x00')
        with self.assertRaises(ValueError):extract(raw,'.zip')

    def test_entry_limit_bomb_and_encrypted_flags_rejected(self):
        for data in (bundle([(f'{i}.txt',b'x') for i in range(33)]),bundle([('bomb.txt',b'x'*1024*1024)])):
            with self.assertRaises(ValueError):extract(data,'.zip')
        data=bytearray(bundle([('a.txt',b'fixture')]))
        data[6]|=1;central=data.index(b'PK\x01\x02');data[central+8]|=1
        with self.assertRaises(ValueError):extract(bytes(data),'.zip')

    def test_empty_directory_is_not_successful_text(self):
        result=extract(bundle([('folder/',b'')]),'.zip')
        self.assertFalse(result['complete']);self.assertEqual(result['blocks'],[])

    def test_pdf_font_or_structure_warning_prevents_full_read_claim(self):
        import logging
        page=Mock(images=[])
        def text():
            logging.getLogger('pypdf').warning('Synthetic unsupported font encoding')
            return 'Условия оплаты: Аванс 90%'
        page.extract_text.side_effect=text
        with patch('pypdf.PdfReader',return_value=Mock(is_encrypted=False,pages=[page])):
            result=extract(b'%PDF-fixture','.pdf')
        self.assertFalse(result['complete'])


class ProofTests(TestCase):
    def test_whole_bundle_cannot_be_promoted_to_contract_or_authority(self):
        item=candidate();url='https://www.b2b-center.ru/documents/fixture.zip'
        card=replace(item.documents[0],text=item.documents[0].text+'\nArchive: '+url)
        fetch=Mock()
        for kind in ('contract','authority'):
            ref=Attachment('package','b2b',url,'Проект договора',kind,'.zip',card.id,'Archive: '+url)
            with self.assertRaises(ValueError):read_attachment(ref,card,hosts={'b2b':('www.b2b-center.ru',)},
                fetch=fetch,clock=lambda:NOW,extract=extract)
        fetch.assert_not_called()

    def enrich(self, payload):
        url='https://www.b2b-center.ru/documents/fixture.zip'
        item=candidate();card=replace(item.documents[0],text=item.documents[0].text+'\nArchive: '+url)
        item=replace(item,documents=(card,))
        ref=Attachment('package','b2b',url,'Документы закупки','terms','.zip',card.id,'Archive: '+url)
        return enrich(item,(ref,),SCOPE,hosts={'b2b':('www.b2b-center.ru',)},
            fetch=lambda *_:Download(url,'ok',NOW,payload),clock=lambda:NOW,extract=extract)

    def test_archive_hash_and_member_location_survive_to_business_evidence(self):
        raw=bundle([('terms.docx',docx(TEXT))]);result=self.enrich(raw)
        archive=result.candidate.documents[-1]
        self.assertEqual(archive.sha256,hashlib.sha256(raw).hexdigest())
        self.assertTrue(archive.complete)
        self.assertTrue(any('terms.docx; абз.' in fact.locator for fact in result.candidate.facts['payment_period']))

    def test_incomplete_archive_cannot_override_confirmed_primary_payment(self):
        result=self.enrich(bundle([('terms.txt','Условия оплаты: Аванс 90%'.encode()),('unread.doc',b'unknown')]))
        report=assess(result.candidate,NOW,{'b2b':('www.b2b-center.ru',)})
        self.assertIn('Неполный текст документа: требуется проверка или OCR',report['risks'])
        self.assertNotEqual(report['values'].get('advance_conditions'),'Аванс 90%')
        self.assertEqual(report['bucket'],'unconfirmed')

    def test_opposing_terms_in_two_files_are_retained_as_conflicting_evidence(self):
        result=self.enrich(bundle([('a.txt','Условия оплаты: Постоплата 30 дней'.encode()),
                                   ('b.txt','Условия оплаты: Аванс 50%'.encode())]))
        report=assess(result.candidate,NOW,{'b2b':('www.b2b-center.ru',)})
        self.assertIn('payment_period',report['conflicts'])
        locations=[row['locator'] for row in report['evidence']['payment_period']]
        self.assertTrue(any('a.txt' in value for value in locations))
        self.assertTrue(any('b.txt' in value for value in locations))


class StepZipTests(TestCase):
    def test_normalization_is_exact_and_bound_to_the_published_procedure(self):
        raw='https://www.ahstep.ru/storage/tenders\\tender63928705612762.zip'
        self.assertEqual(document_url(raw,CARD),raw.replace('\\','/'))
        for value in (raw.replace('63928705612762','63928705612763'),raw.replace('www.ahstep.ru','attacker.example'),
                      raw+'?token=fake',raw.replace('tenders\\','tenders/../'),raw.replace('https:','http:')):
            with self.assertRaises(ValueError):document_url(value,CARD)

    def run_reader(self, *, scope=SCOPE, archive_fetch=None, permission=None, monotonic=None):
        options={} if monotonic is None else {'monotonic':monotonic}
        return adapter(clock=lambda:NOW,access_check=permission or (lambda _:Decision(True,'allowed')),
            scope=scope,fetch=lambda url:(200,'text/html',LIST if url==LISTING else BODY),
            archive_fetch=archive_fetch or (lambda *_:(200,bundle([('terms.docx',docx(TEXT))]))),
            extract_document=extract,**options)(Profile(),NOW)

    def test_scoped_reader_downloads_only_observed_archive_and_enriches_terms(self):
        fetch=Mock(return_value=(200,bundle([('terms.docx',docx(TEXT))])))
        result=self.run_reader(archive_fetch=fetch)
        self.assertEqual(fetch.call_count,1)
        self.assertEqual(fetch.call_args.args[0],'https://www.ahstep.ru/storage/tenders/tender63928705612762.zip')
        self.assertEqual(result.attachment_statuses[0]['status'],'text')
        self.assertEqual(len(result.candidates[0].documents),2)

    def test_absent_scope_or_denied_archive_policy_never_downloads(self):
        fetch=Mock();self.run_reader(scope=None,archive_fetch=fetch);fetch.assert_not_called()
        permission=lambda url:Decision(False,'robots_disallow') if '/storage/' in url else Decision(True,'allowed')
        result=self.run_reader(permission=permission,archive_fetch=fetch)
        fetch.assert_not_called();self.assertEqual(result.attachment_statuses[0]['status'],'robots_disallow')

    def test_expired_lease_and_redirect_leave_document_unverified(self):
        ticks=iter((0,46));fetch=Mock()
        result=self.run_reader(archive_fetch=fetch,monotonic=lambda:next(ticks))
        fetch.assert_not_called();self.assertEqual(result.attachment_statuses[0]['status'],'not_verified')
        result=self.run_reader(archive_fetch=lambda *_:(302,b''))
        self.assertEqual(result.attachment_statuses[0]['status'],'unavailable')

