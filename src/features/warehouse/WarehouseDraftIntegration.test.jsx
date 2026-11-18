import React from 'react';
import {act,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {DistributionWorkspace} from './WarehouseDistributionPanel';
const allocation={id:8,companyId:2,lotId:5,projectName:'Школа',materialName:'Кабель',unit:'м',quantity:'4',returnedQuantity:'0',netQuantity:'4',returns:[]};
const props={user:{id:400},companyContext:{mode:'company',selectedCompanyId:2,companies:[{companyId:2,role:'директор'}]},projects:[{id:11,companyId:2,name:'Школа'}]};
const originalCrypto=global.crypto;
beforeAll(()=>Object.defineProperty(global,'crypto',{configurable:true,value:require('crypto').webcrypto}));
afterAll(()=>Object.defineProperty(global,'crypto',{configurable:true,value:originalCrypto}));
const ok=data=>({ok:true,status:200,json:async()=>JSON.parse(JSON.stringify(data))});
test('batch and return drafts are loaded and saved independently in the real workspace',async()=>{
 sessionStorage.clear();
 let batch={companyId:2,userId:400,revision:4,document:{rows:[{lotId:5,projectId:11,quantity:'2'}],reason:'Выдача'},sources:[],lastOperation:null};
 let returned={companyId:2,userId:400,revision:6,document:{allocationId:8,quantity:'1.',reason:'Возврат'},source:allocation,lastOperation:null};
 const put=[];
 global.fetch=jest.fn(async(url,opts={})=>{
  const path=new URL(url,'http://localhost').pathname;
  if(path.endsWith('/return-draft')){
   if(opts.method==='PUT'){const body=JSON.parse(opts.body);put.push({path,body});returned={...returned,revision:returned.revision+1,document:body.document};}
   return ok(returned);
  }
  if(path.endsWith('/draft')){
   if(opts.method==='PUT'){const body=JSON.parse(opts.body);put.push({path,body});batch={...batch,revision:batch.revision+1,document:body.document};}
   return ok(batch);
  }
  return ok({items:path.endsWith('/sources')?[{lotId:5,materialName:'Кабель',unit:'м',availableQuantity:'10'}]:path.endsWith('/transfers')?[]:[allocation],nextCursor:null,truncated:false});
 });
 const editor=render(<DistributionWorkspace {...props}/>);
 await waitFor(()=>expect(screen.getByLabelText('Количество возврата')).toHaveValue('1.'));
 expect(screen.getByLabelText('Количество 1')).toHaveValue('2');expect(put).toHaveLength(0);
 expect(screen.getByLabelText(/Подтверждаю фактический возврат/)).not.toBeChecked();
 fireEvent.change(screen.getByLabelText('Количество возврата'),{target:{value:'1'}});
 fireEvent.click(screen.getByRole('button',{name:'Сохранить черновик возврата',exact:true}));
 await waitFor(()=>expect(returned.revision).toBe(7));expect(batch.revision).toBe(4);expect(batch.document.reason).toBe('Выдача');
 fireEvent.click(screen.getByRole('button',{name:'Отмена',exact:true}));await waitFor(()=>expect(returned.document.allocationId).toBeNull());
 fireEvent.change(screen.getByLabelText('Количество 1'),{target:{value:'3'}});
 fireEvent.click(screen.getByRole('button',{name:'Сохранить черновик',exact:true}));await waitFor(()=>expect(batch.revision).toBe(5));
 expect(returned.revision).toBe(8);expect(put.map(p=>p.body.expectedRevision)).toEqual([6,7,4]);
 editor.unmount();render(<DistributionWorkspace {...props}/>);
 await waitFor(()=>expect(screen.getByLabelText('Количество 1')).toHaveValue('3'));
 expect(screen.queryByLabelText('Количество возврата')).not.toBeInTheDocument();
});
test('loading return draft prevents opening another return or issuing a batch',async()=>{
 sessionStorage.clear();let resolve;
 global.fetch=jest.fn(async(url)=>{
  const path=new URL(url,'http://localhost').pathname;
  if(path.endsWith('/return-draft'))return new Promise(r=>{resolve=r;});
  if(path.endsWith('/draft'))return ok({companyId:2,userId:400,revision:0,document:{rows:[{lotId:null,projectId:null,quantity:''}],reason:''},sources:[],lastOperation:null});
  return ok({items:path.endsWith('/sources')||path.endsWith('/transfers')?[]:[allocation],nextCursor:null,truncated:false});
 });
 render(<DistributionWorkspace {...props}/>);await screen.findByRole('button',{name:'Оформить возврат',exact:true});
 expect(screen.getByRole('button',{name:'Оформить возврат',exact:true})).toBeDisabled();
 expect(screen.getByRole('button',{name:'Распределить одним пакетом',exact:true})).toBeDisabled();
 await act(async()=>resolve(ok({companyId:2,userId:400,revision:0,document:{allocationId:null,quantity:'',reason:''},source:null,lastOperation:null})));
 await waitFor(()=>expect(screen.getByRole('button',{name:'Оформить возврат',exact:true})).toBeEnabled());
});
