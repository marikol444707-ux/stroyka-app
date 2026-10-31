"""Read-only B2B CDP adapter for an already reviewed credentials-free browser.

No browser is started/imported here. open_browser is a protected async context
manager yielding the existing bounded CDP call; it owns isolation, network rules,
robots/access policy and cleanup. Model input cannot select the factory or JS.
"""
import asyncio
import base64
import hashlib
import json
from urllib.parse import parse_qs, urlsplit

from jev_agent.server_runtime.scripts.jev_commercial_search import OBSERVE, search_url, tender_url
from .b2b import B2BReader, Observation, HOST
from .documents import Download, MAX_BYTES, extract_isolated
from .model import public_url
from ..state import Scope

TEXT = '''(()=>{const text=document.body?.innerText||'';
const names=new Set(['документы закупки','документы процедуры','документация закупки']);
const sections=[...document.querySelectorAll('main section,main [role="region"]')].filter(s=>{
 if(s.closest('header,footer,nav,aside'))return false;
 const label=(s.getAttribute('aria-label')||s.querySelector(':scope > h2,:scope > h3,:scope > h4')?.innerText||'')
  .trim().toLowerCase().replace(/\\s+/g,' ');return names.has(label);
});
const links=sections.flatMap(s=>[...s.querySelectorAll('a[href]')].filter(a=>!a.closest('header,footer,nav,aside'))
 .map(a=>({url:a.href,name:(a.innerText||'').slice(0,200),section:'procurement_documents'}))).slice(0,100);
return {url:location.href,
ready:document.readyState,oversize:text.length>131072,text:text.slice(0,131073),
links:links};})()'''

DOWNLOAD_JS='''(async()=>{
const url=__URL__,maximum=__MAX__,timeout=__TIMEOUT__;
const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),timeout);
try {
 const response=await fetch(url,{method:'GET',credentials:'omit',redirect:'error',
   cache:'no-store',referrerPolicy:'no-referrer',signal:controller.signal});
 if(response.url!==url||response.redirected)return {status:'unavailable'};
 if(response.status===401)return {status:'login_required'};
 if(!response.ok)return {status:'unavailable'};
 const declared=Number(response.headers.get('Content-Length')||0);
 if(!Number.isFinite(declared)||declared<0||declared>maximum)return {status:'unavailable'};
 if(!response.body)return {status:'unavailable'};
 const reader=response.body.getReader();const chunks=[];let total=0;
 while(true){
  const next=await reader.read();if(next.done)break;
  total+=next.value.length;
  if(total>maximum||chunks.length>=8192){await reader.cancel();return {status:'unavailable'};}
  chunks.push(next.value);
 }
 if(!total)return {status:'unavailable'};
 let binary='';
 for(const chunk of chunks){
  for(let n=0;n<chunk.length;n+=32768)binary+=String.fromCharCode(...chunk.subarray(n,n+32768));
 }
 return {status:'ok',url:url,bytes:total,base64:btoa(binary)};
}catch(_){return {status:'unavailable'};}finally{controller.abort();clearTimeout(timer);}
})()'''


def attachment_url(url):
    return (public_url(url) and urlsplit(url).hostname==HOST
            and any(urlsplit(url).path.lower().endswith(ext) for ext in ('.pdf','.docx','.txt')))


def approved_url(url):
    if not isinstance(url,str) or len(url)>2048:raise ValueError('bounded_b2b_browser_url_required')
    parsed=urlsplit(url)
    if parsed.path=='/app/next/market-search':
        params=parse_qs(parsed.query,strict_parsing=True)
        term=params.get('q',[])
        if len(term)!=1 or url!=search_url(term[0]):raise ValueError('generated_b2b_search_url_required')
    else:tender_url(url)


class Session:
    def __init__(self,call,clock,*,poll_seconds=.3,access_check=None):
        if not callable(call) or not callable(clock) or not 0<=poll_seconds<=1:
            raise ValueError('protected_bounded_cdp_binding_required')
        self.call,self.clock,self.poll=call,clock,poll_seconds
        self._card=None;self._links=set();self._downloads={};self._download_deadline=None
        self._generation=0
        if access_check is not None and not callable(access_check):raise ValueError('protected_access_check_required')
        self.access_check=access_check

    def approve(self,url):approved_url(url)

    def is_listing(self,url):return urlsplit(url).path=='/app/next/market-search'

    def is_attachment(self,url):return attachment_url(url)

    async def observe_listing(self,url):
        observed=await self.call('Runtime.evaluate',{'expression':OBSERVE,'returnByValue':True})
        if type(observed) is not dict or 'exceptionDetails' in observed:raise ValueError('b2b_search_evaluation_failed')
        return observed.get('result',{}).get('value')

    def invalidate(self):
        self._generation+=1
        self._card=None;self._links.clear();self._downloads.clear();self._download_deadline=None

    async def read(self,url):
        self.approve(url)
        self.invalidate()
        if self.access_check is not None:
            from .access import Decision
            decision=await asyncio.to_thread(self.access_check,url)
            if type(decision) is not Decision:raise ValueError('typed_public_access_decision_required')
            if not decision.allowed:return Observation(url,decision.status,self.clock())
        return await asyncio.wait_for(self._read(url),25)

    async def _read(self,url):
        await self.call('Page.navigate',{'url':url})
        search=self.is_listing(url)
        previous=None
        for _ in range(12):
            reply=await self.call('Runtime.evaluate',{'expression':TEXT,'returnByValue':True})
            page=reply.get('result',{}).get('value') if type(reply) is dict else None
            if (type(page) is not dict or page.get('url')!=url or page.get('oversize') is not False
                    or type(page.get('text')) is not str or len(page['text'].encode())>512*1024):
                raise ValueError('bounded_exact_b2b_page_required')
            if 'exceptionDetails' in reply:raise ValueError('b2b_page_evaluation_failed')
            text=page['text'];folded=text.casefold()
            # Explicit access challenges are terminal; no automatic solving.
            if any(word in folded for word in ('подтвердите, что вы не робот','captcha','проверка, что вы не робот')):
                return Observation(url,'captcha',self.clock())
            if text.strip().casefold() in ('вход в систему','войдите для просмотра закупки','необходима авторизация'):
                return Observation(url,'login_required',self.clock())
            if page.get('ready')!='complete':
                await asyncio.sleep(self.poll);continue
            state=None
            if search:
                state=await self.observe_listing(url)
                # Bound serialization before carrying any source output forward.
                if type(state) is not dict or len(json.dumps(state,ensure_ascii=False).encode())>128*1024:
                    raise ValueError('bounded_b2b_search_state_required')
            links=page.get('links',[])
            if type(links) is not list or len(links)>100 or len(json.dumps(links).encode())>256*1024:
                raise ValueError('bounded_b2b_dom_links_required')
            signature=hashlib.sha256(json.dumps({'text':text,'state':state,'links':links},ensure_ascii=False,sort_keys=True).encode()).hexdigest()
            if signature==previous:
                if not search:
                    if any(type(row) is not dict or set(row) not in ({'url','name'},{'url','name','section'}) for row in links):
                        raise ValueError('observed_dom_attachment_links_required')
                    self._card=url
                    self._links={row['url'] for row in links if row.get('section')=='procurement_documents'
                                 and self.is_attachment(row.get('url'))}
                    self._download_deadline=asyncio.get_running_loop().time()+45
                return Observation(url,'ok',self.clock(),text,state,tuple(links))
            previous=signature
            await asyncio.sleep(self.poll)
        raise ValueError('stable_b2b_page_not_observed')

    async def download(self,url,maximum):
        """Only links from the current stable primary page, no cookies/redirects.

        Fetch runs in a new isolated JS world so page code cannot replace fetch
        or btoa. The existing CDP transport must bound replies to <=12 MiB.
        No arbitrary URL/model-facing download tool is registered.
        """
        if (not self.is_attachment(url) or url not in self._links or self._card is None
                or type(maximum) is not int or not 0<maximum<=MAX_BYTES):
            raise ValueError('current_primary_public_attachment_required')
        if url in self._downloads:
            result=self._downloads[url]
            if len(result.content)>maximum:raise ValueError('cached_attachment_size_limit')
            return result
        if len(self._downloads)>=8 or asyncio.get_running_loop().time()>=self._download_deadline:
            return Download(url,'unavailable',self.clock())
        # Reserve before any remote work; even timeouts do not trigger retries.
        generation=self._generation;card=self._card
        self._downloads[url]=Download(url,'unavailable',self.clock())
        if self.access_check is not None:
            from .access import Decision
            decision=await asyncio.to_thread(self.access_check,url)
            if type(decision) is not Decision:raise ValueError('typed_public_access_decision_required')
            if not decision.allowed:
                result=Download(url,decision.status,self.clock())
                if generation==self._generation:self._downloads[url]=result
                return result
        try:result=await asyncio.wait_for(self._download(url,maximum,card,generation),20)
        except Exception:result=Download(url,'unavailable',self.clock())
        if generation!=self._generation:return Download(url,'unavailable',self.clock())
        self._downloads[url]=result
        return result

    async def _download(self,url,maximum,card,generation):
        frame=await self.call('Page.getFrameTree',{})
        frame=frame.get('frameTree',{}).get('frame',{}) if type(frame) is dict else {}
        if frame.get('url')!=card or generation!=self._generation or type(frame.get('id')) is not str or not frame['id']:
            raise ValueError('current_b2b_frame_changed')
        world=await self.call('Page.createIsolatedWorld',{'frameId':frame['id'],
            'worldName':'jev-public-attachment','grantUniveralAccess':False})
        context=world.get('executionContextId') if type(world) is dict else None
        if generation!=self._generation or self._card!=card:raise ValueError('attachment_card_changed')
        if type(context) is not int or context<=0:raise ValueError('isolated_download_world_required')
        remaining=self._download_deadline-asyncio.get_running_loop().time()
        if remaining<=0:return Download(url,'unavailable',self.clock())
        timeout=max(1,min(15000,int(remaining*1000)))
        expression=DOWNLOAD_JS.replace('__MAX__',str(maximum)).replace('__TIMEOUT__',str(timeout)).replace('__URL__',json.dumps(url))
        reply=await self.call('Runtime.evaluate',{'expression':expression,'contextId':context,
            'returnByValue':True,'awaitPromise':True,'timeout':timeout+1000})
        if generation!=self._generation or self._card!=card:raise ValueError('attachment_card_changed')
        if type(reply) is not dict or 'exceptionDetails' in reply:raise ValueError('attachment_read_failed')
        value=reply.get('result',{}).get('value')
        if type(value) is not dict:raise ValueError('attachment_result_required')
        if value.get('status') in ('unavailable','login_required') and set(value)=={'status'}:
            return Download(url,value['status'],self.clock())
        if (set(value)!={'status','url','bytes','base64'} or value['status']!='ok' or value['url']!=url
                or type(value['bytes']) is not int or not 0<value['bytes']<=maximum
                or type(value['base64']) is not str or len(value['base64'])>((maximum+2)//3)*4):
            raise ValueError('bounded_binary_attachment_required')
        content=base64.b64decode(value['base64'],validate=True)
        if len(content)!=value['bytes']:raise ValueError('attachment_size_mismatch')
        return Download(url,'ok',self.clock(),content)


def browser_adapter(*,open_browser,clock,document_enricher=None,document_scope=None,
                    extract_document=extract_isolated,access_check=None):
    """Protected sync worker adapter. No asyncio loop or browser on import."""
    if not callable(open_browser) or not callable(clock):raise ValueError('protected_browser_factory_required')
    if document_scope is not None:
        if type(document_scope) is not Scope or document_enricher is not None:
            raise ValueError('one_protected_document_binding_required')
        document_scope.key()
    if not callable(extract_document):raise ValueError('protected_document_extractor_required')
    def collect(profile,started):
        async def operation():
            async with open_browser() as call:
                session=Session(call,clock,access_check=access_check)
                loop=asyncio.get_running_loop()
                def read(url):
                    future=asyncio.run_coroutine_threadsafe(session.read(url),loop)
                    try:return future.result(timeout=30)
                    except BaseException:
                        future.cancel();raise
                bound=document_enricher
                if document_scope is not None:
                    from functools import partial
                    from .terms import enrich
                    def fetch(url,maximum):
                        future=asyncio.run_coroutine_threadsafe(session.download(url,maximum),loop)
                        try:return future.result(timeout=25)
                        except BaseException:
                            future.cancel();raise
                    bound=partial(enrich,scope=document_scope,hosts={'b2b':(HOST,)},fetch=fetch,
                                  clock=clock,extract=extract_document)
                return await asyncio.to_thread(B2BReader(read=read,clock=clock,document_enricher=bound),profile,started)
        # The host worker is synchronous. Existing async callers must use an
        # explicit worker thread, not nest or replace Hermes' running loop.
        try:asyncio.get_running_loop()
        except RuntimeError:pass
        else:raise ValueError('synchronous_host_worker_required')
        return asyncio.run(operation())
    return collect
