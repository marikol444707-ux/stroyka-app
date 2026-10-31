import { recordLegacyPayment } from './legacyInvoicePayment';
const command={requestId:'11111111-1111-4111-8111-111111111111',companyId:2,invoiceId:4,amount:'10.00',expectedPaidAmount:'0.00',paidAt:'2026-10-31'};
const data={ok:true,requestId:command.requestId,companyId:2,invoiceId:4,projectPaymentId:8};
const response=value=>({ok:true,json:async()=>value});
beforeEach(()=>localStorage.clear());
it('uses one atomic command with company headers and keeps identity until refresh',async()=>{
 const fetchFn=jest.fn(async()=>response(data));
 const result=await recordLegacyPayment({api:'/api',key:'key',storage:localStorage,command,fetchFn});
 expect(fetchFn).toHaveBeenCalledTimes(1);
 expect(fetchFn.mock.calls[0][0]).toBe('/api/supplier-invoices/4/legacy-payments');
 expect(fetchFn.mock.calls[0][1].headers['X-Company-Id']).toBe('2');
 expect(localStorage.getItem('key')).not.toBeNull();result.clear();expect(localStorage.getItem('key')).toBeNull();
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
 localStorage.setItem('key','another');result.clear();expect(localStorage.getItem('key')).toBe('another');
});
