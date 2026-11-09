// Existing batch transport has its own integration suite; this suite exercises the actual return hook.
jest.mock('./useWarehouseBatchDraft',()=>()=>({loading:false,saving:false,dirty:false,error:'',phase:'ready',readyToSubmit:true,flush:async()=>undefined,clear:()=>{},rejectConflict:()=>{}}));
import React from 'react';
import {act,fireEvent,render,screen,waitFor,within} from '@testing-library/react';
import {DistributionWorkspace} from './WarehouseDistributionPanel';
const allocation={id:8,companyId:2,lotId:5,warehouseInvoiceId:10,projectId:11,projectName:'Школа',materialName:'Кабель',unit:'м',quantity:'4',returnedQuantity:'0',netQuantity:'4',returns:[]};
const props={user:{id:101},companyContext:{mode:'company',selectedCompanyId:2,companies:[{companyId:2,role:'директор'}]},projects:[{id:11,companyId:2,name:'Школа'}]};
const empty=()=>({allocationId:null,quantity:'',reason:''});
const ok=(data,status=200)=>({ok:status<400,status,json:async()=>data});
const originalCrypto=global.crypto;
beforeAll(()=>Object.defineProperty(global,'crypto',{configurable:true,value:require('crypto').webcrypto}));
afterAll(()=>Object.defineProperty(global,'crypto',{configurable:true,value:originalCrypto}));
let nextUser=100,server,writes,commands,operations,loseSave,loseReturn,history,fetcher;
beforeEach(()=>{
 props.user={id:nextUser++};sessionStorage.clear();writes=[];commands=[];operations=new Map();loseSave=false;loseReturn=false;history=[allocation];
 server={companyId:2,userId:props.user.id,revision:0,document:empty(),source:null,lastOperation:null};
 fetcher=jest.fn(async(url,options={})=>{
  const path=new URL(url,'http://localhost').pathname;
  if(path.endsWith('/return-draft')){
   if(options.method==='PUT'){
    const body=JSON.parse(options.body);writes.push(body);
    if(server.lastSave===body.requestId&&server.revision===body.expectedRevision+1)return ok(JSON.parse(JSON.stringify(server)));
    if(body.expectedRevision!==server.revision)return ok({detail:{code:'warehouse_return_draft_conflict',message:'Черновик возврата изменён в другой вкладке'}},409);
    server={...server,revision:server.revision+1,document:body.document,lastSave:body.requestId,source:body.document.allocationId?allocation:null};
    if(loseSave){loseSave=false;throw Error('Ответ сохранения потерян');}
   }
   return ok(JSON.parse(JSON.stringify(server)));
  }
  if(options.method==='POST'&&path.endsWith('/returns')){
   const body=JSON.parse(options.body);commands.push(options);let result=operations.get(body.requestId);
   if(!result){
    if(Number(options.headers['X-Warehouse-Return-Draft-Revision'])!==server.revision)return ok({detail:{code:'warehouse_return_draft_conflict',message:'Черновик возврата изменён в другой вкладке'}},409);
    result={ok:true,requestId:body.requestId,operationId:20,item:{...allocation,returnedQuantity:body.quantity}};operations.set(body.requestId,result);
    server={...server,revision:server.revision+1,document:empty(),source:null,lastSave:null,lastOperation:{requestId:body.requestId,operationId:20}};
   }
   if(loseReturn){loseReturn=false;throw Error('Ответ возврата потерян');}
   return ok(result);
  }
  return ok({items:path.endsWith('/sources')||path.endsWith('/transfers')?[]:history,nextCursor:null,truncated:false});
 });global.fetch=fetcher;
});
async function fill(root=screen){
 await waitFor(()=>expect(root.getByRole('button',{name:'Оформить возврат',exact:true})).toBeEnabled());
 fireEvent.click(root.getByRole('button',{name:'Оформить возврат',exact:true}));
 fireEvent.change(root.getByLabelText('Количество возврата'),{target:{value:'1.'}});
 fireEvent.change(root.getByLabelText('Основание возврата'),{target:{value:'Для другого устройства'}});
 fireEvent.click(root.getByLabelText(/Подтверждаю фактический возврат/));
}
test('return draft survives another device and requires a fresh physical confirmation',async()=>{
 const first=render(<DistributionWorkspace {...props}/>);await fill();
 await waitFor(()=>expect(server.document.quantity).toBe('1.'));
 first.unmount();sessionStorage.clear();render(<DistributionWorkspace {...props}/>);
 await waitFor(()=>expect(screen.getByLabelText('Количество возврата')).toHaveValue('1.'));
 expect(screen.getByLabelText('Основание возврата')).toHaveValue('Для другого устройства');
 expect(screen.getByLabelText(/Подтверждаю фактический возврат/)).not.toBeChecked();
 expect(screen.getByRole('button',{name:'Подтвердить возврат',exact:true})).toBeDisabled();expect(commands).toHaveLength(0);
});
test('two editors preserve local return input on conflict without automatic overwrite',async()=>{
 const a=render(<DistributionWorkspace {...props}/>),b=render(<DistributionWorkspace {...props}/>);
 await fill(within(a.container));await waitFor(()=>expect(server.revision).toBe(1));
 await fill(within(b.container));await within(b.container).findByText('Черновик возврата изменён в другой вкладке');
 const n=writes.length;await act(async()=>new Promise(r=>setTimeout(r,500)));
 expect(writes).toHaveLength(n);expect(within(b.container).getByLabelText('Количество возврата')).toHaveValue('1.');
});
async function valid(){await fill();fireEvent.change(screen.getByLabelText('Количество возврата'),{target:{value:'1'}});}
const submit=()=>fireEvent.click(screen.getByRole('button',{name:'Подтвердить возврат',exact:true}));
test('lost return response retries the exact command and revision once',async()=>{
 render(<DistributionWorkspace {...props}/>);await valid();loseReturn=true;submit();
 await screen.findByText(/Ответ возврата потерян/);
 fireEvent.click(screen.getByRole('button',{name:'Повторить неподтверждённую операцию',exact:true}));
 await screen.findByText(/Предыдущий возврат сохранён/);
 expect(commands).toHaveLength(2);expect(commands[1].body).toBe(commands[0].body);
 expect(commands[1].headers['X-Warehouse-Return-Draft-Revision']).toBe(commands[0].headers['X-Warehouse-Return-Draft-Revision']);
 expect(operations.size).toBe(1);expect(screen.queryByLabelText('Количество возврата')).not.toBeInTheDocument();
});
test('completed return is not repeated after opening on another device',async()=>{
 const first=render(<DistributionWorkspace {...props}/>);await valid();loseReturn=true;submit();
 await screen.findByText(/Ответ возврата потерян/);first.unmount();sessionStorage.clear();render(<DistributionWorkspace {...props}/>);
 await screen.findByText(/Предыдущий возврат сохранён/);
 expect(commands).toHaveLength(1);expect(screen.queryByLabelText('Количество возврата')).not.toBeInTheDocument();
});
test('an issue conflict keeps local return data and disables submission',async()=>{
 render(<DistributionWorkspace {...props}/>);await valid();await waitFor(()=>expect(server.revision).toBe(1));server.revision=2;submit();
 await screen.findByText('Загрузить серверный возврат');
 expect(screen.getByLabelText('Количество возврата')).toHaveValue('1');
 expect(screen.getByRole('button',{name:'Подтвердить возврат',exact:true})).toBeDisabled();expect(operations.size).toBe(0);
});
test('lost save retries its mutation before applying newer edits',async()=>{
 render(<DistributionWorkspace {...props}/>);loseSave=true;await fill();await screen.findByText('Ответ сохранения потерян');
 fireEvent.change(screen.getByLabelText('Количество возврата'),{target:{value:'2'}});
 fireEvent.click(screen.getByRole('button',{name:'Сохранить черновик возврата',exact:true}));
 await waitFor(()=>expect(server.document.quantity).toBe('2'));expect(writes).toHaveLength(3);expect(writes[1]).toEqual(writes[0]);
});
test('navigation recovery retains partial input and does not restore physical confirmation',async()=>{
 const first=render(<DistributionWorkspace {...props}/>);await fill();first.unmount();expect(server.revision).toBe(0);
 render(<DistributionWorkspace {...props}/>);await waitFor(()=>expect(screen.getByLabelText('Количество возврата')).toHaveValue('1.'));
 expect(screen.getByLabelText(/Подтверждаю фактический возврат/)).not.toBeChecked();
 await waitFor(()=>expect(server.document.quantity).toBe('1.'));
});
test('a saved return without fresh history remains visible but cannot be posted',async()=>{
 const first=render(<DistributionWorkspace {...props}/>);await valid();await waitFor(()=>expect(server.revision).toBe(1));first.unmount();history=[];
 render(<DistributionWorkspace {...props}/>);await waitFor(()=>expect(screen.getByLabelText('Количество возврата')).toHaveValue('1'));
 fireEvent.click(screen.getByLabelText(/Подтверждаю фактический возврат/));
 expect(screen.getByRole('button',{name:'Подтвердить возврат',exact:true})).toBeDisabled();expect(commands).toHaveLength(0);
});
test('explicit cancellation clears only the personal return draft',async()=>{
 render(<DistributionWorkspace {...props}/>);await fill();await waitFor(()=>expect(server.revision).toBe(1));
 fireEvent.click(screen.getByRole('button',{name:'Отмена',exact:true}));await waitFor(()=>expect(server.document).toEqual(empty()));
 expect(server.revision).toBe(2);expect(commands).toHaveLength(0);
});
test('foreign source data is rejected even if the envelope matches',async()=>{
 server={...server,revision:1,document:{allocationId:8,quantity:'1',reason:'foreign'},source:{...allocation,companyId:3}};
 render(<DistributionWorkspace {...props}/>);await screen.findByText(/Сервер не подтвердил черновик возврата/);
 expect(screen.queryByDisplayValue('foreign')).not.toBeInTheDocument();expect(commands).toHaveLength(0);
});
