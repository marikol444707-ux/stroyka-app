"""Read-only public EIS originals and review snapshots. No application credentials."""
import asyncio
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
from urllib.parse import parse_qs, urljoin, urlparse
from uuid import uuid4

try:
    from scripts.jev_eis_probe import verify_ca
except ImportError:
    from jev_eis_probe import verify_ca

MAX_FILE=32*1024*1024
MAX_TOTAL=128*1024*1024


def validate_notice(url):
    p=urlparse(url);q=parse_qs(p.query)
    if (p.scheme!='https' or p.netloc!='zakupki.gov.ru' or p.fragment
        or not re.fullmatch(r'/epz/order/notice/(?:zk20|ok20|ea20)/view/common-info.html',p.path)
        or set(q)!={'regNumber'} or len(q['regNumber'])!=1 or not re.fullmatch(r'\d{19}',q['regNumber'][0])):raise ValueError('Unsupported notice URL')
    return q['regNumber'][0]


def validate_download(url):
    p=urlparse(url);q=parse_qs(p.query)
    if (p.scheme!='https' or p.netloc!='zakupki.gov.ru' or p.fragment
        or p.path!='/44fz/filestore/public/1.0/download/priz/file.html'
        or set(q)!={'uid'} or len(q['uid'])!=1 or not re.fullmatch(r'[A-Fa-f0-9]{32}',q['uid'][0])):raise ValueError('Unsupported original URL')
    return url


class Page(HTMLParser):
    def __init__(self):
        super().__init__();self.links=[];self.anchor=None;self.label=[];self.text=[];self.skip=0
    def handle_starttag(self,tag,attrs):
        if tag in {'script','style'}:self.skip+=1
        if tag=='a':self.anchor=dict(attrs);self.label=[]
    def handle_endtag(self,tag):
        if tag in {'script','style'}:self.skip=max(0,self.skip-1)
        if tag=='a' and self.anchor is not None:
            self.links.append({**self.anchor,'text':' '.join(' '.join(self.label).split())});self.anchor=None
    def handle_data(self,data):
        if not self.skip and data.strip():self.text.append(data.strip())
        if self.anchor is not None:self.label.append(data)


def inventory(html, number):
    page=Page();page.feed(html);text='\n'.join(page.text)
    if not re.search(r'(?<!\d)'+re.escape(number)+r'(?!\d)',text):raise ValueError('Wrong notice in document page')
    files={}
    for anchor in page.links:
        url=urljoin('https://zakupki.gov.ru',anchor.get('href',''))
        try:validate_download(url)
        except ValueError:continue
        files[url]={'url':url,'name':anchor.get('title') or anchor['text']}
    if len(files)>25:raise ValueError('Document count limit')
    return {'notice_number':number,'files':list(files.values()),'listing_text':text,
            'listing_sha256':hashlib.sha256(text.encode()).hexdigest(),
            'revision_label':'Действующая' if re.search(r'Редакция\s+Действующая',text) else 'не подтверждена'}


class Browser:
    def __init__(self, env, tmp):self.env=env;self.tmp=tmp;self.seq=0;self.events=[]
    async def __aenter__(self):
        import urllib.request
        import websockets
        self.chrome=subprocess.Popen(['/usr/bin/google-chrome','--headless=new','--no-sandbox','--disable-dev-shm-usage','--remote-debugging-port=9229','--user-data-dir='+self.tmp+'/chrome','about:blank'],env=self.env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            for _ in range(40):
                try:
                    with urllib.request.urlopen('http://127.0.0.1:9229/json/list',timeout=1) as r:pages=[x for x in json.load(r) if x.get('type')=='page']
                    if pages:break
                except OSError:pass
                await asyncio.sleep(.2)
            else:raise TimeoutError('Browser startup')
            endpoint=pages[0]['webSocketDebuggerUrl']
            if not endpoint.startswith('ws://127.0.0.1:9229/devtools/page/'):raise ValueError('Unexpected CDP endpoint')
            self.ws=await websockets.connect(endpoint,max_size=4*1024*1024)
            return self
        except BaseException:
            await self.__aexit__(None,None,None);raise
    async def __aexit__(self,*args):
        try:
            if hasattr(self,'ws'):await self.ws.close()
        finally:
            self.chrome.terminate()
            try:self.chrome.wait(timeout=5)
            except subprocess.TimeoutExpired:self.chrome.kill();self.chrome.wait(timeout=5)
    async def receive(self):
        value=json.loads(await asyncio.wait_for(self.ws.recv(),15))
        if 'method' in value:
            self.events.append(value)
            if len(self.events)>3000:self.events=self.events[-1500:]
        return value
    async def call(self,method,params):
        self.seq+=1;seq=self.seq
        await self.ws.send(json.dumps({'id':seq,'method':method,'params':params}))
        deadline=time.monotonic()+25
        while time.monotonic()<deadline:
            reply=await self.receive()
            if reply.get('id')==seq:
                if 'error' in reply:
                    error=reply['error'];message=str(error.get('message',''))
                    if method=='Runtime.evaluate' and any(x in message for x in ['Cannot find context','Execution context was destroyed']):return {}
                    raise RuntimeError('Browser command rejected: '+method)
                return reply.get('result',{})
        raise TimeoutError('Browser command budget')
    async def read(self,expression):
        result=await self.call('Runtime.evaluate',{'expression':expression,'returnByValue':True})
        if result.get('exceptionDetails'):return None
        return result.get('result',{}).get('value')
    async def page(self,url,number):
        await self.call('Page.navigate',{'url':url})
        for _ in range(60):
            state=await self.read('({url:location.href,ready:document.readyState,html:document.documentElement?.outerHTML||"",text:document.body?.innerText||""})')
            if state and state['ready']=='complete' and number in state['text']:
                p=urlparse(state['url'])
                if p.scheme!='https' or p.netloc!='zakupki.gov.ru':raise ValueError('Foreign page redirect')
                return state
            await asyncio.sleep(.3)
        raise TimeoutError('Notice page not ready')
    async def download(self,url,directory):
        validate_download(url);self.events=[]
        await self.call('Browser.setDownloadBehavior',{'behavior':'allowAndName','downloadPath':str(directory),'eventsEnabled':True})
        await self.call('Page.navigate',{'url':url})
        guid=None;finished=False;deadline=time.monotonic()+55
        while time.monotonic()<deadline:
            events,self.events=self.events,[]
            for event in events:
                p=event.get('params',{});method=event.get('method')
                if method=='Browser.downloadWillBegin':
                    if p.get('url')!=url:raise ValueError('Unexpected download URL')
                    guid=p['guid']
                    if not re.fullmatch(r'[a-zA-Z0-9-]{1,80}',guid):raise ValueError('Unexpected download ID')
                if method=='Browser.downloadProgress' and guid and p.get('guid')==guid:
                    if max(p.get('totalBytes',0),p.get('receivedBytes',0))>MAX_FILE:
                        await self.call('Browser.cancelDownload',{'guid':guid});raise ValueError('File size limit')
                    if p.get('state')=='canceled':raise RuntimeError('Download canceled')
                    finished=p.get('state')=='completed'
            if finished:
                path=directory/guid
                if path.exists() and path.stat().st_size<=MAX_FILE:return path
            try:await asyncio.wait_for(self.receive(),2)
            except asyncio.TimeoutError:pass
        raise TimeoutError('Original download budget')


async def collect(notice, destination, env, tmp):
    number=validate_notice(notice);destination.mkdir(parents=True,exist_ok=True)
    originals=destination/'originals';originals.mkdir(exist_ok=True)
    async with Browser(env,tmp) as browser:
        card=await browser.page(notice,number);p=Page();p.feed(card['html'])
        docs=next((urljoin(notice,a.get('href','')) for a in p.links if urlparse(urljoin(notice,a.get('href',''))).path==urlparse(notice).path.replace('common-info.html','documents.html') and parse_qs(urlparse(urljoin(notice,a.get('href',''))).query).get('regNumber')==[number]),None)
        if not docs:raise ValueError('Document tab not found')
        state=await browser.page(docs,number);listing=inventory(state['html'],number)
        (destination/'card.txt').write_text(card['text']);(destination/'listing.txt').write_text(state['text'])
        result={**listing,'notice_url':notice,'documents_url':docs,'retrieved_at':datetime.now(timezone.utc).isoformat(),'card_text':card['text'],'documents':[],'issues':[]}
        total=0
        for index,item in enumerate(listing['files'],1):
            document={'id':'d'+str(index),**item,'status':'download_failed'}
            try:
                path=await browser.download(item['url'],originals);total+=path.stat().st_size
                if total>MAX_TOTAL:raise ValueError('Total download limit')
                suffix=Path(item['name']).suffix.lower()
                if suffix not in {'.docx','.xlsx','.pdf','.xls','.doc','.rtf','.zip','.txt','.csv','.xlsm'}:suffix='.bin'
                saved=originals/('d'+str(index)+suffix);path.rename(saved)
                document.update(status='downloaded',path=str(saved.relative_to(destination)),bytes=saved.stat().st_size,sha256=hashlib.sha256(saved.read_bytes()).hexdigest())
            except Exception as exc:document['error_type']=type(exc).__name__;result['issues'].append(item['name']+': '+type(exc).__name__)
            result['documents'].append(document)
        refreshed=inventory((await browser.page(docs,number))['html'],number)
        result['snapshot_consistent']=listing['files']==refreshed['files'] and listing['listing_sha256']==refreshed['listing_sha256']
        if not result['snapshot_consistent']:result['issues'].append('Набор или редакция документов изменились во время проверки')
        if not result['documents']:result['issues'].append('Оригиналы не найдены')
        (destination/'manifest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
        return result


def worker(notice,destination):
    validate_notice(notice)
    verify_ca(Path('/cert/root.pem'))
    tmp=tempfile.mkdtemp(prefix='eis-docs-');env={'HOME':tmp,'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'}
    db=Path(tmp)/'.pki/nssdb';db.mkdir(parents=True)
    for args in [['certutil','-N','-d','sql:'+str(db),'--empty-password'],['certutil','-A','-d','sql:'+str(db),'-n','EIS Root','-t','C,,','-i','/cert/root.pem']]:subprocess.run(args,env=env,capture_output=True,check=True,timeout=5)
    return asyncio.run(collect(notice,Path(destination),env,tmp))


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--notice',required=True);parser.add_argument('--output',default='/output');args=parser.parse_args()
    try:
        result=worker(args.notice,args.output)
        print(json.dumps({'ok':not result['issues'],'documents':len(result['documents']),'issues':result['issues']},ensure_ascii=False))
    except Exception as exc:print(json.dumps({'ok':False,'status':'documents_failed','error_type':type(exc).__name__}));raise SystemExit(1)
