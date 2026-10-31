import { recordLegacyPayment, refreshLegacyPayment } from './legacyInvoicePayment';
const command={requestId:'11111111-1111-4111-8111-111111111111',companyId:2,invoiceId:4,amount:'10.00',expectedPaidAmount:'0.00',paidAt:'2026-10-31'};
const data={ok:true,requestId:command.requestId,companyId:2,invoiceId:4,projectPaymentId:8};
const response=value=>({ok:true,json:async()=>value});
beforeEach(()=>{localStorage.clear();Object.defineProperty(navigator,'locks',{configurable:true,value:{request:async(_key,_options,fn)=>fn({})}});});
afterEach(()=>{delete navigator.locks;});
it('uses one atomic command with company headers and keeps identity until refresh',async()=>{
 const fetchFn=jest.fn(async()=>response(data));
 const result=await recordLegacyPayment({api:'/api',key:'key',storage:localStorage,command,fetchFn});
 expect(fetchFn).toHaveBeenCalledTimes(1);
 expect(fetchFn.mock.calls[0][0]).toBe('/api/supplier-invoices/4/legacy-payments');
 expect(fetchFn.mock.calls[0][1].headers['X-Company-Id']).toBe('2');
 expect(localStorage.getItem('key')).not.toBeNull();await result.clear();expect(localStorage.getItem('key')).toBeNull();
});
it('network loss retains exact body and subsequent confirmation reuses it',async()=>{
 const fetchFn=jest.fn().mockRejectedValueOnce(new Error('lost')).mockResolvedValueOnce(response(data));
 await expect(recordLegacyPayment({api:'/api',key:'key',storage:localStorage,command,fetchFn})).rejects.toThrow('lost');
 await recordLegacyPayment({api:'/api',key:'key',storage:localStorage,command:{...command,requestId:'different'},fetchFn});
 expect(fetchFn.mock.calls[0][1].body).toBe(fetchFn.mock.calls[1][1].body);
});
it.each([['server failure',{ok:false,json:async()=>({detail:'rejected'})}],['invalid success',response({ok:true})],['wrong company',response({...data,companyId:3})]])('%s never clears pending',async(_,res)=>{
 await expect(recordLegacyPayment({api:'/api',key:'key',storage:localStorage,command,fetchFn:async()=>res})).rejects.toThrow();
 expect(JSON.parse(localStorage.getItem('key'))).toEqual(command);
});
it('storage failure never sends money command',async()=>{
 const fetchFn=jest.fn();const storage={getItem:()=>null,setItem:()=>{throw new Error('storage');}};
 await expect(recordLegacyPayment({api:'/api',key:'key',storage,command,fetchFn})).rejects.toThrow('storage');
 expect(fetchFn).not.toHaveBeenCalled();
});
it('corrupt identity fails closed',async()=>{
 localStorage.setItem('key','{}');const fetchFn=jest.fn();
 await expect(recordLegacyPayment({api:'/api',key:'key',storage:localStorage,command,fetchFn})).rejects.toThrow();
 expect(fetchFn).not.toHaveBeenCalled();
});
it('does not erase another tab pending command',async()=>{
 const result=await recordLegacyPayment({api:'/api',key:'key',storage:localStorage,command,fetchFn:async()=>response(data)});
 localStorage.setItem('key','another');await result.clear();expect(localStorage.getItem('key')).toBe('another');
});

it('fails closed when Web Locks is unsupported',async()=>{
 delete navigator.locks;const fetchFn=jest.fn();
 await expect(recordLegacyPayment({api:'/api',key:'key',storage:localStorage,command,fetchFn})).rejects.toThrow('блокировка');
 expect(fetchFn).not.toHaveBeenCalled();expect(localStorage.getItem('key')).toBeNull();
});
it('two simulated tabs cannot overwrite an in-flight attempt',async()=>{
 let held=false,finish;
 const locks={request:async(_key,_options,fn)=>{if(held)return fn(null);held=true;try{return await fn({});}finally{held=false;}}};
 const fetchFn=jest.fn(()=>new Promise(resolve=>{finish=resolve;}));
 const first=recordLegacyPayment({api:'/api',key:'key',storage:localStorage,command,fetchFn,locks});
 await expect(recordLegacyPayment({api:'/api',key:'key',storage:localStorage,command:{...command,requestId:'second'},fetchFn,locks})).rejects.toThrow('другой вкладке');
 expect(fetchFn).toHaveBeenCalledTimes(1);expect(JSON.parse(localStorage.getItem('key'))).toEqual(command);
 finish(response(data));const result=await first;await result.clear();
 expect(JSON.parse(localStorage.getItem(`key:attempt:${command.requestId}`))).toEqual(command);
});
it('never overwrites durable attempt with a different body',async()=>{
 localStorage.setItem(`key:attempt:${command.requestId}`,JSON.stringify({...command,amount:'99.00'}));
 const fetchFn=jest.fn();await expect(recordLegacyPayment({api:'/api',key:'key',storage:localStorage,command,fetchFn})).rejects.toThrow('другими данными');
 expect(fetchFn).not.toHaveBeenCalled();
});
it('strict refresh rejects HTTP failure without applying empty fallback',async()=>{
 const setInvoices=jest.fn();await expect(refreshLegacyPayment({api:'/api',confirmation:data,isCurrent:()=>true,setInvoices,fetchFn:async()=>({ok:false})})).rejects.toThrow();
 expect(setInvoices).not.toHaveBeenCalled();
});
it('strict refresh validates invoice and applies verified rows',async()=>{
 const rows=[{id:4,companyId:2,paidAmount:10}];const setInvoices=jest.fn();
 const result=await refreshLegacyPayment({api:'/api',confirmation:{...data,paidAmount:'10.00'},isCurrent:()=>true,setInvoices,fetchFn:async()=>response(rows)});
 expect(setInvoices).toHaveBeenCalledWith(rows);expect(result.requestId).toBe(data.requestId);
});
it('strict refresh ignores stale response',async()=>{
 let current=true;const setInvoices=jest.fn();
 await expect(refreshLegacyPayment({api:'/api',confirmation:{...data,paidAmount:'10'},isCurrent:()=>current,setInvoices,fetchFn:async()=>{current=false;return response([{id:4,companyId:2,paidAmount:10}]);}})).rejects.toThrow('Контекст');
 expect(setInvoices).not.toHaveBeenCalled();
});
it('context invalidation before lock grant sends no request',async()=>{
 const fetchFn=jest.fn();
 await expect(recordLegacyPayment({api:'/api',key:'key',storage:localStorage,command,fetchFn,isCurrent:()=>false})).rejects.toThrow('Контекст');
 expect(fetchFn).not.toHaveBeenCalled();expect(localStorage.getItem('key')).toBeNull();
});
