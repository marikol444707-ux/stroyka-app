import { act, renderHook } from '@testing-library/react';
import { useAppMainState } from '../app-shell/useAppMainState';
import { createEstimateWorkflowActions } from './estimateWorkflowActions';
import { persistEstimateAction } from './estimatePersistenceActions';

const original = {id: 7, revision: 1, name: 'Смета', sectionsLoaded: false, sections: []};
const deferred = () => {
  let resolve;
  const promise = new Promise(r => { resolve = r; });
  return {promise, resolve};
};

test.each(['edit', 'switch', 'close', 'reopen'])('late detail response preserves selection and list after %s', async scenario => {
  const response = deferred();
  const {result} = renderHook(useAppMainState);
  act(() => result.current.setEstimatesList([original]));
  const actions = createEstimateWorkflowActions({
    ...result.current, API: '/api', fetchFn: () => response.promise,
  });
  let opening;
  act(() => { opening = actions.openEstimateDetail(original); });
  act(() => {
    if (scenario === 'edit') {
      const edited = {...original, name: 'Новая правка'};
      result.current.setSelectedEstimate(edited);
      result.current.setEstimatesList([edited]);
    }
    if (scenario === 'switch') result.current.setSelectedEstimate({id: 8});
    if (scenario === 'close' || scenario === 'reopen') result.current.setSelectedEstimate(null);
    if (scenario === 'reopen') result.current.setSelectedEstimate(original);
  });
  const expected = result.current.selectedEstimate;
  const list = result.current.estimatesList;
  await act(async () => {
    response.resolve({ok: true, json: async () => [{...original, sectionsLoaded: true}]});
    expect(await opening).toBeNull();
  });
  expect(result.current.selectedEstimate).toBe(expected);
  expect(result.current.estimatesList).toBe(list);
});

test('current detail response fills selection and list', async () => {
  const {result} = renderHook(useAppMainState);
  act(() => result.current.setEstimatesList([original]));
  const actions = createEstimateWorkflowActions({
    ...result.current, API: '/api',
    fetchFn: async () => ({ok: true, json: async () => [{...original, sectionsLoaded: true}]}),
  });
  await act(async () => { await actions.openEstimateDetail(original); });
  expect(result.current.selectedEstimate.sectionsLoaded).toBe(true);
  expect(result.current.estimatesList[0].sectionsLoaded).toBe(true);
});

test.each(['edit', 'switch', 'close', 'reopen'])('ordinary autosave does not replace selection after %s', async scenario => {
  const response = deferred();
  const {result} = renderHook(useAppMainState);
  act(() => result.current.setSelectedEstimate(original));
  let saving;
  act(() => { saving = persistEstimateAction({
    API: '/api', est: original, beginEstimateSave: result.current.beginEstimateSave, fetchFn: () => response.promise,
    estimatesList: [original], queueEstimateQualityReviewTask: jest.fn(), queueEstimateNormReviewTask: jest.fn(),
  }); });
  act(() => {
    if (scenario === 'edit') result.current.setSelectedEstimate({...original, name: 'Новая правка'});
    if (scenario === 'switch') result.current.setSelectedEstimate({id: 8});
    if (scenario === 'close' || scenario === 'reopen') result.current.setSelectedEstimate(null);
    if (scenario === 'reopen') result.current.setSelectedEstimate(original);
  });
  const expected = result.current.selectedEstimate;
  await act(async () => { response.resolve({ok: true, json: async () => ({revision: 2})}); await saving; });
  expect(result.current.selectedEstimate).toBe(expected);
});

 test('changing company invalidates an outstanding save, even if the same ID is reopened', async () => {
  const {result, rerender} = renderHook(({company}) => useAppMainState(company), {initialProps:{company:'1'}});
  act(() => result.current.setSelectedEstimate(original));
  let operation;
  act(() => { operation = result.current.beginEstimateSave(original); });
  rerender({company:'2'});
  act(() => result.current.setSelectedEstimate(original));
  expect(operation.isCurrent()).toBe(false);
  act(() => { operation.finish({status:'conflict', error:'old company'}); });
  expect(result.current.estimateSaveState).toEqual({status:'idle',error:''});
  expect(result.current.selectedEstimate.revision).toBe(1);
});

test('a late detail load cannot undo a newer server revision acknowledged by a metadata save', async () => {
  const response = deferred();
  const {result} = renderHook(useAppMainState);
  act(() => result.current.setEstimatesList([original]));
  const actions = createEstimateWorkflowActions({...result.current, API:'/api', fetchFn:()=>response.promise});
  let loading, save;
  act(() => { loading = actions.openEstimateDetail(original); });
  act(() => { save = result.current.beginEstimateSave(original, {fullSnapshot:false}); });
  act(() => { save.finish({status:'saved',revision:2,estimate:{...original,isTemplate:true}}); });
  await act(async () => {
    response.resolve({ok:true,json:async()=>[{...original,revision:1,sectionsLoaded:true}]});
    await loading;
  });
  expect(result.current.selectedEstimate).toMatchObject({revision:2,isTemplate:true});
  expect(result.current.estimateSaveState.status).toBe('saved');
});

test('changing status from the list updates its revision without opening an editor', async () => {
  const {result} = renderHook(useAppMainState);
  const estimate = {...original, status:'Активная'};
  act(() => result.current.setEstimatesList([estimate]));
  const actions = createEstimateWorkflowActions({
    ...result.current, API:'/api', notify:jest.fn(),
    fetchFn:async()=>({ok:true,json:async()=>({revision:2,status:'Черновик'})}),
  });
  await act(async()=>{ await actions.setEstimateStatusRemote(estimate, 'Черновик'); });
  expect(result.current.estimatesList[0]).toMatchObject({status:'Черновик',revision:2});
  expect(result.current.selectedEstimate).toBeNull();
  expect(result.current.estimateSaveState).toEqual({status:'idle',error:''});
});

test.each([true, false])('a late list status response after opening an editor has no UI effects (success=%s)', async success => {
  const response = deferred();
  const {result} = renderHook(useAppMainState);
  const estimate = {...original,status:'Активная'};
  act(()=>result.current.setEstimatesList([estimate]));
  const alertFn = jest.fn();
  const actions = createEstimateWorkflowActions({
    ...result.current, API:'/api', notify:jest.fn(), alertFn, fetchFn:()=>response.promise,
  });
  let changing;
  act(()=>{ changing = actions.setEstimateStatusRemote(estimate, 'Черновик'); });
  act(()=>result.current.setSelectedEstimate({...original,id:8}));
  const selected = result.current.selectedEstimate;
  const list = result.current.estimatesList;
  await act(async()=>{
    response.resolve({ok:success,status:success?200:409,json:async()=>({revision:2,detail:{code:'estimate_revision_conflict'}})});
    await changing;
  });
  expect(result.current.selectedEstimate).toBe(selected);
  expect(result.current.estimatesList).toBe(list);
  expect(result.current.estimateSaveState).toEqual({status:'idle',error:''});
  expect(alertFn).not.toHaveBeenCalled();
});
