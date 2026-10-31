"""Public, first-page STEP discovery and freshly read primary cards.

Reviewed 2026-11-01: ahstep.ru/procurement -> /tender -> /tenders/tender<digits>.
GET only, inherited proxy/CA, no login, browser, JS or redirects. ZIP reading is
opt-in via protected scope and isolated extraction; incomplete bundles remain
unconfirmed. An active listing filter does not confirm a card's current stage.
"""
from datetime import datetime
from html.parser import HTMLParser
import hashlib
import re
import time
from functools import partial
from urllib.parse import urljoin
from urllib.request import Request, build_opener
from urllib.error import HTTPError

from .access import Decision, NoRedirect, USER_AGENT
from .b2b import Observation, extract_fields
from .model import Candidate, Fact
from .documents import Download, extract_isolated, MAX_BYTES
from ..state import Scope
from .platforms import PortalSpec
from .sources import Source

SOURCE = Source('step', 'Степь', 'agriculture', ('ahstep.ru','www.ahstep.ru'))
LISTING = 'https://ahstep.ru/tender?status=1'
CARD_PATH = r'/tenders/tender[0-9]{10,20}'
MAX_HTML = 1024 * 1024


def document_url(raw, card):
    """Canonicalize only the observed same-procedure STEP download path."""
    identifier=card.rsplit('/',1)[-1]
    if (type(raw) is not str or len(raw)>2048 or not re.fullmatch('tender[0-9]{10,20}',identifier)):
        raise ValueError('published_step_archive_required')
    match=re.fullmatch(r'https://www\.ahstep\.ru/storage/tenders[\\/]{1,2}(tender[0-9]{10,20})\.zip',raw)
    if not match or match[1]!=identifier:raise ValueError('same_procedure_archive_required')
    return 'https://www.ahstep.ru/storage/tenders/'+identifier+'.zip'


def fetch_archive(url, maximum):
    if type(maximum) is not int or not 0<maximum<=MAX_BYTES:raise ValueError('archive_size_limit')
    req=Request(url,headers={'User-Agent':USER_AGENT,'Accept':'application/zip'})
    try:response=build_opener(NoRedirect).open(req,timeout=15)
    except HTTPError as error:response=error
    with response:
        return response.code,response.read(maximum+1)


class MainText(HTMLParser):
    """Visible main content + the page h1; scripts/header/footer are not facts."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.main = self.heading = self.skip = 0
        self.parts = []; self.links = []; self.anchor = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'main': self.main += 1
        if tag == 'h1': self.heading += 1
        if tag in ('script', 'style', 'nav', 'footer'): self.skip += 1
        if self.main and not self.skip and tag == 'a' and attrs.get('href'):
            self.anchor = [attrs['href'], []]

    def handle_endtag(self, tag):
        if tag == 'a' and self.anchor:
            href, parts = self.anchor
            self.links.append((href, ' '.join(parts))); self.anchor = None
        if tag == 'main': self.main = max(0, self.main - 1)
        if tag == 'h1': self.heading = max(0, self.heading - 1)
        if tag in ('script', 'style', 'nav', 'footer'): self.skip = max(0, self.skip - 1)

    def handle_data(self, data):
        value = ' '.join(data.split())
        if value and (self.main or self.heading) and not self.skip:
            self.parts.append(value)
            if self.anchor: self.anchor[1].append(value)


def fetch_html(url):
    req = Request(url, headers={'User-Agent': USER_AGENT, 'Accept': 'text/html'})
    try: response = build_opener(NoRedirect).open(req, timeout=12)
    except HTTPError as error: response = error
    with response:
        return response.code, response.headers.get('Content-Type', ''), response.read(MAX_HTML + 1)


def spec(now):
    return PortalSpec(SOURCE, (LISTING,), (None,), notice_pattern=CARD_PATH, planned_at=now)


def read(url, *, clock, access_check, fetch=fetch_html):
    plan = spec(clock()); kind = plan.approve(url)
    permission = access_check(url)
    if type(permission) is not Decision: raise ValueError('typed_owner_access_required')
    if not permission.allowed: return Observation(url, permission.status, clock())
    try:
        code, mime, body = fetch(url)
        if code == 401: return Observation(url, 'login_required', clock())
        if (code != 200 or not isinstance(mime, str) or mime.split(';')[0].strip().lower() != 'text/html'
                or type(body) is not bytes or not 0 < len(body) <= MAX_HTML):
            return Observation(url, 'unavailable', clock())
        parser = MainText(); parser.feed(body.decode('utf-8-sig'))
        text = '\n'.join(parser.parts)
        if not text or len(text.encode()) > 480 * 1024:
            return Observation(url, 'unavailable', clock())
        state = None
        if kind == 'listing':
            if not all(label in text for label in ('Закупочные процедуры', '№ закупочной процедуры', 'Текущий статус')):
                return Observation(url, 'unavailable', clock())
            links = []
            for href, _label in parser.links:
                target = urljoin(url, href)
                try:
                    if plan.approve(target) == 'card' and target not in links: links.append(target)
                except (ValueError, TypeError): pass
            # A populated page whose DOM changes is not an empty success.
            if not links: return Observation(url, 'unavailable', clock())
            state = {'url': url, 'notice_urls': links[:40]}
        elif 'УВЕДОМЛЕНИЕ' not in text or 'О ПРОВЕДЕНИИ ЗАКУПОЧНОЙ ПРОЦЕДУРЫ' not in text:
            return Observation(url, 'unavailable', clock())
        attachments=[]
        if kind=='card':
            for raw,name in parser.links:
                if not re.search('закупочн.*документац',name,re.I):continue
                try:target=document_url(raw,url)
                except ValueError:continue
                if any(item['url']==target for item in attachments):continue
                name=name[:200]
                attachments.append({'url':target,'name':name,'section':'procurement_documents'})
                text+='\nИсходная ссылка архива: '+raw+'\nНормализованный URL: '+target
        return Observation(url, 'ok', clock(), text, state, tuple(attachments),raw_sha256=hashlib.sha256(body).hexdigest())
    except Exception:
        return Observation(url, 'unavailable', clock())


def parse_card(document, source):
    if source != SOURCE.id or document.source != source: raise ValueError('step_card_source_required')
    numbers = set(re.findall(r'Закупочная процедура\s*№\s*([0-9]{1,12})(?![0-9])', document.text))
    if len(numbers) != 1: raise ValueError('independent_step_procedure_number_required')
    facts = extract_fields(document)
    subject = re.search(r'объявляет о проведении открытого запроса предложений на:\s*(.{1,4000}?)\s*'
                        r'и приглашает юридических лиц', document.text, re.S | re.I)
    if subject:
        value = subject[1].strip().strip('«»')
        facts['title'] = (Fact(value, document.id, subject[0], 'Уведомление, пункт 1'),)
        facts['work_scope'] = (Fact(value, document.id, subject[0], 'Уведомление, пункт 1'),)
    deadline = re.search(r'не позднее\s+(\d{1,2}:\d{2})\s+часов\s*\(московское время\)\s*'
                         r'(\d{2}\.\d{2}\.\d{4})\s*г', document.text, re.I)
    if deadline:
        from zoneinfo import ZoneInfo
        try:
            value = datetime.strptime(deadline[2]+' '+deadline[1], '%d.%m.%Y %H:%M').replace(
                tzinfo=ZoneInfo('Europe/Moscow')).isoformat()
            facts['deadline'] = (Fact(value, document.id, deadline[0], 'Уведомление, пункт 4'),)
        except ValueError: pass
    return Candidate(source, next(iter(numbers)), (document,), facts)


def adapter(*, clock, access_check, fetch=fetch_html,scope=None,extract_document=extract_isolated,
            archive_fetch=fetch_archive,monotonic=time.monotonic):
    if scope is not None:
        if type(scope) is not Scope:raise ValueError('protected_step_document_scope_required')
        scope.key()
    def collect(profile, started):
        from .portal_reader import collect_portal
        from .terms import enrich
        profile.validate()
        leases={}
        def page(url):
            leases.clear()
            observed=read(url,clock=clock,access_check=access_check,fetch=fetch)
            for row in observed.attachment_links:leases[row['url']]={'deadline':monotonic()+45,'result':None}
            return observed
        def download(url,maximum):
            lease=leases.get(url)
            if lease is None or monotonic()>lease['deadline']:raise ValueError('fresh_observed_step_archive_required')
            decision=access_check(url)
            if type(decision) is not Decision:raise ValueError('typed_archive_access_required')
            if not decision.allowed:return Download(url,decision.status,clock())
            if lease['result'] is not None:return lease['result']
            result=Download(url,'unavailable',clock())
            try:
                code,body=archive_fetch(url,maximum)
                if code==200 and type(body) is bytes and 0<len(body)<=maximum and body.startswith(b'PK'):
                    result=Download(url,'ok',clock(),body)
                elif code==401:result=Download(url,'login_required',clock())
            except Exception:pass
            lease['result']=result
            return result
        bound=partial(enrich,scope=scope,hosts={'step':SOURCE.hosts},fetch=download,clock=clock,
                      extract=extract_document) if scope is not None else None
        return collect_portal(spec(started),read=page,clock=clock,extract_card=parse_card,document_enricher=bound)
    return collect
