"""Public, first-page STEP discovery and freshly read primary cards.

Reviewed 2026-11-01: ahstep.ru/procurement -> /tender -> /tenders/tender<digits>.
GET only, inherited proxy/CA, no login, browser, JS, redirects or downloads.
An active listing filter does not confirm a card's current stage. ZIP documents
and malformed download links remain unread; counterparty/role/payment unknown.
"""
from datetime import datetime
from html.parser import HTMLParser
import hashlib
import re
from urllib.parse import urljoin
from urllib.request import Request, build_opener
from urllib.error import HTTPError

from .access import Decision, NoRedirect, USER_AGENT
from .b2b import Observation, extract_fields
from .model import Candidate, Fact
from .platforms import PortalSpec
from .sources import Source

SOURCE = Source('step', 'Степь', 'agriculture', ('ahstep.ru',))
LISTING = 'https://ahstep.ru/tender?status=1'
CARD_PATH = r'/tenders/tender[0-9]{10,20}'
MAX_HTML = 1024 * 1024


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
        return Observation(url, 'ok', clock(), text, state, raw_sha256=hashlib.sha256(body).hexdigest())
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


def adapter(*, clock, access_check, fetch=fetch_html):
    def collect(profile, started):
        from .portal_reader import collect_portal
        profile.validate()
        return collect_portal(spec(started), read=lambda url: read(url, clock=clock,
            access_check=access_check, fetch=fetch), clock=clock, extract_card=parse_card)
    return collect
