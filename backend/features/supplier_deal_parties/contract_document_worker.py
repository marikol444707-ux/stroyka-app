"""Private document worker, fixed executables, private temp directory, bounded output."""
import io
import csv
import re
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile
import xml.etree.ElementTree as ET

class Invalid(Exception):pass
class Limit(Exception):pass
class Missing(Exception):pass
class Encrypted(Exception):pass

def run(name,args):
    executable=shutil.which(name)
    if not executable:raise Missing()
    return subprocess.run([executable,*map(str,args)],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,check=True,timeout=90).stdout

BEST_MODELS = Path('/usr/local/share/stroyka-tessdata-best')

def ocr_args(precise=False, language='rus+eng'):
    args = ['-l', language]
    if precise and all((BEST_MODELS / (lang + '.traineddata')).is_file() for lang in ('rus', 'eng')):
        args += ['--tessdata-dir', BEST_MODELS]
    return args

def column_boundary(tsv, width, height):
    """Only two unambiguous, aligned role headers justify splitting a page."""
    rows = list(csv.DictReader(io.StringIO(tsv), delimiter='\t'))
    headers = [r for r in rows if r.get('text', '').strip().rstrip(':') in ('ПОСТАВЩИК', 'ПОКУПАТЕЛЬ')
               and float(r.get('conf', '-1')) >= 80]
    if len(headers) != 2 or len({r['text'].strip().rstrip(':') for r in headers}) != 2:
        return None
    left, right = sorted(headers, key=lambda r: int(r['left']))
    x1, x2 = int(left['left']), int(right['left'])
    y1, y2 = int(left['top']), int(right['top'])
    if x2 - x1 < width * .2 or abs(y1-y2) > height * .015:
        return None
    split = round((x1 + int(left['width'])/2 + x2 + int(right['width'])/2)/2)
    if not width * .35 < split < width * .65:
        return None
    return split, max(0, min(y1, y2)-8)

def column_text(path):
    """Read each column independently; email lines get a Latin-only OCR pass."""
    base = path.with_suffix('.detail')
    run('tesseract', [path, base, *ocr_args(True), '-c', 'tessedit_create_txt=1', '-c', 'tessedit_create_tsv=1'])
    txt, tsv = Path(str(base)+'.txt'), Path(str(base)+'.tsv')
    crop = path.with_name('email-line.png')
    try:
        text = txt.read_text().replace('\x0c', '\n').strip()
        rows = list(csv.DictReader(io.StringIO(tsv.read_text()), delimiter='\t'))
        keys = {(r['block_num'], r['par_num'], r['line_num']) for r in rows
                if re.fullmatch(r'[ecе]-?mail:?', r.get('text', ''), re.I)}
        text_lines = [line for line in text.splitlines() if re.match(r'^[ecе]-?mail\s*:', line, re.I)]
        if len(keys) == 1 and len(text_lines) == 1:
            key = next(iter(keys))
            words = [r for r in rows if r.get('level') == '5' and (r['block_num'], r['par_num'], r['line_num']) == key
                     and re.fullmatch(r'[ecе]-?mail:?', r.get('text', ''), re.I)]
            top = min(int(r['top']) for r in words)
            bottom = max(int(r['top']) + int(r['height']) for r in words)
            from PIL import Image
            with Image.open(path) as page:
                page.crop((0, max(0, top-10), page.width, min(page.height, bottom+10))).save(crop)
            email = run('tesseract', [crop, 'stdout', *ocr_args(True, 'eng'), '--psm', '7']).decode('utf-8').strip()
            if re.fullmatch(r'[ecе]-?mail\s*:\s*[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}', email, re.I):
                text = text.replace(text_lines[0], email, 1)
        return text
    finally:
        txt.unlink(missing_ok=True)
        tsv.unlink(missing_ok=True)
        crop.unlink(missing_ok=True)

def ocr(path, precise=False):
    base = path.with_suffix('.ocr')
    run('tesseract', [path, base, *ocr_args(precise), '-c', 'tessedit_create_txt=1', '-c', 'tessedit_create_tsv=1'])
    text_path, tsv_path = Path(str(base)+'.txt'), Path(str(base)+'.tsv')
    try:
        text = text_path.read_text().replace('\x0c', '\n').strip()
        if not text:
            raise Invalid()
        if precise and re.search(r'ДОГОВОР', text[:300]):
            # Russian preambles: mixed-language OCR confuses Cyrillic initials
            # with Latin letters, which prevents binding the named signatory.
            text = run('tesseract', [path, 'stdout', *ocr_args(True, 'rus')]).decode('utf-8').replace('\x0c', '\n').strip()
        if not re.search(r'реквизит\w*.*сторон', text, re.I):
            return text
        from PIL import Image
        with Image.open(path) as page:
            boundary = column_boundary(tsv_path.read_text(), *page.size)
            if not boundary:
                return text
            split, top = boundary
            # Keep the prose above the columns; replace only the requisites.
            heading = list(re.finditer(r'^.*реквизит\w*.*сторон.*$', text, re.I | re.M))[-1]
            pieces = [text[:heading.end()]]
            for n, box in enumerate(((0, top, split, page.height), (split, top, page.width, page.height))):
                crop = path.with_name('column-' + str(n) + '.png')
                try:
                    page.crop(box).save(crop)
                    piece = column_text(crop)
                    if not piece:
                        return text
                    pieces.append(piece)
                finally:
                    crop.unlink(missing_ok=True)
            return '\n\n'.join(pieces)
    finally:
        text_path.unlink(missing_ok=True)
        tsv_path.unlink(missing_ok=True)

def pdf(data,folder):
    from pypdf import PdfReader
    reader=PdfReader(io.BytesIO(data),strict=False)
    if reader.is_encrypted:raise Encrypted()
    if not 0<len(reader.pages)<=30:raise Limit()
    source=folder/'input.pdf';source.write_bytes(data);texts=[]
    for index,page in enumerate(reader.pages,1):
        text=(page.extract_text() or '').strip()
        # Image-bearing pages are rendered too: a text header does not prove
        # that requisites in the scanned body have been read.
        has_image=bool(page.images)
        if not text or has_image:
            prefix=folder/'render'
            run('pdftoppm',['-f',index,'-l',index,'-singlefile','-scale-to',3200,'-png',source,prefix])
            text=ocr(folder/'render.png',precise=index==1);(folder/'render.png').unlink()
        texts.append(text)
        if sum(map(len,texts))+2*len(texts)>64000:raise Limit()
    return '\n\n'.join(texts)

def office(data,suffix,folder):
    if suffix=='.docx':
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            if len(z.infolist())>2000 or sum(i.file_size for i in z.infolist())>32*1024*1024:raise Limit()
            raw=z.read('word/document.xml')
            if b'<!DOCTYPE' in raw or b'<!ENTITY' in raw:raise Invalid()
            tree=ET.fromstring(raw);ns='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
            # Text-only main document can be read without a converter. Images,
            # headers/footers and objects require rendering the complete document.
            complex_doc=any(e.tag.rsplit('}',1)[-1] in ('drawing','object','pict','altChunk') for e in tree.iter()) or any(n.startswith(('word/header','word/footer')) for n in z.namelist())
            if not complex_doc:
                return '\n'.join(''.join(p.itertext()) for p in tree.iter(ns+'p')).strip()
    source=folder/('source'+suffix);source.write_bytes(data)
    run('libreoffice',['-env:UserInstallation='+ (folder/'profile').as_uri(),'--headless','--convert-to','pdf','--outdir',folder,source])
    return pdf((folder/'source.pdf').read_bytes(),folder)

def main():
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_CPU,(90,90));resource.setrlimit(resource.RLIMIT_FSIZE,(64*1024*1024,)*2)
        if sys.platform=='linux':resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,)*2)
        data=sys.stdin.buffer.read(10*1024*1024+1)
        if len(data)>10*1024*1024:raise Limit()
        suffix=sys.argv[1]
        magic={'.pdf':b'%PDF-','.doc':b'\xd0\xcf\x11\xe0','.docx':b'PK','.png':b'\x89PNG\r\n\x1a\n','.jpg':b'\xff\xd8','.jpeg':b'\xff\xd8'}
        if suffix not in magic or not data.startswith(magic[suffix]):raise Invalid()
        folder=Path(sys.argv[2])
        if suffix=='.pdf':text=pdf(data,folder)
        elif suffix in ('.doc','.docx'):text=office(data,suffix,folder)
        else:
            path=folder/('image'+suffix);path.write_bytes(data);text=ocr(path)
        if len(text)>64000:raise Limit()
        if not text.strip():raise Invalid()
        sys.stdout.buffer.write(text.encode('utf-8'))
        return 0
    except Encrypted:return 6
    except (Limit,MemoryError):return 4
    except (Missing,ImportError):return 3
    except Exception:
        if os.getenv('STROYKA_DOCUMENT_WORKER_DEBUG') == '1':
            import traceback
            traceback.print_exc()
        return 2
if __name__=='__main__':sys.exit(main())
