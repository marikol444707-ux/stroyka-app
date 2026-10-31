"""Shared bounded browser lifecycle for the whole reviewed source batch.

No legacy search subprocesses, inferred MSK/worksite facts, inherited account or
paid search. Each source receives an isolated context from the protected factory.
The factory must enforce the source's hosts and credentials-free network policy.
"""
import asyncio
from functools import partial
import hashlib
import re
import time
from urllib.parse import urlsplit

from jev_agent.server_runtime.scripts.jev_commercial_search import SBER_OBSERVE
from .b2b_browser import Session,browser_adapter
from .documents import Attachment,extract_isolated
from .model import Document,public_url
from .platforms import PortalSpec,platform_specs,listing_urls,parse_primary,LISTING_JS
from .runner import SourceResult
from .sources import source_registry
from .terms import enrich
from ..state import Scope

LIMITATIONS=('first_pages_only','primary_parser_not_live_verified','documents_not_read')


class PortalSession(Session):
    def __init__(self,call,clock,spec,**kwargs):
        super().__init__(call,clock,**kwargs);self.spec=spec

    def approve(self,url):return self.spec.approve(url)

    def is_listing(self,url):return url in self.spec.listings

    def is_attachment(self,url):
        return (public_url(url) and urlsplit(url).hostname in self.spec.source.hosts
                and any(urlsplit(url).path.lower().endswith(ext) for ext in ('.pdf','.docx','.txt')))

    async def observe_listing(self,url):
        script=SBER_OBSERVE if self.spec.source.id=='sber' else LISTING_JS
        reply=await self.call('Runtime.evaluate',{'expression':script,'returnByValue':True})
        if type(reply) is not dict or 'exceptionDetails' in reply:raise ValueError('source_listing_evaluation_failed')
        state=reply.get('result',{}).get('value')
        return {'url':url,'notice_urls':listing_urls(self.spec,url,state)}


def references(observation,card,source):
    if type(observation.attachment_links) is not tuple or len(observation.attachment_links)>100:
        raise ValueError('bounded_source_attachments_required')
    result=[];seen=set()
    for row in observation.attachment_links:
        if type(row) is not dict or row.get('section')!='procurement_documents':continue
        url=row.get('url');name=row.get('name')
        if (not public_url(url) or urlsplit(url).hostname not in source.hosts or type(name) is not str
                or url in seen):continue
        extension=next((ext for ext in ('.pdf','.docx','.txt') if urlsplit(url).path.lower().endswith(ext)),None)
        if extension is None:continue
        if len(result)>=8:break
        seen.add(url);name=re.sub(r'[\x00-\x20\x7f]+',' ',name).strip()[:200] or 'Документ закупки'
        kind='contract' if 'договор' in name.casefold() else 'authority' if 'полномочи' in name.casefold() else 'terms'
        result.append(Attachment(source.id+'-doc-'+hashlib.sha256(url.encode()).hexdigest()[:16],source.id,url,name,kind,
                                 extension,card,'Вложение из DOM: '+name+' — '+url))
    return tuple(result)


def collect_portal(spec,*,read,clock,document_enricher=None,monotonic=time.monotonic):
    listings=[];candidates=[];captures=[];attachments=[];seen=set();calls=0;deadline=monotonic()+180
    limitations=list(LIMITATIONS)
    if document_enricher is not None:limitations[-1]='document_coverage_incomplete'
    def finish(status,extra=()):
        return SourceResult(status,tuple(candidates),tuple(listings),tuple(dict.fromkeys((*limitations,*extra))),
                            tuple(captures),tuple(attachments))
    def capture(url,identifier):
        kind=spec.approve(url);observed=read(url);now=clock()
        if observed.url!=url or not spec.planned_at<=observed.checked_at<=now:
            raise ValueError('fresh_exact_source_capture_required')
        if observed.status in ('captcha','login_required','unavailable','robots_disallow','policy_not_verified'):return None,observed
        if observed.status!='ok':raise ValueError('source_capture_not_verified')
        refs=references(observed,identifier,spec.source) if kind=='card' else ()
        text=observed.text+''.join('\n'+ref.link_quote for ref in refs)
        return Document(identifier,spec.source.id,url,'Выдача '+spec.source.name if kind=='listing' else
                        'Карточка '+spec.source.name,'card',observed.checked_at,text),observed
    for index,url in enumerate(spec.listings):
        if calls>=40 or monotonic()>=deadline:return finish('partial',('read_budget_exhausted',))
        calls+=1
        try:listing,page=capture(url,spec.source.id+'-listing-'+str(index))
        except Exception:return finish('error',('some_primary_cards_not_verified',))
        if listing is None:return finish(page.status)
        listings.append(listing)
        state=page.search_state
        if (type(state) is not dict or state.get('url')!=url or type(state.get('notice_urls')) is not list
                or len(state['notice_urls'])>40):return finish('partial',('some_primary_cards_not_verified',))
        for notice in state['notice_urls']:
            try:
                if spec.approve(notice)!='card':continue
            except (ValueError,TypeError):continue
            if notice in seen:continue
            if calls>=40 or monotonic()>=deadline:return finish('partial',('read_budget_exhausted',))
            seen.add(notice);calls+=1
            try:card,observed=capture(notice,spec.source.id+'-card-'+str(len(seen)))
            except Exception:return finish('error',('some_primary_cards_not_verified',))
            if card is None:return finish(observed.status)
            captures.append(card)
            try:
                candidate=parse_primary(card,spec.source.id)
                if document_enricher:
                    enriched=document_enricher(candidate,references(observed,card.id,spec.source))
                    attachments.extend(enriched.statuses);candidate=enriched.candidate
                candidates.append(candidate)
            except ValueError:
                limitations.append('some_primary_cards_not_verified')
    return finish('partial')


def portal_adapter(spec_factory,*,open_browser,clock,scope=None,extract_document=extract_isolated,access_check=None):
    if scope is not None:
        if type(scope) is not Scope:raise ValueError('protected_source_scope_required')
        scope.key()
    def collect(profile,started):
        spec=spec_factory(profile,started)
        if type(spec) is not PortalSpec or not spec.source.hosts or len(spec.listings)>20:
            raise ValueError('bounded_reviewed_source_spec_required')
        async def operation():
            async with open_browser(spec.source) as call:
                session=PortalSession(call,clock,spec,access_check=access_check);loop=asyncio.get_running_loop()
                def sync(coroutine,timeout):
                    future=asyncio.run_coroutine_threadsafe(coroutine,loop)
                    try:return future.result(timeout=timeout)
                    except BaseException:future.cancel();raise
                read=lambda url:sync(session.read(url),30)
                bound=None
                if scope is not None:
                    bound=partial(enrich,scope=scope,hosts={spec.source.id:spec.source.hosts},
                                  fetch=lambda url,maximum:sync(session.download(url,maximum),25),
                                  clock=clock,extract=extract_document)
                return await asyncio.to_thread(collect_portal,spec,read=read,clock=clock,document_enricher=bound)
        try:asyncio.get_running_loop()
        except RuntimeError:pass
        else:raise ValueError('synchronous_host_worker_required')
        return asyncio.run(operation())
    return collect


def source_bundle(*,open_browser,clock,scope=None,reviewed_recipes=None,extra_sources=(),extract_document=extract_isolated,
                  access_check=None):
    """One call binds all eight existing platforms plus reviewed new portals.

    open_browser(source) is mandatory and operator-bound. No guessing Tender.Pro,
    corporate procurement paths or domains. Unconfigured research targets remain
    explicitly not_connected in the ordinary runner coverage table.
    """
    if not callable(open_browser) or not callable(clock):raise ValueError('protected_batch_browser_factory_required')
    sources=source_registry(extra_sources)
    gate={}
    def permission(url):return gate['check'](url)
    adapters={'b2b':browser_adapter(open_browser=lambda:open_browser(sources['b2b']),clock=clock,
                                  document_scope=scope,extract_document=extract_document,access_check=permission)}
    for key in ('fabrikant','tektorg','gpb','roseltorg','sber','federation','rtender'):
        factory=lambda profile,now,key=key:platform_specs(profile,now)[key]
        adapters[key]=portal_adapter(factory,open_browser=open_browser,clock=clock,scope=scope,extract_document=extract_document,access_check=permission)
    for key,factory in (reviewed_recipes or {}).items():
        if key not in sources or key in adapters:raise ValueError('unique_registered_portal_recipe_required')
        def checked(profile,now,key=key,factory=factory):
            spec=factory(profile,now)
            if type(spec) is not PortalSpec or spec.source.id!=key or not spec.source.hosts:
                raise ValueError('reviewed_portal_identity_required')
            return spec
        # Resolve source metadata once, from protected configuration, not model
        # JSON. Recipes must retain this exact source on each invocation.
        from .model import Profile
        sample=checked(Profile(),clock());sources[key]=sample.source
        def frozen(profile,now,checked=checked,source=sample.source):
            spec=checked(profile,now)
            if spec.source!=source:raise ValueError('portal_source_changed')
            return spec
        adapters[key]=portal_adapter(frozen,open_browser=open_browser,clock=clock,scope=scope,extract_document=extract_document,access_check=permission)
    if access_check is None:
        from .access import PublicAccess
        gate['check']=PublicAccess(host for source in sources.values() for host in source.hosts).check
    elif callable(access_check):gate['check']=access_check
    else:raise ValueError('protected_batch_access_check_required')
    # Permission is checked before starting an expensive browser as well as
    # inside Session before every page/file. Denied/unknown robots must not be
    # masked by an unavailable local Chrome runtime.
    from .access import Decision
    from jev_agent.server_runtime.scripts.jev_commercial_search import search_url
    for key,adapter in list(adapters.items()):
        def guarded(profile,started,key=key,adapter=adapter):
            if key=='b2b':first=search_url(profile.queries[0])
            elif key in ('fabrikant','tektorg','gpb','roseltorg','sber','federation','rtender'):
                first=platform_specs(profile,started)[key].listings[0]
            else:first=reviewed_recipes[key](profile,started).listings[0]
            decision=permission(first)
            if type(decision) is not Decision:raise ValueError('typed_source_preflight_required')
            if not decision.allowed:return SourceResult(decision.status)
            return adapter(profile,started)
        adapters[key]=guarded
    return sources,adapters
