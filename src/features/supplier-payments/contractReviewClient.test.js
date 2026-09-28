import {createContractReviewClient} from './contractReviewClient';
const scope={API:'',userId:7,companyId:1,offerId:71};
const body={buyerCompanyId:1,payerCompanyId:1,expectedVersion:0,reason:'Проверено'};
const row={offerId:71,companyId:1,version:1,buyerCompanyId:1,payerCompanyId:1,reason:'Проверено'};
const response=(data,status=200)=>({ok:status<400,status,json:async()=>data});
let fetcher,storage,locks;
beforeEach(()=>{const values=new Map();storage={getItem:k=>values.get(k)||null,setItem:(k,v)=>values.set(k,v),removeItem:k=>values.delete(k)};
 fetcher=jest.fn();locks={request:async(k,o,fn)=>fn({name:k})};});
const client=()=>createContractReviewClient(scope,{fetcher,storage,locks});
test('writes scoped request only after persistent intent; clears verified result',async()=>{
 fetcher.mockImplementation(async()=>{expect(client().pending().body).toEqual(body);return response(row);});
 expect(await client().save('parties',body)).toEqual(row);expect(client().pending()).toBeNull();
 expect(fetcher.mock.calls[0][1].headers['X-Company-Id']).toBe('1');expect(fetcher.mock.calls[0][1].method).toBe('PUT');
});
test('lost response retries identical revision and reconciles stored version',async()=>{
 fetcher.mockRejectedValueOnce(new TypeError('Network')).mockResolvedValueOnce(response({detail:'Версия изменилась'},409)).mockResolvedValueOnce(response({items:[row]}));
 await expect(client().save('parties',body)).rejects.toThrow('Network');
 expect(await client().save('parties',client().pending().body)).toEqual(row);
 expect(JSON.parse(fetcher.mock.calls[0][1].body)).toEqual(JSON.parse(fetcher.mock.calls[1][1].body));expect(client().pending()).toBeNull();
});
test('different saved revision never silently counts as success',async()=>{
 fetcher.mockResolvedValueOnce(response({detail:'Конфликт'},409)).mockResolvedValueOnce(response({items:[{...row,payerCompanyId:2}]}));
 await expect(client().save('parties',body)).rejects.toThrow();expect(client().pending()).toBeNull();
});
test('foreign response, missing lock and storage failure do not clear intent',async()=>{
 fetcher.mockResolvedValue(response({...row,companyId:2}));await expect(client().save('parties',body)).rejects.toThrow();
 expect(client().pending()).not.toBeNull();fetcher.mockClear();
 await expect(createContractReviewClient(scope,{fetcher,storage,locks:null}).save('parties',body)).rejects.toThrow();expect(fetcher).not.toHaveBeenCalled();
 storage.setItem=()=>{throw new Error('Storage');};storage.removeItem=()=>{};
 await expect(createContractReviewClient({...scope,offerId:72},{fetcher,storage,locks}).save('parties',body)).rejects.toThrow();expect(fetcher).not.toHaveBeenCalled();
});
test('cannot overwrite an uncertain command with edited data',async()=>{
 fetcher.mockRejectedValue(new Error('Network'));await expect(client().save('parties',body)).rejects.toThrow();fetcher.mockClear();
 await expect(client().save('parties',{...body,reason:'Другое'})).rejects.toThrow();expect(fetcher).not.toHaveBeenCalled();
});

test('validation rejection on first attempt allows correcting fields',async()=>{
 fetcher.mockResolvedValueOnce(response({detail:'Неверные реквизиты'},422));
 await expect(client().save('parties',body)).rejects.toThrow();expect(client().pending()).toBeNull();
});
test('validation rejection after uncertain attempt retains original intent',async()=>{
 fetcher.mockRejectedValueOnce(new Error('Network')).mockResolvedValueOnce(response({detail:'Validation'},422));
 await expect(client().save('parties',body)).rejects.toThrow();
 await expect(client().save('parties',body)).rejects.toThrow();expect(client().pending()).not.toBeNull();
});
test('foreign conflict history cannot release pending intent',async()=>{
 fetcher.mockResolvedValueOnce(response({detail:'Конфликт'},409)).mockResolvedValueOnce(response({items:[{...row,companyId:2}]}));
 await expect(client().save('parties',body)).rejects.toThrow();expect(client().pending()).not.toBeNull();
});
