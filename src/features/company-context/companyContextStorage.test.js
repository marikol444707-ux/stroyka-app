import { withStoredCompanyContextHeaders } from './companyContextStorage';
const storage={getItem:key=>key==='user'?JSON.stringify({id:9}):JSON.stringify({mode:'company',companyId:2})};

test('current company supplies headers only when a request has no explicit owner',()=>{
 const result=withStoredCompanyContextHeaders({},storage);
 expect(result.headers.get('X-Company-Id')).toBe('2');
 expect(result.headers.get('X-Company-Mode')).toBe('company');
});
test('a captured form owner survives switching the selected company',()=>{
 const result=withStoredCompanyContextHeaders({headers:{'X-Company-Id':'1','X-Company-Mode':'company','Content-Type':'application/json'}},storage);
 expect(result.headers.get('X-Company-Id')).toBe('1');
 expect(result.headers.get('Content-Type')).toBe('application/json');
});
test('explicit aggregate reads are not replaced by the selected company',()=>{
 const result=withStoredCompanyContextHeaders({headers:{'X-Company-Mode':'all_companies'}},storage);
 expect(result.headers.get('X-Company-Mode')).toBe('all_companies');
 expect(result.headers.has('X-Company-Id')).toBe(false);
});
