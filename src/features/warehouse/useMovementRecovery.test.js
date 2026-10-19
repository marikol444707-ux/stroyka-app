import {act,renderHook,waitFor} from '@testing-library/react';
import useMovementRecovery from './useMovementRecovery';
import useScopedMovementDraft from './useScopedMovementDraft';
const user={id:12};
const context=id=>({mode:'company',selectedCompanyId:id});
const answer=(id,drafts=[])=>({ok:true,json:async()=>({companyId:id,actorUserId:12,drafts})});
const pending=id=>({companyId:id,actorUserId:12,draftId:'abc',complete:false,commands:[]});
beforeEach(()=>{global.fetch=jest.fn(async()=>answer(2));});
test('reload discovers pending server draft and blocks new form',async()=>{
  fetch.mockResolvedValue(answer(2,[pending(2)]));
  const {result,unmount}=renderHook(()=>useMovementRecovery({API:'/api',user,companyContext:context(2)}));
  await waitFor(()=>expect(result.current.loading).toBe(false));
  expect(result.current.blocked).toBe(true);expect(result.current.drafts).toHaveLength(1);
  unmount();
  const again=renderHook(()=>useMovementRecovery({API:'/api',user,companyContext:context(2)}));
  await waitFor(()=>expect(again.result.current.drafts).toHaveLength(1));
});
test('captured refresh/cancel from old company cannot overwrite loaded new company',async()=>{
  fetch.mockImplementation(async(_url,options)=>answer(Number(options.headers['X-Company-Id'])));
  const {result,rerender}=renderHook(({id})=>useMovementRecovery({API:'/api',user,companyContext:context(id)}),{initialProps:{id:2}});
  await waitFor(()=>expect(result.current.loading).toBe(false));
  const stale=result.current;
  rerender({id:3});await waitFor(()=>expect(result.current.loading).toBe(false));
  const calls=fetch.mock.calls.length;
  await act(async()=>{await stale.refresh();await stale.cancel(pending(2));});
  expect(fetch).toHaveBeenCalledTimes(calls);expect(result.current.key).toBe('12:3');expect(result.current.loading).toBe(false);
});
test('old delayed response cannot leak across account switch or logout/relogin same account',async()=>{
  let finish;
  fetch.mockImplementationOnce(()=>new Promise(resolve=>{finish=resolve;}));
  const {result,rerender}=renderHook(({actor})=>useMovementRecovery({API:'/api',user:actor,companyContext:context(2)}),{initialProps:{actor:user}});
  const stale=result.current.refresh;
  rerender({actor:null});rerender({actor:user});
  await waitFor(()=>expect(result.current.loading).toBe(false));
  await act(async()=>{finish(answer(2,[pending(2)]));await stale();});
  expect(result.current.drafts).toEqual([]);expect(result.current.blocked).toBe(false);
});
test('request failure blocks new work until successful refresh',async()=>{
  fetch.mockRejectedValueOnce(new Error('offline'));
  const {result}=renderHook(()=>useMovementRecovery({API:'/api',user,companyContext:context(2)}));
  await waitFor(()=>expect(result.current.error).toBe('offline'));expect(result.current.blocked).toBe(true);
  await act(async()=>{await result.current.refresh();});expect(result.current.blocked).toBe(false);
});
test('cancel uses exact actor/company then reconciles server',async()=>{
  fetch.mockResolvedValueOnce(answer(2,[pending(2)]));
  const {result}=renderHook(()=>useMovementRecovery({API:'/api',user,companyContext:context(2)}));
  await waitFor(()=>expect(result.current.drafts).toHaveLength(1));
  fetch.mockResolvedValueOnce({ok:true,json:async()=>({...pending(2),complete:true})});
  await act(async()=>{await result.current.cancel(result.current.drafts[0]);});
  expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({expectedActorUserId:12});
  expect(fetch.mock.calls[1][0]).toBe('/api/warehouse-movement-drafts/abc/cancel');expect(result.current.blocked).toBe(false);
});
test('scoped form resets and rejects stale setters after company switch and logout',()=>{
  const {result,rerender}=renderHook(({actor,id})=>useScopedMovementDraft(actor,context(id)),{initialProps:{actor:user,id:2}});
  const stale=result.current.setNewMovement;
  act(()=>stale({notes:'private',selectedMaterials:[]}));expect(result.current.newMovement.notes).toBe('private');
  rerender({actor:user,id:3});expect(result.current.newMovement.notes).toBe('');
  act(()=>stale({notes:'leak'}));expect(result.current.newMovement.notes).toBe('');
  const sameAccount=result.current.setNewMovement;
  rerender({actor:null,id:3});rerender({actor:user,id:3});
  act(()=>sameAccount({notes:'late'}));expect(result.current.newMovement.notes).toBe('');
});
