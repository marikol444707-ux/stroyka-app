import ast
import base64
import io
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from backend.features.model_gateway.contract import ModelInputPart, build_model_request, ModelGatewayError
from backend.features.model_gateway.yandex_adapter import build_yandex_model_adapter
from scripts import invoice_provider_status_patch as operator
from scripts.test_invoice_provider_status_patch import DiagnosticFilesystemTest

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = "def _invoice_scan_ai_content(entry: dict, index: int, total: int) -> list:\n    mime_type = str(entry.get(\"mimeType\") or \"image/jpeg\").lower()\n    label = \"PDF-документ\" if mime_type == \"application/pdf\" else \"Страница документа\"\n    content = [ModelInputPart(kind=\"text\", value=f\"{label} {index} из {total}\")]\n    if mime_type == \"application/pdf\":\n        pdf_bytes = _invoice_scan_pdf_bytes(entry)\n        pdf_text = _extract_invoice_scan_pdf_text(pdf_bytes)\n        rendered_pages = _render_invoice_scan_pdf_pages(pdf_bytes)\n        content.append(ModelInputPart(\n            kind=\"file_data_url\",\n            value=\"data:application/pdf;base64,\" + str(entry.get(\"data\") or \"\"),\n            filename=\"invoice-\" + str(index) + \".pdf\",\n        ))\n        if pdf_text:\n            content.append(ModelInputPart(\n                kind=\"text\",\n                value=(\n                    \"Текст, извлеченный из PDF. Используй его для номера, даты, поставщика, покупателя, \"\n                    \"таблицы товаров, НДС и итогов. Не выдумывай отсутствующие строки.\\n\\n\"\n                    + pdf_text[:24000]\n                ),\n            ))\n        if rendered_pages:\n            content.append(ModelInputPart(\n                kind=\"text\",\n                value=\"Ниже визуальный рендер страниц PDF. Распознай счет также по изображениям.\",\n            ))\n            for page_idx, page_base64 in enumerate(rendered_pages, start=1):\n                content.append(ModelInputPart(kind=\"text\", value=f\"Рендер PDF страницы {page_idx}\"))\n                content.append(ModelInputPart(\n                    kind=\"image_data_url\",\n                    value=\"data:image/png;base64,\" + page_base64,\n                ))\n    else:\n        content.append(ModelInputPart(\n            kind=\"image_data_url\",\n            value=f\"data:{entry['mimeType']};base64,{entry['data']}\",\n        ))\n    return content\n"

class HTTPException(Exception):
    def __init__(self, status_code, detail):
        self.status_code, self.detail = status_code, detail

def content_function(source, pages, text='Synthetic invoice text'):
    tree = ast.parse(source)
    fn = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == '_invoice_scan_ai_content')
    render = Mock(return_value=pages)
    namespace = {'ModelInputPart': ModelInputPart, 'HTTPException': HTTPException,
                 '_invoice_scan_pdf_bytes': lambda entry: b'%PDF synthetic',
                 '_extract_invoice_scan_pdf_text': Mock(return_value=text),
                 '_render_invoice_scan_pdf_pages': render}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), '<invoice-content-test>', 'exec'), namespace)
    return namespace['_invoice_scan_ai_content'], render

class InvoicePdfContentTest(unittest.TestCase):
    def test_pdf_pages_reach_the_model_as_images_without_inline_file_data(self):
        fixed = operator.repair_pdf_source(ORIGINAL)
        content, render = content_function(fixed, ['YWJj', 'ZGVm'])
        parts = content({'mimeType':'application/pdf', 'data':'cHJpdmF0ZS1wZGY='}, 1, 1)
        self.assertEqual([part.value for part in parts if part.kind == 'image_data_url'],
                         ['data:image/png;base64,YWJj', 'data:image/png;base64,ZGVm'])
        self.assertFalse(any(part.kind in ('file_data_url','file_id') for part in parts))
        self.assertTrue(any('Synthetic invoice text' in part.value for part in parts))
        render.assert_called_once_with(b'%PDF synthetic', max_pages=7)
        def create(**values):
            blocks = values['input'][0]['content']
            if any(part['type']=='input_file' for part in blocks):
                raise RuntimeError('Only files with file_id are supported in input')
            self.assertEqual(len([part for part in blocks if part['type']=='input_image']), 2)
            self.assertFalse(any(part['type']=='input_file' for part in blocks))
            return SimpleNamespace(output_text='{"items":[{"quantity":2}]}')
        adapter = build_yandex_model_adapter(api_key='test-key', folder_id='folder-1',
            client_factory=lambda **_: SimpleNamespace(responses=SimpleNamespace(create=create)),
            telemetry_sink=lambda **_:None)
        request = build_model_request(capability='invoice_scan', instructions='Synthetic invoice only',
            input_parts=tuple(parts), temperature=.1, max_output_tokens=12000, deadline_seconds=20)
        old_content, _ = content_function(ORIGINAL, ['YWJj', 'ZGVm'])
        old_parts = old_content({'mimeType':'application/pdf','data':'YWJj'},1,1)
        old_request = build_model_request(capability='invoice_scan', instructions='Synthetic invoice only',
            input_parts=tuple(old_parts), temperature=.1, max_output_tokens=12000, deadline_seconds=20)
        with self.assertRaises(ModelGatewayError):
            adapter.generate(old_request)
        self.assertIn('"quantity":2', adapter.generate(request).output_text)

    def test_missing_renderer_or_failed_conversion_does_not_send_text_only_or_partial_invoice(self):
        content, _ = content_function(operator.repair_pdf_source(ORIGINAL), [])
        with self.assertRaises(HTTPException) as caught:
            content({'mimeType':'application/pdf','data':'YWJj'}, 1, 1)
        self.assertEqual(caught.exception.status_code, 422)
        self.assertIn('фотографии', caught.exception.detail)

    def test_seventh_page_is_detected_and_not_silently_discarded(self):
        content, _ = content_function(operator.repair_pdf_source(ORIGINAL), ['YWJj']*7)
        with self.assertRaises(HTTPException) as caught:
            content({'mimeType':'application/pdf','data':'YWJj'}, 1, 1)
        self.assertEqual(caught.exception.status_code, 422)
        self.assertIn('6 страниц', caught.exception.detail)

    def test_six_pages_are_all_preserved(self):
        content, _ = content_function(operator.repair_pdf_source(ORIGINAL), ['YWJj']*6)
        parts = content({'mimeType':'application/pdf','data':'YWJj'}, 1, 1)
        self.assertEqual(sum(part.kind=='image_data_url' for part in parts), 6)

    def test_plain_photo_uses_the_existing_path_without_pdf_conversion(self):
        content, render = content_function(operator.repair_pdf_source(ORIGINAL), [])
        parts = content({'mimeType':'image/jpeg','data':'YWJj'}, 2, 3)
        self.assertEqual(parts, [ModelInputPart('text','Страница документа 2 из 3'),
                                 ModelInputPart('image_data_url','data:image/jpeg;base64,YWJj')])
        render.assert_not_called()

    def test_production_patch_and_repository_implementation_have_identical_ast(self):
        def shape(source):
            node = next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef)
                        and n.name=='_invoice_scan_ai_content')
            return ast.dump(node, include_attributes=False)
        self.assertEqual(shape(operator.repair_pdf_source(ORIGINAL)), shape((ROOT/'backend/main.py').read_text()))
        with self.assertRaises(operator.Stop):
            operator.repair_pdf_source(operator.repair_pdf_source(ORIGINAL))

    @unittest.skipUnless(shutil.which('pdftoppm'), 'pdftoppm unavailable')
    def test_real_two_page_pdf_renders_as_two_images_and_leaves_no_tempfiles(self):
        from PIL import Image, ImageDraw
        pages = [Image.new('RGB',(320,200),'white') for _ in range(2)]
        for number, page in enumerate(pages,1):
            ImageDraw.Draw(page).text((16,16),f'SYNTHETIC INVOICE PAGE {number}',fill='black')
        stream = io.BytesIO()
        pages[0].save(stream,format='PDF',save_all=True,append_images=pages[1:])
        tree = ast.parse((ROOT/'backend/main.py').read_text())
        names = {'_invoice_scan_pdf_bytes','_extract_invoice_scan_pdf_text',
                 '_invoice_scan_pdftoppm_bin','_render_invoice_scan_pdf_pages','_invoice_scan_ai_content'}
        functions = [node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name in names]
        namespace = dict(base64=base64,io=io,os=os,shutil=shutil,subprocess=subprocess,tempfile=tempfile,
                         HTTPException=HTTPException,ModelInputPart=ModelInputPart)
        exec(compile(ast.Module(body=functions,type_ignores=[]),'<real-pdf-functions>','exec'),namespace)
        with tempfile.TemporaryDirectory() as temporary:
            from unittest.mock import patch
            with patch.object(tempfile,'tempdir',temporary):
                parts = namespace['_invoice_scan_ai_content']({'mimeType':'application/pdf',
                    'data':base64.b64encode(stream.getvalue()).decode()},1,1)
                self.assertEqual(list(Path(temporary).iterdir()),[])
        images = [part for part in parts if part.kind=='image_data_url']
        self.assertEqual(len(images),2)
        self.assertTrue(all(base64.b64decode(part.value.split(',',1)[1]).startswith(b'\x89PNG') for part in images))

class PdfRepairFilesystemTest(DiagnosticFilesystemTest):
    def prepare_main(self):
        target = self.root/operator.MAIN_TARGET
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('unrelated_before = 1\n\n'+ORIGINAL+'\nunrelated_after = 2\n')
        self.git('add','.')
        self.git('-c','user.name=Tests','-c','user.email=tests@example.invalid','commit','-qm','Production main fixture')
        self.head = self.git('rev-parse','HEAD')
        return target

    def test_main_install_preserves_adapter_and_exact_restore_uses_main_target(self):
        target = self.prepare_main()
        adapter = self.target.read_bytes()
        before = target.read_bytes()
        plan, original, _ = operator.pdf_repair_plan(self.root,self.head)
        self.assertEqual(original,before)
        self.assertEqual(self.operations,[])
        result = operator.repair_pdf(self.root,self.head,self.backups,operate=self.operate)
        self.assertEqual(result['state'],'pdf_images_repaired_awaiting_scan')
        self.assertEqual(self.target.read_bytes(),adapter)
        self.assertIn('unrelated_after = 2',target.read_text())
        self.assertEqual(self.git('rev-parse','HEAD'),self.head)
        operator.restore(self.root,Path(result['backup']),operate=self.operate)
        self.assertEqual(target.read_bytes(),before)
        self.assertEqual(self.git('status','--porcelain'),'')

    def test_dirty_main_and_unknown_head_are_refused_before_service_calls(self):
        target = self.prepare_main()
        with self.assertRaisesRegex(operator.Stop,'installed_head_mismatch'):
            operator.repair_pdf(self.root,'00000000',self.backups,operate=self.operate)
        target.write_text(target.read_text()+'\n# independent edit\n')
        with self.assertRaisesRegex(operator.Stop,'main_has_local_changes'):
            operator.repair_pdf(self.root,self.head,self.backups,operate=self.operate)
        self.assertEqual(self.operations,[])
        self.assertEqual(list(self.backups.iterdir()),[])

    def test_failed_main_restart_restores_main_without_touching_adapter(self):
        target = self.prepare_main()
        before, adapter = target.read_bytes(), self.target.read_bytes()
        attempts = []
        def operate(service,action):
            if action=='restart':
                attempts.append(action)
                if len(attempts)==1:
                    raise RuntimeError('fake restart failure')
        with self.assertRaisesRegex(operator.Stop,'original_restored'):
            operator.repair_pdf(self.root,self.head,self.backups,operate=operate)
        self.assertEqual(target.read_bytes(),before)
        self.assertEqual(self.target.read_bytes(),adapter)
        self.assertEqual(len(attempts),2)

if __name__=='__main__':
    unittest.main()
