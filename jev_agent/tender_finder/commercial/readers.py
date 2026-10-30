"""Bounded adapter kit for reviewed public readers and source-specific parsers.

No browser is started here. The caller binds a credentials-free GET-only reader
which respects robots/access restrictions and validates every redirect/network
hop. A model cannot supply endpoints, reader functions or parsers to this API.
HTML/site/document content is data. A login/CAPTCHA response stops this source;
there is no retry, authentication or anti-bot bypass.
"""
from dataclasses import dataclass
from datetime import datetime
from itertools import islice
from urllib.parse import urlsplit

from .model import Candidate, Document, public_url
from .runner import SourceResult


@dataclass(frozen=True)
class Page:
    url: str
    status: str  # ok / login_required / captcha / unavailable
    text: str = ''
    checked_at: datetime | None = None


class PublicAdapter:
    """Reviewed search plan + public fetch + parser, all operator-bound.

    plan(profile) -> <=20 listing URLs; links(listing) -> <=100 card URLs;
    extract(card_document) -> Candidate with facts citing that exact capture.
    Documents beyond the primary card require a separate reviewed parser/reader,
    not a command embedded in a site. Missing terms stay explicitly unverified.
    """
    def __init__(self, source, *, plan, fetch, links, extract, clock):
        if (not source.hosts or not all(callable(callback) for callback in (plan, fetch, links, extract, clock))):
            raise ValueError('reviewed_public_adapter_bindings_required')
        self.source = source
        self.plan, self.fetch, self.links, self.extract, self.clock = plan, fetch, links, extract, clock

    def allowed(self, url):
        if not public_url(url) or urlsplit(url).hostname not in self.source.hosts:
            raise ValueError('reviewed_public_endpoint_required')

    def capture(self, url, started, name):
        self.allowed(url)
        page = self.fetch(url)
        if type(page) is not Page: raise ValueError('typed_public_page_required')
        self.allowed(page.url)
        if page.url != url:
            # A canonical redirect requires an explicit source parser/plan change,
            # never adopt a redirect to a login page as procurement evidence.
            raise ValueError('public_page_identity_changed')
        if page.status in ('login_required', 'captcha', 'unavailable'):
            return None, page.status
        if page.status != 'ok' or page.checked_at is None or not started <= page.checked_at <= self.clock():
            raise ValueError('fresh_public_capture_required')
        doc = Document(name, self.source.id, page.url, name, 'card', page.checked_at, page.text)
        return doc, None

    def __call__(self, profile, started):
        urls = tuple(islice(self.plan(profile), 21))
        if not 1 <= len(urls) <= 20 or len(set(urls)) != len(urls):
            raise ValueError('bounded_unique_search_plan_required')
        listings, candidates, visited = [], [], set()
        for index, url in enumerate(urls):
            listing, failure = self.capture(url, started, f'listing-{index}')
            if failure: return SourceResult(failure, tuple(candidates), tuple(listings))
            listings.append(listing)
            links = tuple(islice(self.links(listing), 101))
            if len(links) > 100: raise ValueError('bounded_primary_card_links_required')
            for card_url in links:
                if card_url in visited: continue
                if len(visited) >= 100: return SourceResult('partial', tuple(candidates), tuple(listings))
                visited.add(card_url)
                card, failure = self.capture(card_url, started, f'card-{len(visited)}')
                if failure: return SourceResult(failure, tuple(candidates), tuple(listings))
                item = self.extract(card)
                if (type(item) is not Candidate or item.source != self.source.id
                        or item.documents != (card,)):
                    raise ValueError('parser_must_cite_exact_primary_capture')
                candidates.append(item)
        return SourceResult('checked', tuple(candidates), tuple(listings))
