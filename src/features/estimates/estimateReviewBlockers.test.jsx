import { act, renderHook } from '@testing-library/react';
import { useAppMainState } from '../app-shell/useAppMainState';
import { createEstimateWorkflowActions } from './estimateWorkflowActions';
import { createEstimatePageActions } from './estimatePageActions';
import { persistEstimateAction } from './estimatePersistenceActions';
import { createMaterialNormCoverageActions } from '../material-norms/materialNormCoverageActions';

const a = {id:7, revision:1, name:'A', projectId:11, projectName:'School', status:'Активная', sectionsLoaded:true, sections:[{name:'Section',items:[]}]};
const b = {...a,id:8,name:'B',status:'Черновик'};
const deferred = () => { let resolve; const promise = new Promise(r => {resolve=r;}); return {promise,resolve}; };
const response = (data, status=200) => ({ok:status===200,status,json:async()=>data});
function setup(selected=a) {
  const {result} = renderHook(useAppMainState);
  act(()=>{result.current.setEstimatesList([a,b]); result.current.setSelectedEstimate(selected);});
  return result;
}
function persistence(result, fetchFn, quality=jest.fn(), norm=jest.fn()) {
  return (est, options) => persistEstimateAction({...result.current, API:'/api',est,options,fetchFn,
    queueEstimateQualityReviewTask:quality,queueEstimateNormReviewTask:norm});
}

test.each(['edit','reopen','open-from-list'])('DELETE preserves a newer draft (%s) and explains server deletion', async scenario=>{
  const result = setup(scenario==='open-from-list'?null:a), pending=deferred();
  const actions=createEstimateWorkflowActions({...result.current,API:'/api',confirmFn:()=>true,fetchFn:()=>pending.promise});
  let deleting;
  act(()=>{deleting=actions.deleteEstimateRemote(a);});
  act(()=>{
    if(scenario==='reopen') result.current.setSelectedEstimate(null);
    if(scenario!=='edit') result.current.setSelectedEstimate(a);
    result.current.setSelectedEstimate({...a,name:'Новый локальный черновик'});
  });
  const draft=result.current.selectedEstimate;
  await act(async()=>{pending.resolve(response({ok:true}));await deleting;});
  expect(result.current.selectedEstimate).toBe(draft);
  expect(result.current.hasUnsavedEstimateChanges).toBe(true);
  expect(result.current.estimateSaveState.error).toMatch(/удалена.*сервере/);
  expect(result.current.estimatesList.some(e=>e.id===a.id)).toBe(false);
});

test('unchanged DELETE closes only its original editor',async()=>{
  const result=setup();
  await act(async()=>{await createEstimateWorkflowActions({...result.current,API:'/api',confirmFn:()=>true,fetchFn:async()=>response({ok:true})}).deleteEstimateRemote(a);});
  expect(result.current.selectedEstimate).toBeNull();
});

test('coverage outside editor acknowledges revision for the next save',async()=>{
  const result=setup(null);const fetchFn=jest.fn().mockResolvedValueOnce(response({revision:2})).mockResolvedValueOnce(response({revision:3}));
  const notice=jest.fn();
  const update=async()=>createMaterialNormCoverageActions({...result.current,user:{name:'User'},canEditMaterialNorms:()=>true,sectionsOfEstimate:e=>e.sections,
    persistEstimate:persistence(result,fetchFn),setMaterialNormNotice:notice}).updateEstimateFromNormCoverage({estimateId:7,sectionIdx:0},s=>({...s,items:[...s.items,{name:'material'}]}),'Saved','OK');
  await act(update);
  expect(result.current.estimatesList[0].revision).toBe(2);
  await act(update);
  expect(JSON.parse(fetchFn.mock.calls[1][1].body).expectedRevision).toBe(2);
  expect(result.current.estimatesList[0].revision).toBe(3);
  expect(notice.mock.calls.map(([n])=>n.tone)).toEqual(['success','success']);
  expect(result.current.selectedEstimate).toBeNull();
});

test.each([409,500])('coverage reports HTTP %s without false success or losing local draft',async status=>{
  const result=setup(null), notice=jest.fn();
  const fetchFn=jest.fn().mockResolvedValue(response({detail:{code:status===409?'estimate_revision_conflict':'failed',message:'failure'}},status));
  await act(async()=>{await createMaterialNormCoverageActions({...result.current,canEditMaterialNorms:()=>true,sectionsOfEstimate:e=>e.sections,
    persistEstimate:persistence(result,fetchFn),setMaterialNormNotice:notice}).updateEstimateFromNormCoverage({estimateId:7,sectionIdx:0},s=>({...s,items:[{name:'local material'}]}),'Saved','OK');});
  expect(notice).toHaveBeenCalledWith(expect.objectContaining({tone:'error'}));
  expect(notice).not.toHaveBeenCalledWith(expect.objectContaining({tone:'success'}));
  expect(result.current.estimatesList[0]).toMatchObject({revision:1,sections:[{items:[{name:'local material'}]}]});
  expect(fetchFn).toHaveBeenCalledTimes(1);
});

test.each(['conflict','error','edit','switch','close','reopen'])('normalization stops follow-up effects after %s',async scenario=>{
  const result=setup(),pending=deferred(),queue=jest.fn(),warnings=jest.fn(),alert=jest.fn();
  const fetchFn=()=>pending.promise;
  const actions=createEstimatePageActions({...result.current,normalizeEstimateImportSections:s=>[...s],persistEstimate:persistence(result,fetchFn),
    estimateQualityRows:()=>[],setImportValidationWarnings:warnings,queueEstimateQualityReviewTask:queue,alertFn:alert});
  let normalizing;
  act(()=>{normalizing=actions.handleNormalizeSelectedEstimateImport();});
  act(()=>{
    if(scenario==='edit') result.current.setSelectedEstimate({...result.current.selectedEstimate,name:'new'});
    if(scenario==='switch') result.current.setSelectedEstimate(b);
    if(['close','reopen'].includes(scenario)) result.current.setSelectedEstimate(null);
    if(scenario==='reopen') result.current.setSelectedEstimate(a);
  });
  await act(async()=>{pending.resolve(['conflict','error'].includes(scenario)?response({detail:{code:'estimate_revision_conflict'}},scenario==='conflict'?409:500):response({revision:2}));await normalizing;});
  expect(queue).not.toHaveBeenCalled();expect(warnings).not.toHaveBeenCalled();expect(alert).not.toHaveBeenCalled();
});

test.each(['comparison','summary'])('late %s details preserve newer list entries',async mode=>{
  const result=setup(null),pending=deferred(); const unloaded={...a,sectionsLoaded:false};
  act(()=>result.current.setEstimatesList([unloaded,b]));
  const actions=createEstimateWorkflowActions({...result.current,API:'/api',fetchFn:()=>pending.promise,showPreview:jest.fn(),buildEstimateDiffDocContent:()=>'',buildProjectEstimateDiffSummaryDocContent:()=>''});
  let loading;
  act(()=>{loading=mode==='comparison'?actions.openEstimateDiffPreview(unloaded,b):actions.openProjectEstimateDiffSummary('School',[{base:unloaded,next:b}]);});
  const newer={...a,name:'Новые данные',revision:5};
  act(()=>result.current.setEstimatesList([newer,b]));
  await act(async()=>{pending.resolve(response([a]));await loading;});
  expect(result.current.estimatesList[0]).toBe(newer);
});

test('activation uses server revisions for both estimates and preserves unrelated edits',async()=>{
  const result=setup(null),pending=deferred();
  const actions=createEstimateWorkflowActions({...result.current,API:'/api',fetchFn:jest.fn().mockReturnValueOnce(pending.promise),estimateReconciliations:[{baseEstimateId:7,nextEstimateId:8}]});
  let saving;
  await act(async()=>{saving=actions.setEstimateStatusRemote(b,'Активная');});
  const unrelated={id:99,name:'new local draft',revision:1};
  act(()=>result.current.setEstimatesList(prev=>[...prev,unrelated]));
  await act(async()=>{pending.resolve(response({revision:4,affectedEstimates:[{id:7,previousRevision:1,revision:12,status:'Черновик'},{id:8,previousRevision:1,revision:4,status:'Активная'}]}));await saving;});
  expect(result.current.estimatesList.find(e=>e.id===7)).toMatchObject({revision:12,status:'Черновик'});
  expect(result.current.estimatesList.find(e=>e.id===8)).toMatchObject({revision:4,status:'Активная'});
  expect(result.current.estimatesList.find(e=>e.id===99)).toBe(unrelated);
});

test.each(['edit','reopen'])('late list save skips acknowledgment and reviews after %s',async scenario=>{
  const result=setup(null),pending=deferred(),quality=jest.fn(),norm=jest.fn(),notice=jest.fn();
  const coverage=createMaterialNormCoverageActions({...result.current,canEditMaterialNorms:()=>true,sectionsOfEstimate:e=>e.sections,
    persistEstimate:persistence(result,()=>pending.promise,quality,norm),setMaterialNormNotice:notice});
  let saving;
  act(()=>{saving=coverage.updateEstimateFromNormCoverage({estimateId:7,sectionIdx:0},s=>({...s,items:[{name:'saved snapshot'}]}),'Saved','OK');});
  const newer={...result.current.estimatesList[0],name:'new draft'};
  act(()=>{
    if(scenario==='edit') result.current.setEstimatesList(prev=>prev.map(e=>e.id===7?newer:e));
    else {result.current.setSelectedEstimate(a);result.current.setSelectedEstimate(null);}
  });
  const before=result.current.estimatesList;
  await act(async()=>{pending.resolve(response({revision:2}));await saving;});
  expect(result.current.estimatesList).toBe(before);
  expect(notice).not.toHaveBeenCalled();expect(quality).not.toHaveBeenCalled();expect(norm).not.toHaveBeenCalled();
});

test('normalization current save runs follow-up but a close during review suppresses success alert',async()=>{
  const result=setup(),review=deferred(),queue=jest.fn(()=>review.promise),warnings=jest.fn(),alert=jest.fn();
  const actions=createEstimatePageActions({...result.current,normalizeEstimateImportSections:s=>[...s],persistEstimate:persistence(result,async()=>response({revision:2})),
    estimateQualityRows:()=>[],setImportValidationWarnings:warnings,queueEstimateQualityReviewTask:queue,alertFn:alert});
  let normalizing;
  await act(async()=>{normalizing=actions.handleNormalizeSelectedEstimateImport();});
  expect(warnings).toHaveBeenCalledTimes(1);
  expect(queue).toHaveBeenCalledWith(expect.objectContaining({revision:2}),'Нормализация импорта сметы');
  act(()=>result.current.setSelectedEstimate(null));
  await act(async()=>{review.resolve();await normalizing;});
  expect(alert).not.toHaveBeenCalled();
});

test('activation must not rebase a previous estimate whose server snapshot was unknown',async()=>{
  const result=setup(null);
  const actions=createEstimateWorkflowActions({...result.current,API:'/api',estimateReconciliations:[{baseEstimateId:7,nextEstimateId:8}],
    fetchFn:async()=>response({revision:2,affectedEstimates:[{id:7,previousRevision:9,revision:10,status:'Черновик'},{id:8,previousRevision:1,revision:2,status:'Активная'}]})});
  await act(async()=>{await actions.setEstimateStatusRemote(b,'Активная');});
  // The next PUT must conflict; adopting revision 10 would allow overwriting unseen changes.
  expect(result.current.estimatesList.find(e=>e.id===7)).toBe(a);
  expect(result.current.estimatesList.find(e=>e.id===8).revision).toBe(2);
});

test('importing a new active estimate acknowledges the previous estimate revision',async()=>{
  const result=setup(null),noop=jest.fn();
  const fetchFn=jest.fn(async url=>{
    if(url.endsWith('/parse-smeta')) return response({items:[{section:'Section',name:'Work',unit:'шт',quantity:1,type:'work'}],count:1});
    if(url.endsWith('/estimates')) return response({id:99,revision:1,affectedEstimates:[{id:7,previousRevision:1,revision:2,status:'Черновик'}]});
    return response({response:'{"warnings":[]}'});
  });
  const actions=createEstimatePageActions({...result.current,API:'/api',fetchFn,readApiResult:r=>r.json(),
    newEstimate:{projectId:11,projectName:'School',status:'Активная'},projects:[],isLeadership:true,nextEstimateVersionFor:()=> '2.0',
    enrichEstimateMeasurementBasis:s=>s,isGlobalEstimateTemplate:()=>false,sameEstimateGroup:()=>true,
    createEstimateReconciliation:async()=>null,queueEstimateDiffReviewTask:noop,autoReconcileEstimateChanges:noop,
    queueEstimateQualityReviewTask:noop,queueEstimateNormReviewTask:noop,estimateQualityRows:()=>[],alertFn:noop,
    setImportValidating:noop,setImportValidationWarnings:noop});
  await act(async()=>{await actions.handleEstimateImportFile({target:{files:[new File(['local'],'estimate.xlsx')],value:'file'}});});
  expect(result.current.estimatesList.find(e=>e.id===7)).toMatchObject({status:'Черновик',revision:2});
  expect(result.current.estimatesList.find(e=>e.id===99)).toMatchObject({status:'Активная',revision:1});
});

test('activation also acknowledges the unchanged open previous estimate without clearing dirty edits',async()=>{
  const result=setup(a);
  act(()=>result.current.setSelectedEstimate({...a,name:'local unsaved title'}));
  const actions=createEstimateWorkflowActions({...result.current,API:'/api',estimateReconciliations:[{baseEstimateId:7,nextEstimateId:8}],
    fetchFn:async()=>response({revision:2,affectedEstimates:[{id:7,previousRevision:1,revision:2,status:'Черновик'},{id:8,previousRevision:1,revision:2,status:'Активная'}]})});
  await act(async()=>{await actions.setEstimateStatusRemote(b,'Активная');});
  expect(result.current.selectedEstimate).toMatchObject({id:7,name:'local unsaved title',revision:2,status:'Черновик'});
  expect(result.current.hasUnsavedEstimateChanges).toBe(true);
  expect(result.current.estimateSaveState.status).toBe('dirty');
});
