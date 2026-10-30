"""Read-only B2B CDP adapter for an already reviewed credentials-free browser.

No browser is started/imported here. open_browser is a protected async context
manager yielding the existing bounded CDP call; it owns isolation, network rules,
robots/access policy and cleanup. Model input cannot select the factory or JS.
"""
import asyncio
import hashlib
import json
from urllib.parse import parse_qs, urlsplit

from jev_agent.server_runtime.scripts.jev_commercial_search import OBSERVE, search_url, tender_url
from .b2b import B2BReader, Observation, HOST

TEXT = '''(()=>{const text=document.body?.innerText||'';return {url:location.href,
ready:document.readyState,oversize:text.length>131072,text:text.slice(0,131073)};})()'''


def approved_url(url):
    if not isinstance(url,str) or len(url)>2048:raise ValueError('bounded_b2b_browser_url_required')
    parsed=urlsplit(url)
    if parsed.path=='/app/next/market-search':
        params=parse_qs(parsed.query,strict_parsing=True)
        term=params.get('q',[])
        if len(term)!=1 or url!=search_url(term[0]):raise ValueError('generated_b2b_search_url_required')
    else:tender_url(url)


class Session:
    def __init__(self,call,clock,*,poll_seconds=.3):
        if not callable(call) or not callable(clock) or not 0<=poll_seconds<=1:
            raise ValueError('protected_bounded_cdp_binding_required')
        self.call,self.clock,self.poll=call,clock,poll_seconds

    async def read(self,url):
        approved_url(url)
        return await asyncio.wait_for(self._read(url),25)

    async def _read(self,url):
        await self.call('Page.navigate',{'url':url})
        search=urlsplit(url).path=='/app/next/market-search'
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
                observed=await self.call('Runtime.evaluate',{'expression':OBSERVE,'returnByValue':True})
                if type(observed) is not dict or 'exceptionDetails' in observed:raise ValueError('b2b_search_evaluation_failed')
                state=observed.get('result',{}).get('value')
                # Bound serialization before carrying any source output forward.
                if type(state) is not dict or len(json.dumps(state,ensure_ascii=False).encode())>128*1024:
                    raise ValueError('bounded_b2b_search_state_required')
            signature=hashlib.sha256(json.dumps({'text':text,'state':state},ensure_ascii=False,sort_keys=True).encode()).hexdigest()
            if signature==previous:return Observation(url,'ok',self.clock(),text,state)
            previous=signature
            await asyncio.sleep(self.poll)
        raise ValueError('stable_b2b_page_not_observed')


def browser_adapter(*,open_browser,clock):
    """Protected sync worker adapter. No asyncio loop or browser on import."""
    if not callable(open_browser) or not callable(clock):raise ValueError('protected_browser_factory_required')
    def collect(profile,started):
        async def operation():
            async with open_browser() as call:
                session=Session(call,clock)
                loop=asyncio.get_running_loop()
                def read(url):
                    future=asyncio.run_coroutine_threadsafe(session.read(url),loop)
                    try:return future.result(timeout=30)
                    except BaseException:
                        future.cancel();raise
                return await asyncio.to_thread(B2BReader(read=read,clock=clock),profile,started)
        # The host worker is synchronous. Existing async callers must use an
        # explicit worker thread, not nest or replace Hermes' running loop.
        try:asyncio.get_running_loop()
        except RuntimeError:pass
        else:raise ValueError('synchronous_host_worker_required')
        return asyncio.run(operation())
    return collect
