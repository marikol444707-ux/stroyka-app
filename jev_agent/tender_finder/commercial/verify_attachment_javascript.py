"""Execute the fixed download JS with synthetic streams; not a live Chrome test."""
import base64
import json
import shutil
import unittest

from .b2b_browser import DOWNLOAD_JS
from ..invoker import _run_bounded

LAUNCHER=r'''
const fs=require('fs'),vm=require('vm');const input=JSON.parse(fs.readFileSync(0,'utf8'));
const active=new Set();let cancelled=false,reads=0,options=null,requested=null,index=0;
const fixture=input.fixture;
const context={AbortController,Uint8Array,String,Number,btoa,
 setTimeout:(fn,ms)=>{const id=setTimeout(fn,ms);active.add(id);return id;},
 clearTimeout:id=>{clearTimeout(id);active.delete(id);},
 fetch:async(url,opts)=>{
  options=opts;requested=url;
  if(fixture.hang)return await new Promise((_,reject)=>opts.signal.addEventListener('abort',()=>reject(Error('fixture-abort'))));
  return {url:fixture.url||url,redirected:!!fixture.redirected,status:fixture.status||200,ok:fixture.ok!==false,
   headers:{get:()=>fixture.declared===undefined?null:fixture.declared},
   body:fixture.noBody?null:{getReader:()=>({
    read:async()=>{reads++;if(fixture.readError)throw Error('fixture-error');
      if(index>=(fixture.chunks||[]).length)return {done:true};
      return {done:false,value:Uint8Array.from(fixture.chunks[index++])};},
    cancel:async()=>{cancelled=true;}})}};}
};
Promise.resolve(vm.runInNewContext(input.expression,context,{timeout:1000})).then(value=>{
 process.stdout.write(JSON.stringify({value,cancelled,reads,requested,activeTimers:active.size,
   method:options?.method,credentials:options?.credentials,redirect:options?.redirect,
   referrerPolicy:options?.referrerPolicy,aborted:options?.signal.aborted}));
}).catch(()=>{process.exitCode=2;});
'''


def execute(fixture,*,maximum=65536,url='https://www.b2b-center.ru/documents/fixture.docx'):
    node=shutil.which('node')
    if not node:raise ValueError('node_required_for_javascript_acceptance')
    expression=DOWNLOAD_JS.replace('__MAX__',str(maximum)).replace('__TIMEOUT__','20').replace('__URL__',json.dumps(url))
    output,code=_run_bounded((node,'-e',LAUNCHER),json.dumps({'expression':expression,'fixture':fixture}).encode(),5)
    if code!=0:raise ValueError('download_javascript_fixture_failed')
    return json.loads(output)


class JavaScriptTests(unittest.TestCase):
    def test_binary_roundtrip_get_options_and_timer_cleanup(self):
        expected=bytes(range(256))*180
        chunks=[list(expected[:33000]),list(expected[33000:])]
        report=execute({'chunks':chunks})
        self.assertEqual(base64.b64decode(report['value']['base64']),expected)
        self.assertEqual(report['value']['bytes'],len(expected))
        self.assertEqual((report['method'],report['credentials'],report['redirect'],report['referrerPolicy']),
                         ('GET','omit','error','no-referrer'))
        self.assertEqual(report['activeTimers'],0);self.assertTrue(report['aborted'])

    def test_stream_oversize_cancels_before_accumulating_more(self):
        report=execute({'chunks':[[1]*100,[2]*100]},maximum=150)
        self.assertEqual(report['value'],{'status':'unavailable'})
        self.assertTrue(report['cancelled']);self.assertEqual(report['reads'],2)

    def test_declared_oversize_and_nonfinite_size_reject_before_body_read(self):
        for declared in ('9999999999','Infinity','-1','not a number'):
            report=execute({'declared':declared,'chunks':[[1,2,3]]},maximum=100)
            self.assertEqual(report['value'],{'status':'unavailable'});self.assertEqual(report['reads'],0)

    def test_login_redirect_empty_and_reader_failure_never_return_document(self):
        for fixture,status in (({'status':401},'login_required'),({'redirected':True},'unavailable'),
                ({'url':'https://attacker.example/redirect'},'unavailable'),({'noBody':True},'unavailable'),
                ({'chunks':[]},'unavailable'),({'readError':True},'unavailable')):
            report=execute(fixture)
            self.assertEqual(report['value'],{'status':status})
            self.assertEqual(report['activeTimers'],0)

    def test_timeout_aborts_fetch_and_clears_timer(self):
        report=execute({'hang':True})
        self.assertEqual(report['value'],{'status':'unavailable'})
        self.assertTrue(report['aborted']);self.assertEqual(report['activeTimers'],0)

    def test_placeholder_words_in_observed_filename_are_not_rewritten(self):
        url='https://www.b2b-center.ru/documents/__MAX__-__TIMEOUT__.docx'
        report=execute({'chunks':[[1]]},url=url)
        self.assertEqual(report['requested'],url);self.assertEqual(report['value']['url'],url)


if __name__=='__main__':unittest.main()
