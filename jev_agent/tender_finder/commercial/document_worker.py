"""Standalone sandbox child. stdin bytes only; no URLs, secrets or file paths."""
import io
import json
import sys
import zipfile
import xml.etree.ElementTree as ET

MAX_BYTES=8*1024*1024
MAX_TEXT=64000


def extract(data,extension):
    if type(data) is not bytes or not 0<len(data)<=MAX_BYTES:raise ValueError('document_size_limit')
    blocks=[];complete=True
    if extension=='.pdf':
        if not data.startswith(b'%PDF-'):raise ValueError('document_magic_mismatch')
        from pypdf import PdfReader
        reader=PdfReader(io.BytesIO(data),strict=True)
        if reader.is_encrypted:return {'status':'encrypted','blocks':[],'complete':False}
        if not 1<=len(reader.pages)<=30:raise ValueError('document_page_limit')
        for index,page in enumerate(reader.pages,1):
            text=(page.extract_text() or '').strip()
            # Text headers/logos do not prove that scanned contract terms were read.
            if not text or bool(page.images):complete=False
            blocks.append({'locator':f'стр. {index}','text':text})
            if sum(len(row['text']) for row in blocks)>MAX_TEXT:raise ValueError('document_text_limit')
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
