import { submitAllocation, readAllocationPending } from './allocationClient';
const scope={API:'/api',userId:7,companyId:2,invoiceId:12};
const context={companyId:2,invoiceId:12,groupId:8,version:0,payments:[{paymentId:10,amount:'120.00',refundedAmount:'0.00',remainingAmount:'120.00',allocatedAmount:'0.00',unallocatedAmount:'120.00'}],receipts:[{receiptId:30,warehouseId:40,amount:'100.00',allocated:'0.00',remaining:'100.00'},{receiptId:31,warehouseId:41,amount:'100.00',allocated:'0.00',remaining:'100.00'}],allocations:[]};
const draft={reason:'По двум приёмкам',rows:[{paymentId:10,receiptId:30,amount:'80'},{paymentId:10,receiptId:31,amount:'20'}]};
const uuid=()=> '12345678-1234-4234-8234-123456789abc';
const locks={request:(key,opts,fn)=>fn({name:key})};
const result={companyId:2,requestId:uuid(),groupId:8,version:1,revisionId:12};
const response=data=>({ok:true,json:async()=>data});
const send=extra=>submitAllocation({scope,context,draft,uuid,locks,...extra});
beforeEach(()=>localStorage.clear());
test('saves exact full revision before send and clears only matched confirmation',async()=>{
 const fetcher=jest.fn(async()=>{expect(readAllocationPending(scope).body.rows[0].amount).toBe('80.00');return response(result);});
 expect(await send({fetcher})).toEqual(result);expect(readAllocationPending(scope)).toBeNull();
 expect(fetcher.mock.calls[0][1].headers['X-Company-Id']).toBe('2');
});
test('lost response persists across reload and repeats exact UUID and rows',async()=>{
 await expect(send({fetcher:async()=>{throw new TypeError('offline');}})).rejects.toThrow();
 const saved=readAllocationPending(scope),fetcher=jest.fn(async()=>response(result));
 await submitAllocation({scope,expectedPending:saved,locks,fetcher});
 expect(JSON.parse(fetcher.mock.calls[0][1].body)).toEqual(saved.body);
});
test.each([[[10,30,'101']],[[10,30,'80'],[10,31,'50']],[[99,30,'1']],[[10,30,'1.001']],[[10,30,'1'],[10,30,'2']]].map(rows=>[rows]))('rejects invalid revision %j',async rows=>{
 const fetcher=jest.fn();await expect(send({fetcher,draft:{...draft,rows:rows.map(([paymentId,receiptId,amount])=>({paymentId,receiptId,amount}))}})).rejects.toThrow();expect(fetcher).not.toHaveBeenCalled();
});
test('foreign confirmation or generic conflict retains saved intent',async()=>{
 await expect(send({fetcher:async()=>response({...result,groupId:99})})).rejects.toThrow();
 const saved=readAllocationPending(scope);
 await expect(submitAllocation({scope,expectedPending:saved,locks,fetcher:async()=>({ok:false,status:409,json:async()=>({detail:'Conflict'})})})).rejects.toThrow();
 expect(readAllocationPending(scope)).toEqual(saved);expect(readAllocationPending({...scope,companyId:3})).toBeNull();
});
test('only scoped server confirmation of non-save releases a stale attempt',async()=>{
 await expect(send({fetcher:async()=>({ok:false,status:409,json:async()=>({detail:{code:'allocation_not_saved',companyId:2,groupId:8,requestId:uuid(),message:'Обновите данные'}})})})).rejects.toThrow('Обновите');
 expect(readAllocationPending(scope)).toBeNull();
});
test('missing lock or unwritable storage never sends',async()=>{
 const fetcher=jest.fn();await expect(send({locks:null,fetcher})).rejects.toThrow();
 await expect(send({fetcher,storage:{getItem:()=>null,setItem:()=>{throw new Error('storage');}}})).rejects.toThrow();expect(fetcher).not.toHaveBeenCalled();
});
