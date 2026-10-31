"""One batch of source-specific public plans; no claim of live acceptance.

Only endpoints/notice families already present in the legacy implementation are
used. Customer-region filters and legacy inferred timezone/region facts are NOT
carried forward. Primary fields are freshly parsed independently of discovery.
Unknown new portals need an operator-reviewed recipe, never a guessed endpoint.
"""
from dataclasses import dataclass
from datetime import datetime
import json
import re
from urllib.parse import urlencode,urlsplit

from jev_agent.server_runtime.scripts import jev_commercial_search as legacy
from .model import Candidate,Document,public_url
from .model import aware
from .b2b import extract_fields
from .sources import Source,source_registry

PROVIDERS={'fabrikant':'Фабрикант','tektorg':'ТЭК-Торг','gpb':'ЭТП ГПБ','roseltorg':'Росэлторг',
           'sber':'Сбер А','federation':'Торги Федерации','rtender':'Р-ТЕНДЕР'}


@dataclass(frozen=True)
class PortalSpec:
    source: Source
    listings: tuple[str,...]
    terms: tuple[str|None,...]
    provider: str | None = None
    # Generic owner portals need reviewed notice path patterns, supplied only
    # by protected configuration after inspecting the official procurement site.
    notice_pattern: str | None = None
    planned_at: datetime | None = None
    notice_query_key: str | None = None

    def __post_init__(self):
        if (type(self.source) is not Source or not self.source.hosts or type(self.listings) is not tuple
                or not 1<=len(self.listings)<=20 or len(set(self.listings))!=len(self.listings)
                or type(self.terms) is not tuple or len(self.terms)!=len(self.listings)
                or not aware(self.planned_at)
                or any(not public_url(url) or urlsplit(url).hostname not in self.source.hosts for url in self.listings)):
            raise ValueError('bounded_reviewed_portal_spec_required')

    def approve(self,url):
        if not public_url(url) or urlsplit(url).hostname not in self.source.hosts:
            raise ValueError('reviewed_public_source_url_required')
        if url in self.listings:return 'listing'
        if self.provider:
            if legacy.procedure_url({'source':self.provider,'url':url})!=url:
                raise ValueError('exact_primary_url_required')
        elif self.notice_pattern:
            from urllib.parse import parse_qs
            parsed=urlsplit(url)
            if not re.fullmatch(self.notice_pattern,parsed.path):
                raise ValueError('reviewed_owner_notice_path_required')
            if self.notice_query_key is None:
                if parsed.query:raise ValueError('unexpected_owner_notice_query')
            else:
                params=parse_qs(parsed.query,strict_parsing=True)
                if (set(params)!={self.notice_query_key} or len(params[self.notice_query_key])!=1
                        or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,127}',params[self.notice_query_key][0])):
                    raise ValueError('exact_owner_notice_identifier_required')
        else:raise ValueError('reviewed_primary_url_family_required')
        return 'card'


def platform_specs(profile,now):
    profile.validate();sources=source_registry()
    terms=tuple(dict.fromkeys((*profile.queries,*profile.regions)))
    if len(terms)>20:raise ValueError('bounded_source_terms_required')
    rosel=lambda term:'https://www.roseltorg.ru/procedures/search_ajax?'+urlencode([
        ('sale','1'),('source[]','2'),('status[]','0'),('status[]','5'),('query_field',term)])
    plans={
        'roseltorg':tuple(rosel(term) for term in terms),
        'tektorg':tuple(legacy.tektorg_search_url(term) for term in terms),
        'sber':tuple(legacy.sber_search_url(term,now) for term in terms),
        'rtender':tuple(legacy.rtender_search_url(term) for term in terms),
        'fabrikant':('https://www.fabrikant.ru/procedure/search/purchases?'+urlencode([
            ('section_ids[]','2'),('statuses[]','1'),('statuses[]','5')]),),
        'gpb':('https://etpgpb.ru/api/v2/procedures/?'+urlencode([
            ('page','1'),('per','10'),('procedure[stage][0]','accepting')]),),
        'federation':('https://lk.fedtorgi.ru/api/v1/procedures/search?page=1&limit=10',),
    }
    result={}
    for key,urls in plans.items():
        result[key]=PortalSpec(sources[key],urls,terms if len(urls)==len(terms) else (None,)*len(urls),PROVIDERS[key],planned_at=now)
    return result


def parse_primary(document,source):
    """Explicit primary procedure heading only; never use listing slug as ID."""
    if document.source!=source:raise ValueError('primary_source_identity_required')
    pattern=r'(?:Тендер|Закупка|Процедура|Запрос предложений|Запрос цен|Конкурс|Аукцион)\s*(?:№|номер)\s*([A-Za-zА-Яа-я0-9][A-Za-zА-Яа-я0-9._/-]{0,127})(?![A-Za-zА-Яа-я0-9])'
    identifiers=set(re.findall(pattern,document.text,re.I))
    if len(identifiers)!=1:raise ValueError('unique_primary_procedure_number_required')
    return Candidate(source,next(iter(identifiers)),(document,),extract_fields(document))


LISTING_JS='''(()=>({url:location.href,
links:[...document.querySelectorAll('main a[href]')].filter(a=>!a.closest('header,footer,nav,aside')).slice(0,200).map(a=>a.href),
next:document.querySelector('script#__NEXT_DATA__')?.textContent?.slice(0,1048577)||null,
text:(document.body?.innerText||'').slice(0,131073)}))()'''


def listing_urls(spec,url,payload):
    """Identifiers/links only. Prices, deadlines, region and role are discarded."""
    if type(payload) is not dict or payload.get('url')!=url:raise ValueError('exact_listing_capture_required')
    index=spec.listings.index(url);term=spec.terms[index]
    links=payload.get('links',[])
    if type(links) is not list or len(links)>200:raise ValueError('bounded_listing_links_required')
    links=list(links)
    key=spec.source.id
    if key in ('gpb','rtender'):
        raw=payload.get('text','')
        if type(raw) is not str or len(raw.encode())>256*1024:raise ValueError('bounded_listing_json_required')
        data=json.loads(raw)
        if key=='gpb':
            rows=data.get('data') if type(data) is dict else None
            if type(rows) is not list or len(rows)>20:raise ValueError('bounded_gpb_listing_required')
            for row in rows:
                try:links.append(legacy.etpgpb_row(row)['url'])
                except (ValueError,KeyError,TypeError):continue
        else:
            rows=legacy.rtender_page_data(url,data,term)['list']
            for row in rows:
                try:links.append(legacy.rtender_row(row)['url'])
                except (ValueError,KeyError,TypeError):continue
    elif key=='tektorg' and payload.get('next') is not None:
        raw=payload['next']
        if type(raw) is not str or len(raw.encode())>1024*1024:raise ValueError('bounded_tektorg_state_required')
        state=json.loads(raw)
        props=state.get('props',{}).get('pageProps',{})
        listing=props.get('initialReduxState',{}).get('listingProcedures',{})
        rows=listing.get('data')
        if type(rows) is not list or not all(legacy.tektorg_search_checks(url,props,listing,rows,term).values()):
            raise ValueError('tektorg_listing_not_verified')
        for row in rows:
            try:links.append(legacy.tektorg_row(row)['url'])
            except (ValueError,KeyError,TypeError):continue
    elif key=='sber':
        if not all(legacy.sber_search_checks(payload,term,now=spec.planned_at,requested_url=url).values()):
            raise ValueError('sber_listing_not_verified')
        rows=payload.get('rows',[])
        if type(rows) is not list or len(rows)>20:raise ValueError('bounded_sber_listing_required')
        for row in rows:
            if row.get('source','').strip()!='Торги коммерческих заказчиков':continue
            try:links.append(legacy.procedure_url({'source':'Сбер А','url':row['url']}))
            except (ValueError,KeyError,TypeError):continue
    result=[]
    for link in links:
        try:
            if spec.approve(link)=='card' and link not in result:result.append(link)
        except (ValueError,TypeError):continue
        if len(result)>=40:break
    return result
