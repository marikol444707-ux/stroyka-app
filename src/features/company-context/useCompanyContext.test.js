import {act, renderHook} from '@testing-library/react';
import {useCompanyContext} from './useCompanyContext';

const initialFlag=process.env.REACT_APP_PARTICIPANT_SUPPORT_ACCESS_ENABLED;
const originalFetch=global.fetch;
const company=(id)=>({defaultCompanyId:id,companies:[{companyId:id,name:'Synthetic company'}]});
const response=(body)=>({ok:true,json:async()=>body});
beforeEach(()=>{localStorage.clear();process.env.REACT_APP_PARTICIPANT_SUPPORT_ACCESS_ENABLED='1';});
afterEach(()=>{global.fetch=originalFetch;if(initialFlag===undefined)delete process.env.REACT_APP_PARTICIPANT_SUPPORT_ACCESS_ENABLED;else process.env.REACT_APP_PARTICIPANT_SUPPORT_ACCESS_ENABLED=initialFlag;});

test('dedicated support workspace has no buyer company request or selection',async()=>{
  global.fetch=jest.fn(async()=>response(company(2)));
  const user={id:12,role:'platform_support'};
  const {result}=renderHook(()=>useCompanyContext({API:'/api',user}));
  await act(async()=>{await result.current.refresh();});
  expect(fetch).not.toHaveBeenCalled();expect(result.current.companies).toEqual([]);
  expect(result.current.selectedCompanyId).toBeNull();expect(result.current.loading).toBe(false);
});
test('switching actors aborts and ignores a late previous company response',async()=>{
  let late;let oldSignal;
  global.fetch=jest.fn((_url,options)=>{oldSignal=options.signal;return new Promise(resolve=>{late=resolve;});});
  const {result,rerender}=renderHook(({user})=>useCompanyContext({API:'/api',user}),{initialProps:{user:{id:7,role:'директор'}}});
  rerender({user:{id:12,role:'platform_support'}});
  await act(async()=>{late(response(company(2)));});
  expect(oldSignal.aborted).toBe(true);expect(fetch).toHaveBeenCalledTimes(1);
  expect(result.current.context).toBeNull();expect(result.current.selectedCompanyId).toBeNull();
  expect(localStorage.length).toBe(0);
});
test('latest refresh wins even if an aborted older fetch resolves',async()=>{
  const pending=[];global.fetch=jest.fn(()=>new Promise(resolve=>pending.push(resolve)));
  const user={id:7,role:'директор'};
  const {result}=renderHook(()=>useCompanyContext({API:'/api',user}));
  // Keep the actor object stable: a refresh is not a new login.
  let refreshing;act(()=>{refreshing=result.current.refresh();});
  await act(async()=>{pending[1](response(company(3)));await refreshing;});
  await act(async()=>{pending[0](response(company(2)));});
  expect(result.current.selectedCompanyId).toBe(3);
});
test('feature off keeps existing support company context',async()=>{
  process.env.REACT_APP_PARTICIPANT_SUPPORT_ACCESS_ENABLED='0';
  const user={id:12,role:'platform_support'};global.fetch=jest.fn(async()=>response(company(2)));
  const {result}=renderHook(()=>useCompanyContext({API:'/api',user}));
  await act(async()=>{});expect(result.current.selectedCompanyId).toBe(2);expect(fetch).toHaveBeenCalledTimes(1);
});
test('ordinary actor change hides the loaded company while the new context is loading',async()=>{
  let nextReply;global.fetch=jest.fn().mockResolvedValueOnce(response(company(2))).mockImplementationOnce(()=>new Promise(resolve=>{nextReply=resolve;}));
  const {result,rerender}=renderHook(({user})=>useCompanyContext({API:'/api',user}),{initialProps:{user:{id:7,role:'директор'}}});
  await act(async()=>{});expect(result.current.selectedCompanyId).toBe(2);
  rerender({user:{id:8,role:'бухгалтер'}});
  expect(result.current.context).toBeNull();expect(result.current.selectedCompanyId).toBeNull();
  await act(async()=>nextReply(response(company(3))));expect(result.current.selectedCompanyId).toBe(3);
  rerender({user:null});expect(result.current.context).toBeNull();expect(result.current.companies).toEqual([]);
});
test('refresh preserves the selected company if browser storage is unavailable',async()=>{
  const body={defaultCompanyId:2,companies:[{companyId:2},{companyId:3}]};
  const user={id:7,role:'директор'};global.fetch=jest.fn(async()=>response(body));
  const storage=jest.spyOn(Storage.prototype,'setItem').mockImplementation(()=>{throw new Error('Storage unavailable');});
  try {
    const {result}=renderHook(()=>useCompanyContext({API:'/api',user}));
    await act(async()=>{});
    act(()=>result.current.setSelectedCompanyId(3));expect(result.current.selectedCompanyId).toBe(3);
    await act(async()=>{await result.current.refresh();});expect(result.current.selectedCompanyId).toBe(3);
  } finally {storage.mockRestore();}
});
