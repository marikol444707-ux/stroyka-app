// Return persistence is verified separately in WarehouseReturnPersistence.test.jsx.
jest.mock('./useWarehouseReturnDraft', () => () => ({ loading: false, saving: false, dirty: false, error: '', phase: 'ready', readyToSubmit: true, flush: async () => undefined, rejectConflict: () => {} }));
import React from 'react';
import { fireEvent, render, screen, waitFor, act, within } from '@testing-library/react';
import { DistributionWorkspace } from './WarehouseDistributionPanel';
const lot={lotId:5,warehouseInvoiceId:10,invoiceNumber:'DRAFT-10',invoiceLineIndex:0,materialName:'Кабель',unit:'м',availableQuantity:'10'};
const props={user:{id:1},companyContext:{mode:'company',selectedCompanyId:2,companies:[{companyId:2,role:'директор'}]},projects:[{id:11,companyId:2,name:'Объект'}]};
const empty=()=>({rows:[{lotId:null,projectId:null,quantity:''}],reason:''});
const ok=(data,status=200)=>({ok:status<400,status,json:async()=>data});
const originalCrypto=global.crypto;
beforeAll(()=>Object.defineProperty(global,'crypto',{configurable:true,value:require('crypto').webcrypto}));
afterAll(()=>Object.defineProperty(global,'crypto',{configurable:true,value:originalCrypto}));
let nextUser=100;
let server,writeBodies,fetcher,issues,loseIssueReply,loseSaveReply,sourceItems;
beforeEach(()=>{
 props.user={id:nextUser++};
 sessionStorage.clear();issues=new Map();loseIssueReply=false;loseSaveReply=false;sourceItems=[lot];server={companyId:2,userId:props.user.id,revision:0,document:empty(),sources:[],lastOperation:null};writeBodies=[];
 fetcher=jest.fn(async(url,options={})=>{
  const path=new URL(url,'http://localhost').pathname;
  if(path.endsWith('/draft')) {
   if(options.method==='PUT') {
    const body=JSON.parse(options.body);writeBodies.push(body);
    if(server.lastSave===body.requestId && server.revision===body.expectedRevision+1) return ok(JSON.parse(JSON.stringify(server)));
    if(body.expectedRevision!==server.revision)return ok({detail:'Черновик изменён в другой вкладке'},409);
    server={...server,revision:server.revision+1,lastSave:body.requestId,document:body.document,sources:[{...lot,availabilityUnknown:true}]};
    if(loseSaveReply){loseSaveReply=false;throw Error('Ответ сохранения потерян');}
   }
   return ok(JSON.parse(JSON.stringify(server)));
  }
  if(options.method==='POST' && path==='/warehouse-distributions') {
   const body=JSON.parse(options.body);let result=issues.get(body.requestId);
   if(!result) {
    if(Number(options.headers['X-Warehouse-Draft-Revision'])!==server.revision)return ok({detail:{code:'warehouse_draft_conflict',message:'Черновик изменён в другой вкладке'}},409);
    result={ok:true,requestId:body.requestId,operationId:20,items:[{id:10}]};issues.set(body.requestId,result);
    server={...server,revision:server.revision+1,document:empty(),lastSave:null,lastOperation:{requestId:body.requestId,operationId:20}};
   }
   if(loseIssueReply){loseIssueReply=false;throw Error('Ответ выдачи потерян');}
   return ok(result);
  }
  return ok({items:path.endsWith('/sources')?sourceItems:[],nextCursor:null,truncated:false});
 });global.fetch=fetcher;
});
async function fill(root=screen){
 await root.findByRole('option',{name:/DRAFT-10/});
 await waitFor(()=>expect(root.getByLabelText('Количество 1')).toBeEnabled());
 fireEvent.change(root.getByLabelText('Партия 1'),{target:{value:'5'}});
 fireEvent.change(root.getByLabelText('Объект 1'),{target:{value:'11'}});
 fireEvent.change(root.getByLabelText('Количество 1'),{target:{value:'2.'}});
 fireEvent.change(root.getByLabelText('Основание распределения'),{target:{value:'Черновик для другого устройства'}});
}
test('beforeunload warns while the current draft has not been acknowledged',async()=>{
 render(<DistributionWorkspace {...props}/>);await fill();
 const unsaved=new Event('beforeunload',{cancelable:true});window.dispatchEvent(unsaved);expect(unsaved.defaultPrevented).toBe(true);
 await waitFor(()=>expect(server.revision).toBe(1));
 await waitFor(()=>expect(screen.getByText('Черновик сохранён на сервере.')).toBeInTheDocument());
 const saved=new Event('beforeunload',{cancelable:true});window.dispatchEvent(saved);expect(saved.defaultPrevented).toBe(false);
});
test('saved partial draft survives a new device without browser storage',async()=>{
 const first=render(<DistributionWorkspace {...props}/>);await fill();
 await waitFor(()=>expect(server.document.reason).toBe('Черновик для другого устройства'));
 first.unmount();sessionStorage.clear();localStorage.clear();
 render(<DistributionWorkspace {...props}/>);
 await waitFor(()=>expect(screen.getByLabelText('Количество 1')).toHaveValue('2.'));
 expect(screen.getByLabelText('Партия 1')).toHaveValue('5');
 expect(screen.getByLabelText('Объект 1')).toHaveValue('11');
 expect(screen.getByLabelText('Основание распределения')).toHaveValue('Черновик для другого устройства');
 expect(fetcher.mock.calls.some(([,o])=>o?.method==='POST')).toBe(false);
});
test('two editors retain local edits on revision conflict without retrying over the server',async()=>{
 const a=render(<DistributionWorkspace {...props}/>),b=render(<DistributionWorkspace {...props}/>);
 await fill(within(a.container));
 await waitFor(()=>expect(server.revision).toBeGreaterThan(0));
 await fill(within(b.container));
 await within(b.container).findByText(/Черновик изменён в другой вкладке/);
 const attempts=writeBodies.length;
 expect(within(b.container).getByLabelText('Основание распределения')).toHaveValue('Черновик для другого устройства');
 await act(async()=>{await new Promise(r=>setTimeout(r,500));});
 expect(writeBodies).toHaveLength(attempts);
});

async function fillValid(){await fill();fireEvent.change(screen.getByLabelText('Количество 1'),{target:{value:'2'}});}
const submit=()=>fireEvent.click(screen.getByRole('button',{name:'Распределить одним пакетом'}));
test('committed issue survives closed tab with no second stock command on another device',async()=>{
 const first=render(<DistributionWorkspace {...props}/>);await fillValid();loseIssueReply=true;submit();
 await screen.findByText(/Ответ выдачи потерян/);expect(issues.size).toBe(1);
 first.unmount();sessionStorage.clear();localStorage.clear();render(<DistributionWorkspace {...props}/>);
 await screen.findByText(/Предыдущая выдача сохранена/);
 expect(screen.getByLabelText('Количество 1')).toHaveValue('');expect(issues.size).toBe(1);
 expect(fetcher.mock.calls.filter(([,o])=>o?.method==='POST')).toHaveLength(1);
});
test('lost issue reply retries exact request and draft revision then reloads server draft',async()=>{
 render(<DistributionWorkspace {...props}/>);await fillValid();loseIssueReply=true;submit();
 await screen.findByText(/Ответ выдачи потерян/);
 fireEvent.click(screen.getByText('Повторить неподтверждённую операцию'));
 await screen.findByText(/Операция сохранена/);
 const writes=fetcher.mock.calls.filter(([,o])=>o?.method==='POST');expect(writes).toHaveLength(2);
 expect(writes[1][1].body).toBe(writes[0][1].body);
 expect(writes[1][1].headers['X-Warehouse-Draft-Revision']).toBe(writes[0][1].headers['X-Warehouse-Draft-Revision']);
 expect(issues.size).toBe(1);expect(screen.getByLabelText('Количество 1')).toHaveValue('');
});
test('stale draft issue keeps input and exposes explicit conflict recovery',async()=>{
 render(<DistributionWorkspace {...props}/>);await fillValid();await waitFor(()=>expect(server.revision).toBe(1));
 server={...server,revision:2};submit();
 await screen.findByText('Загрузить серверный черновик');
 expect(screen.getByLabelText('Количество 1')).toHaveValue('2');
 expect(screen.getByRole('button',{name:'Распределить одним пакетом'})).toBeDisabled();
 expect(issues.size).toBe(0);
});
test('restored draft retains IDs but requires a fresh source before submission',async()=>{
 const first=render(<DistributionWorkspace {...props}/>);await fillValid();await waitFor(()=>expect(server.revision).toBe(1));
 first.unmount();sourceItems=[];render(<DistributionWorkspace {...props}/>);
 await waitFor(()=>expect(screen.getByLabelText('Количество 1')).toHaveValue('2'));
 expect(screen.getByLabelText('Партия 1')).toHaveValue('5');
 expect(screen.getByRole('button',{name:'Распределить одним пакетом'})).toBeDisabled();
});
test('unknown save result is retried with the same mutation before saving later edits',async()=>{
 render(<DistributionWorkspace {...props}/>);loseSaveReply=true;await fill();
 await screen.findByText('Ответ сохранения потерян');
 fireEvent.change(screen.getByLabelText('Количество 1'),{target:{value:'3'}});
 fireEvent.click(screen.getByRole('button',{name:'Сохранить черновик',exact:true}));
 await waitFor(()=>expect(server.document.rows[0].quantity).toBe('3'));
 expect(writeBodies).toHaveLength(3);expect(writeBodies[1]).toEqual(writeBodies[0]);
 expect(writeBodies[2].expectedRevision).toBe(1);
});
test('a response for another user is rejected without displaying their draft',async()=>{
 server={...server,userId:9,document:{...empty(),reason:'Foreign private draft'}};
 render(<DistributionWorkspace {...props}/>);
 await screen.findByText(/Сервер не подтвердил черновик пользователя/);
 expect(screen.queryByDisplayValue('Foreign private draft')).not.toBeInTheDocument();
 expect(screen.getByRole('button',{name:'Распределить одним пакетом'})).toBeDisabled();
});

test('leaving the section before autosave preserves local input on return',async()=>{
 const first=render(<DistributionWorkspace {...props}/>);await fill();
 first.unmount();expect(server.revision).toBe(0);
 const warning=new Event('beforeunload',{cancelable:true});window.dispatchEvent(warning);expect(warning.defaultPrevented).toBe(true);
 render(<DistributionWorkspace {...props}/>);
 await waitFor(()=>expect(screen.getByLabelText('Количество 1')).toHaveValue('2.'));
 await waitFor(()=>expect(server.document.reason).toBe('Черновик для другого устройства'));
});

test('unacknowledged navigation recovery cannot replace a newer device draft',async()=>{
 const first=render(<DistributionWorkspace {...props}/>);await fill();first.unmount();
 server={...server,revision:1,document:{...empty(),reason:'Другой компьютер'}};
 render(<DistributionWorkspace {...props}/>);
 await screen.findByText(/Серверный черновик изменился/);
 expect(screen.getByLabelText('Количество 1')).toHaveValue('2.');
 await act(async()=>{await new Promise(r=>setTimeout(r,500));});
 expect(writeBodies).toHaveLength(0);expect(server.document.reason).toBe('Другой компьютер');
});
test('a late load from the previous identity cannot hydrate a newly opened editor',async()=>{
 let finish;
 global.fetch=jest.fn((url,options)=>String(url).endsWith('/draft') && options?.method==='GET'
  ? new Promise(resolve=>{finish=resolve;}) : fetcher(url,options));
 const first=render(<DistributionWorkspace {...props}/>);await waitFor(()=>expect(finish).toBeDefined());
 const oldResponse=JSON.parse(JSON.stringify({...server,document:{...empty(),reason:'Старый ответ'}}));
 const oldFinish=finish;first.unmount();global.fetch=fetcher;
 props.user={id:nextUser++};server={...server,userId:props.user.id,document:{...empty(),reason:'Новый пользователь'}};
 render(<DistributionWorkspace {...props}/>);await screen.findByDisplayValue('Новый пользователь');
 await act(async()=>oldFinish(ok(oldResponse)));
 expect(screen.getByLabelText('Основание распределения')).toHaveValue('Новый пользователь');
 expect(screen.queryByDisplayValue('Старый ответ')).not.toBeInTheDocument();
});

test('revoked list access invalidates a pending draft load',async()=>{
 let finish;
 global.fetch=jest.fn(async(url,options)=>{
  if(String(url).endsWith('/draft'))return new Promise(resolve=>{finish=resolve;});
  return ok({detail:'Доступ отозван'},403);
 });
 render(<DistributionWorkspace {...props}/>);
 await screen.findByText('Доступ отозван');
 await act(async()=>finish(ok({...server,document:{...empty(),reason:'Скрытый черновик'}})));
 expect(screen.queryByDisplayValue('Скрытый черновик')).not.toBeInTheDocument();
 expect(screen.getByRole('button',{name:'Распределить одним пакетом'})).toBeDisabled();
});
