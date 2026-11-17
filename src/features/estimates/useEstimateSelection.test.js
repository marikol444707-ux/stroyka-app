import {act, renderHook} from '@testing-library/react';
import {useEstimateSelection} from './useEstimateSelection';
const estimate = {id:7, revision:1, sections:[]};

test('server detail loading establishes a clean draft', () => {
  const {result}=renderHook(useEstimateSelection);
  act(()=>result.current.setSelectedEstimate(estimate));
  act(()=>result.current.setSelectedEstimate({...estimate,sectionsLoaded:true},{fromServer:true}));
  expect(result.current.hasUnsavedEstimateChanges).toBe(false);
  expect(result.current.estimateSaveState.status).toBe('idle');
});

test('a metadata save acknowledges revision while keeping unsaved content dirty', () => {
  const {result}=renderHook(useEstimateSelection);
  act(()=>result.current.setSelectedEstimate(estimate));
  act(()=>result.current.setSelectedEstimate({...estimate,name:'Локальная правка'}));
  let operation;
  act(()=>{operation=result.current.beginEstimateSave(result.current.selectedEstimate,{fullSnapshot:false});});
  act(()=>{operation.finish({status:'saved',revision:2,estimate:{...result.current.selectedEstimate,isTemplate:true}});});
  expect(result.current.selectedEstimate).toMatchObject({name:'Локальная правка',isTemplate:true,revision:2});
  expect(result.current.hasUnsavedEstimateChanges).toBe(true);
  expect(result.current.estimateSaveState.status).toBe('dirty');
});

test('two saves of the same edit revision ignore the older response', () => {
  const {result}=renderHook(useEstimateSelection);
  act(()=>result.current.setSelectedEstimate(estimate));
  let first,second;
  act(()=>{first=result.current.beginEstimateSave(estimate);second=result.current.beginEstimateSave(estimate);});
  act(()=>{second.finish({status:'conflict',error:'Conflict'});first.finish({status:'saved',revision:2});});
  expect(result.current.selectedEstimate).toBe(estimate);
  expect(result.current.estimateSaveState).toEqual({status:'conflict',error:'Conflict'});
});
