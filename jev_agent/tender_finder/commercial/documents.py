"""Linked public attachments -> isolated text -> source-bound Document.

Fetch/extraction callbacks are protected bindings, never model arguments. No
default network transport, login, arbitrary URL tool, file writes or OCR fallback.
"""
from dataclasses import dataclass
from datetime import datetime
import hashlib
from pathlib import Path
import shutil
import sys
from urllib.parse import urlsplit

from .model import Document, aware, public_url
from ..invoker import _run_bounded

MAX_BYTES=8*1024*1024


def sandbox_command(extension):
    if extension not in ('.pdf','.docx','.txt') or sys.platform!='linux':
        raise ValueError('isolated_document_format_required')
    sandbox=shutil.which('bwrap')
    if not sandbox:raise ValueError('document_sandbox_unavailable')
    worker=Path(__file__).with_name('document_worker.py').resolve(strict=True)
    command=[sandbox,'--unshare-all','--new-session','--die-with-parent','--cap-drop','ALL',
             '--ro-bind','/usr','/usr','--ro-bind','/lib','/lib','--symlink','usr/bin','/bin']
    if Path('/lib64').exists():command+=['--ro-bind','/lib64','/lib64']
    prefix=Path(sys.prefix).resolve()
    if not prefix.is_relative_to('/usr') and not prefix.is_relative_to('/lib'):
        for parent in reversed(prefix.parents):
            if parent!=Path('/'):command+=['--dir',str(parent)]
        command+=['--ro-bind',str(prefix),str(prefix)]
    command+=['--proc','/proc','--dev','/dev','--tmpfs','/tmp','--chdir','/tmp',
              '--ro-bind',str(worker),'/worker.py','--clearenv','--setenv','LANG','C.UTF-8',
              sys.executable,'-I','-B','/worker.py',extension]
    return command


def extract_isolated(data,extension):
    if type(data) is not bytes or not 0<len(data)<=MAX_BYTES:raise ValueError('document_size_limit')
    import json
    raw,code=_run_bounded(sandbox_command(extension),data,10)
    if code!=0 or len(raw)>512*1024:raise ValueError('document_isolated_read_failed')
    result=json.loads(raw)
    if (type(result) is not dict or set(result)!={'status','complete','blocks'}
            or type(result['complete']) is not bool or type(result['blocks']) is not list
            or len(result['blocks'])>2000 or result['status'] not in ('text','needs_review_or_ocr','encrypted')):
        raise ValueError('bounded_document_text_required')
    if result['complete']!=(result['status']=='text'):raise ValueError('document_completeness_conflict')
    for row in result['blocks']:
        if (type(row) is not dict or set(row)!={'locator','text'} or type(row['text']) is not str
                or type(row['locator']) is not str or not 1<=len(row['locator'])<=100):
            raise ValueError('document_text_block_required')
    if sum(len(row['text']) for row in result['blocks'])>64000:raise ValueError('document_text_limit')
    return result


@dataclass(frozen=True)
class Attachment:
    id: str
    source: str
    url: str
    name: str
    kind: str
    extension: str
    # Must be captured from the real primary card's attachment listing by the
    # reviewed reader. A title/URL from a model is not an attachment reference.
    card_id: str
    link_quote: str


@dataclass(frozen=True)
class Download:
    url: str
    status: str
    checked_at: datetime
    content: bytes = b''


@dataclass(frozen=True)
class ReadResult:
    reference: Attachment
    status: str
    document: Document | None = None
    blocks: tuple = ()


def read_attachment(reference,card,*,hosts,fetch,clock,extract=extract_isolated):
    if (type(reference) is not Attachment or type(card) is not Document or card.kind!='card'
            or reference.card_id!=card.id or reference.source!=card.source
            or reference.kind not in ('terms','contract','quote','authority')
            or reference.extension not in ('.pdf','.docx','.txt')
            or not reference.id or reference.id==card.id or not reference.name
            or not public_url(reference.url) or reference.source not in hosts
            or urlsplit(reference.url).hostname not in hosts[reference.source]
            or not reference.link_quote or reference.link_quote not in card.text
            or reference.url not in reference.link_quote or not callable(fetch) or not callable(extract)):
        raise ValueError('reviewed_primary_attachment_reference_required')
    try:
        response=fetch(reference.url,MAX_BYTES)
        now=clock()
        if (type(response) is not Download or response.url!=reference.url or not aware(now)
                or not aware(response.checked_at) or not card.checked_at<=response.checked_at<=now):
            raise ValueError('fresh_exact_attachment_download_required')
        if response.status in ('login_required','captcha','unavailable','robots_disallow','policy_not_verified'):
            return ReadResult(reference,response.status)
        if response.status!='ok' or type(response.content) is not bytes or not 0<len(response.content)<=MAX_BYTES:
            raise ValueError('bounded_attachment_download_required')
        result=extract(response.content,reference.extension)
        text='\n\n'.join('['+row['locator']+']\n'+row['text'] for row in result['blocks'])
        if not text.strip() or not result['blocks']:return ReadResult(reference,result['status'])
        doc=Document(reference.id,reference.source,reference.url,reference.name,reference.kind,response.checked_at,
                     text,raw_sha256=hashlib.sha256(response.content).hexdigest(),complete=result['complete'])
        return ReadResult(reference,result['status'],doc,tuple(result['blocks']))
    except Exception:
        # An inaccessible attachment is not an absent attachment. No raw errors,
        # passwords, credential-bearing redirects or download body in status.
        return ReadResult(reference,'not_verified')
