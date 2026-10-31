"""Standalone sandbox child. stdin bytes only; no URLs, secrets or file paths."""
import io
import json
import sys
import zipfile
import stat
import logging
import xml.etree.ElementTree as ET

MAX_BYTES=8*1024*1024
MAX_TEXT=64000


class PDFWarnings(logging.Handler):
    def __init__(self):
        super().__init__(level=logging.WARNING);self.seen=False
    def emit(self,record):self.seen=True


def extract_pdf(data):
    if not data.startswith(b'%PDF-'):raise ValueError('document_magic_mismatch')
    from pypdf import PdfReader
    warnings=PDFWarnings();logger=logging.getLogger('pypdf');logger.addHandler(warnings)
    blocks=[];complete=True
    try:
        reader=PdfReader(io.BytesIO(data),strict=True)
        if reader.is_encrypted:return {'status':'encrypted','blocks':[],'complete':False}
        if not 1<=len(reader.pages)<=30:raise ValueError('document_page_limit')
        for index,page in enumerate(reader.pages,1):
            text=(page.extract_text() or '').strip()
            if not text or bool(page.images):complete=False
            blocks.append({'locator':f'стр. {index}','text':text})
            if sum(len(row['text']) for row in blocks)>MAX_TEXT:raise ValueError('document_text_limit')
        complete=complete and not warnings.seen
        return {'status':'text' if complete else 'needs_review_or_ocr','blocks':blocks,'complete':complete}
    finally:logger.removeHandler(warnings)


def extract_bundle(data):
    """Flat ZIP documents, bounded in memory; never extract files or recurse ZIPs."""
    if not data.startswith(b'PK'):raise ValueError('document_magic_mismatch')
    blocks=[];complete=True
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        entries=archive.infolist()
        if (not 1<=len(entries)<=32 or len({row.filename.casefold() for row in entries})!=len(entries)
                or sum(row.file_size for row in entries)>16*1024*1024):
            raise ValueError('document_bundle_limit')
        for row in entries:
            path=row.filename
            if (not path or row.orig_filename!=path or path.startswith(('/','\\')) or '\\' in path or ':' in path
                    or any(part in ('..','.','') for part in path.rstrip('/').split('/'))
                    or any(ord(char)<32 or ord(char)==127 for char in path)
                    or stat.S_IFMT(row.external_attr>>16) not in (0,stat.S_IFREG,stat.S_IFDIR) or row.flag_bits&1
                    or row.compress_type not in (0,8) or row.file_size>MAX_BYTES
                    or row.file_size>200*max(1,row.compress_size)):
                raise ValueError('unsafe_document_bundle_entry')
        for index,row in enumerate(entries,1):
            if row.is_dir():continue
            name=row.filename.rsplit('/',1)[-1]
            locator=f'файл {index}: '+name[:45]
            extension='.'+name.rsplit('.',1)[-1].lower() if '.' in name else ''
            if extension not in ('.pdf','.docx','.txt'):
                complete=False
                blocks.append({'locator':locator,'text':'Файл не прочитан: неподдерживаемый формат.'})
                continue
            try:
                result=extract(archive.read(row),extension)
            except Exception:
                complete=False
                blocks.append({'locator':locator,'text':'Файл не прочитан: ошибка формата или ограничения чтения.'})
                continue
            complete=complete and result['complete']
            if not result['blocks']:
                blocks.append({'locator':locator,'text':'Файл не прочитан: зашифрован или не содержит доступного текста.'})
            for block in result['blocks']:
                blocks.append({'locator':locator+'; '+block['locator'],'text':block['text']})
            if len(blocks)>2000 or sum(len(block['text']) for block in blocks)>MAX_TEXT:
                raise ValueError('document_bundle_text_limit')
    if not blocks:complete=False
    return {'status':'text' if complete else 'needs_review_or_ocr','blocks':blocks,'complete':complete}


def extract(data,extension):
    if type(data) is not bytes or not 0<len(data)<=MAX_BYTES:raise ValueError('document_size_limit')
    blocks=[];complete=True
    if extension=='.zip':return extract_bundle(data)
    if extension=='.pdf':
        result=extract_pdf(data);blocks=result['blocks'];complete=result['complete']
        if result['status']=='encrypted':return result
    elif extension=='.docx':
        if not data.startswith(b'PK'):raise ValueError('document_magic_mismatch')
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries=archive.infolist()
            if (len(entries)>2000 or len({row.filename for row in entries})!=len(entries)
                    or sum(row.file_size for row in entries)>16*1024*1024
                    or any(row.flag_bits&1 or row.compress_type not in (0,8) for row in entries)):
                raise ValueError('document_archive_limit')
            names={row.filename for row in entries}
            if any(name.lower().endswith(('.bin','.vba')) for name in names):raise ValueError('active_office_content')
            main=archive.getinfo('word/document.xml')
            if main.file_size>2*1024*1024:raise ValueError('document_xml_limit')
            raw=archive.read(main)
            if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():raise ValueError('document_entity_rejected')
            root=ET.fromstring(raw)
            ns='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
            # Track-change deletions must never become current contract terms.
            if any(node.tag.rsplit('}',1)[-1] in ('drawing','object','pict','altChunk','ins','del')
                   for node in root.iter()) or any(name.startswith(('word/header','word/footer')) for name in names):
                complete=False
            for index,paragraph in enumerate(root.iter(ns+'p'),1):
                text=''.join(node.text or '' for node in paragraph.iter(ns+'t')).strip()
                if text:blocks.append({'locator':f'абз. {index}','text':text})
                if len(blocks)>2000 or sum(len(row['text']) for row in blocks)>MAX_TEXT:
                    raise ValueError('document_text_limit')
    elif extension=='.txt':
        text=data.decode('utf-8-sig')
        if len(text)>MAX_TEXT:raise ValueError('document_text_limit')
        blocks=[{'locator':'текст','text':text}]
    else:raise ValueError('unsupported_document_format')
    if not any(row['text'].strip() for row in blocks):complete=False
    if any(ord(c)<32 and c not in '\r\n\t' for row in blocks for c in row['text']):
        raise ValueError('document_control_characters')
    return {'status':'text' if complete else 'needs_review_or_ocr','blocks':blocks,'complete':complete}


def main():
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_CPU,(6,6))
        resource.setrlimit(resource.RLIMIT_AS,(512*1024*1024,)*2)
        resource.setrlimit(resource.RLIMIT_FSIZE,(1024*1024,)*2)
        resource.setrlimit(resource.RLIMIT_NOFILE,(32,32))
        if len(sys.argv)!=2:raise ValueError('explicit_document_format_required')
        result=extract(sys.stdin.buffer.read(MAX_BYTES+1),sys.argv[1])
        raw=json.dumps(result,ensure_ascii=False).encode()
        if len(raw)>512*1024:raise ValueError('document_output_limit')
        sys.stdout.buffer.write(raw)
        return 0
    except Exception:
        sys.stdout.write('{"status":"unreadable","complete":false,"blocks":[]}')
        return 2


if __name__=='__main__':raise SystemExit(main())
