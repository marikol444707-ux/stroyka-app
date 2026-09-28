import {createLegacyLineReviewClient} from './legacyLineReviewClient';
const scope={API:'',userId:7,companyId:2,invoiceId:3};
const body={requestId:'test-id',confirmed:true,lines:[{}]};
const reply=(data,status=200)=>({ok:status<400,status,json:async()=>data});
let storage,fetcher,locks;
beforeEach(()=>{const map=new Map();storage={getItem:k=>map.get(k)||null,setItem:(k,v)=>map.set(k,v),removeItem:k=>map.delete(k)};fetcher=jest.fn();locks={request:async(k,o,fn)=>fn({})};});
const client=()=>createLegacyLineReviewClient(scope,{storage,fetcher,locks});
test('persists before send and retries the exact command after lost response',async()=>{
 fetcher.mockImplementationOnce(async()=>{expect(client().pending()).toEqual(body);throw new Error('Network');})
 .mockResolvedValueOnce(reply({companyId:2,invoiceId:3,requestId:'test-id',reviewed:true,specId:9}));
 await expect(client().save(body)).rejects.toThrow();await client().save(client().pending());
 expect(fetcher.mock.calls[0][1].body).toBe(fetcher.mock.calls[1][1].body);expect(client().pending()).toBeNull();
});
test('only matching scoped non-save releases persisted intent',async()=>{
 fetcher.mockResolvedValueOnce(reply({detail:{code:'legacy_line_review_not_saved',companyId:99,invoiceId:3,requestId:'test-id'}},409))
 .mockResolvedValueOnce(reply({detail:{code:'legacy_line_review_not_saved',companyId:2,invoiceId:3,requestId:'test-id'}},409));
 await expect(client().save(body)).rejects.toThrow();expect(client().pending()).toEqual(body);
 await expect(client().save(body)).rejects.toThrow();expect(client().pending()).toBeNull();
});
test('foreign success and edited retry cannot discard uncertain command',async()=>{
 fetcher.mockResolvedValue(reply({companyId:99,invoiceId:3,requestId:'test-id',reviewed:true,specId:9}));
 await expect(client().save(body)).rejects.toThrow();fetcher.mockClear();
 await expect(client().save({...body,reason:'changed'})).rejects.toThrow();expect(fetcher).not.toHaveBeenCalled();expect(client().pending()).toEqual(body);
});
