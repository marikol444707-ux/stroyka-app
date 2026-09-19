import React from 'react';
import {renderHook,waitFor,act} from '@testing-library/react';
import useSupplierTeam from './useSupplierTeam';
const originalFetch=global.fetch;
afterEach(()=>{global.fetch=originalFetch;});
it('loads in StrictMode and drops the prior user context on user switch',async()=>{
 let owner=7;
 global.fetch=jest.fn(async path=>({ok:true,json:async()=>path.endsWith('/customers')?[{id:owner,name:'Заказчик'}]:[{id:owner,name:'Поставщик',role:'manager'}]}));
 const {result,rerender}=renderHook(({user})=>useSupplierTeam('/api',user),{initialProps:{user:{id:1,role:'поставщик'}},wrapper:({children})=><React.StrictMode>{children}</React.StrictMode>});
 await waitFor(()=>expect(result.current.status).toBe('ready'));
 expect(result.current.suppliers[0].id).toBe(7);
 owner=8;rerender({user:{id:2,role:'поставщик'}});
 expect(result.current.suppliers).toEqual([]);
 await waitFor(()=>expect(result.current.status).toBe('ready'));
 expect(result.current.suppliers[0].id).toBe(8);
});
it('clears previously assigned customer names on authorization error',async()=>{
 let denied=false;
 global.fetch=jest.fn(async path=>({ok:!denied,status:denied?403:200,json:async()=>denied?{detail:'Доступ отозван'}:path.endsWith('/customers')?[{id:2,name:'PRIVATE CUSTOMER'}]:[{id:7,role:'manager'}]}));
 const {result}=renderHook(()=>useSupplierTeam('/api',{id:1,role:'поставщик'}));
 await waitFor(()=>expect(result.current.status).toBe('ready'));
 denied=true;await act(async()=>{await result.current.reload();});
 expect(result.current.status).toBe('error');expect(result.current.customers).toBeUndefined();expect(result.current.suppliers).toEqual([]);
});
