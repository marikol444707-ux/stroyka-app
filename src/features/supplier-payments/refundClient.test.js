import { readRefundPending, submitRefund, refundContext, cancelRefund } from './refundClient';
const scope={API:'/api',userId:7,companyId:2,invoiceId:12};
const uuid=()=> '12345678-1234-4234-8234-123456789abc';
const context={companyId:2,invoiceId:12,groupId:8,version:1,payments:[{paymentId:10,amount:'100.00',refundedAmount:'0.00',remainingAmount:'100.00',allocatedAmount:'80.00',unallocatedAmount:'20.00'}],
  receipts:[{receiptId:30,warehouseId:40,amount:'100.00',allocated:'80.00',remaining:'20.00'}],allocations:[{paymentId:10,receiptId:30,amount:'80.00'}]};
const draft={paymentId:10,amount:'25',unallocatedAmount:'5',paidAt:'2026-09-28',reason:'Выписка',releases:[{receiptId:30,amount:'20'}]};
const result={companyId:2,requestId:uuid(),groupId:8,paymentId:10,version:2,revisionId:2,operationId:50,projectPaymentId:60,kind:'refund',amount:'25.00'};
const locks={request:(key,opts,fn)=>fn({name:key})};
const response=data=>({ok:true,json:async()=>data});
beforeEach(()=>{localStorage.clear();jest.clearAllMocks();});
const send=extra=>submitRefund({scope,context,draft,uuid,locks,...extra});
test('persists exact command before fetch, validates response and clears',async()=>{
  const fetcher=jest.fn(async()=>{expect(readRefundPending(scope).body.amount).toBe('25.00');return response(result);});
  expect(await send({fetcher})).toEqual(result);
  const init=fetcher.mock.calls[0][1];expect(init.headers['X-Company-Id']).toBe('2');
  expect(JSON.parse(init.body)).toEqual({requestId:uuid(),groupId:8,expectedVersion:1,...draft,amount:'25.00',unallocatedAmount:'5.00',releases:[{receiptId:30,amount:'20.00'}]});
  expect(readRefundPending(scope)).toBeNull();
});
test('connection loss and 409 keep exact request for retry or server cancellation',async()=>{
  await expect(send({fetcher:async()=>{throw new TypeError('offline');}})).rejects.toThrow();
  const saved=readRefundPending(scope);
  await expect(submitRefund({scope,expectedPending:saved,locks,fetcher:async()=>({ok:false,status:409,json:async()=>({detail:'Conflict'})})})).rejects.toThrow('Conflict');
  expect(readRefundPending(scope)).toEqual(saved);
  const fetcher=jest.fn(async()=>response(result));
  await submitRefund({scope,expectedPending:saved,locks,fetcher});
  expect(JSON.parse(fetcher.mock.calls[0][1].body)).toEqual(saved.body);
});
test('wrong result scope preserves pending',async()=>{
  await expect(send({fetcher:async()=>response({...result,companyId:3})})).rejects.toThrow();
  expect(readRefundPending(scope)).not.toBeNull();
  expect(readRefundPending({...scope,companyId:3})).toBeNull();
  expect(readRefundPending({...scope,API:'/other'})).toBeNull();
});
test('rejects overrelease, free capacity and sum mismatches before send',async()=>{
  for(const change of [{amount:'90',unallocatedAmount:'5',releases:[{receiptId:30,amount:'85'}]}, {amount:'21',unallocatedAmount:'21',releases:[]}, {amount:'26'}, {amount:'0.001'}]){
    const fetcher=jest.fn();await expect(send({draft:{...draft,...change},fetcher})).rejects.toThrow();expect(fetcher).not.toHaveBeenCalled();
  }
});
test('corrupt or unavailable storage and missing lock fail closed',async()=>{
  const fetcher=jest.fn();await expect(send({fetcher,storage:{getItem:()=>'{bad'}})).rejects.toThrow();
  await expect(send({fetcher,locks:null})).rejects.toThrow();expect(fetcher).not.toHaveBeenCalled();
});
test('read context must match selected invoice',async()=>{
  await expect(refundContext(scope,{fetcher:async()=>response({...context,invoiceId:99})})).rejects.toThrow();
});
test('server cancellation retains cancel intent until confirmed',async()=>{
  await expect(send({fetcher:async()=>{throw new Error('offline');}})).rejects.toThrow();
  let saved=readRefundPending(scope);
  await expect(cancelRefund({scope,expectedPending:saved,locks,fetcher:async()=>{throw new Error('offline');}})).rejects.toThrow();
  saved=readRefundPending(scope);expect(saved.cancelRequested).toBe(true);
  await expect(submitRefund({scope,expectedPending:saved,locks,fetcher:jest.fn()})).rejects.toThrow();
  const fetcher=jest.fn(async()=>response({status:'cancelled',companyId:2,requestId:uuid(),documentKind:'invoice',documentId:12,kind:'refund'}));
  await cancelRefund({scope,expectedPending:saved,locks,fetcher});
  expect(JSON.parse(fetcher.mock.calls[0][1].body)).toEqual({requestId:uuid(),kind:'refund',documentKind:'invoice',documentId:12,amount:'25.00',paidAt:draft.paidAt,reason:draft.reason});
  expect(readRefundPending(scope)).toBeNull();
});
