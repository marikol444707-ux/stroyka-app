"""Read one EIS page using the existing jev_eis_documents.Browser.page method.

No new browser, document downloader, model, service or generic fetch API. The
protected runtime owns the reviewed, isolated Browser lifecycle and credentials-
free sandbox. Importing this module never opens a page. Source text is untrusted
data; observing it does not verify procurement fields or company eligibility.
"""
import asyncio
import hashlib
import re
from urllib.parse import parse_qs, urlsplit

from .reporting import aware

MAX_TEXT_BYTES = 96 * 1024
MAX_HTML_BYTES = 1024 * 1024


def notice_identity(url):
    """The same narrow 44-FZ URL surface accepted by the reviewed reader."""
    if not isinstance(url,str) or len(url)>2048 or any(ord(char)<33 for char in url):
        raise ValueError('unsupported_notice_url')
    parsed=urlsplit(url)
    try:params=parse_qs(parsed.query,keep_blank_values=True,strict_parsing=True)
    except ValueError:raise ValueError('unsupported_notice_url') from None
    values=params.get('regNumber',[])
    if (parsed.scheme!='https' or parsed.netloc!='zakupki.gov.ru' or parsed.fragment
            or not re.fullmatch(r'/epz/order/notice/(?:zk20|ok20|ea20)/view/common-info\.html',parsed.path)
            or set(params)!={'regNumber'} or len(values)!=1 or not re.fullmatch('[0-9]{19}',values[0])):
        raise ValueError('unsupported_notice_url')
    return values[0],parsed.path


async def read_notice_page(url, *, browser, clock, timeout_seconds=40):
    """browser is an already opened reviewed Browser, bound by server code.

    Never call Browser.documents_page/download, eis-review, collect or model.
    No automatic retry or result cache. The job layer must control idempotency.
    """
    number,path=notice_identity(url)
    if type(timeout_seconds) is not int or not 1<=timeout_seconds<=60 or not callable(clock):
        raise ValueError('bounded_reader_context_required')
    try:
        page=await asyncio.wait_for(browser.page(url,number),timeout=timeout_seconds)
        if type(page) is not dict or page.get('ready')!='complete':
            raise ValueError('page_not_ready')
        if notice_identity(page.get('url'))!=(number,path):
            raise ValueError('page_identity_conflict')
        text=page.get('text');html=page.get('html')
        if not isinstance(text,str) or not isinstance(html,str):
            raise ValueError('invalid_page_text')
        text_bytes=text.encode('utf-8');html_bytes=html.encode('utf-8')
        if len(text_bytes)>MAX_TEXT_BYTES or len(html_bytes)>MAX_HTML_BYTES:
            return {'ok':False,'status':'page_size_limit','notice_number':number}
        if not re.search(r'(?<![0-9])'+re.escape(number)+r'(?![0-9])',text):
            raise ValueError('notice_not_observed')
        checked_at=clock()
        if not aware(checked_at):raise ValueError('aware_clock_required')
    except asyncio.TimeoutError:
        return {'ok':False,'status':'page_timeout','notice_number':number}
    except Exception:
        return {'ok':False,'status':'page_not_verified','notice_number':number}
    return {'ok':True,'status':'page_observed','notice_number':number,'url':page['url'],
            'checked_at':checked_at.isoformat(),'text':text,
            'text_sha256':hashlib.sha256(text_bytes).hexdigest(),
            'html_sha256':hashlib.sha256(html_bytes).hexdigest(),
            'untrusted_source_text':True,'card_fields_verified':False,
            'attachments_requested':False,'model_calls':0}
