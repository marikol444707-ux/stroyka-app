import { act, renderHook } from '@testing-library/react';
import { clearNavigationTarget, navigationHref, readNavigationTarget, selectedCompanyId, targetMatchesRow, targetMatchesProject, useNavigationTarget } from './navigationTarget';
afterEach(() => window.history.replaceState({}, '', '/app'));
test.each(['material','tool','estimate','document'])('round trip exact %s link retains company and project', type => {
  const path = navigationHref({type,id:45,companyId:3,projectId:7}, 'https://example.test/app');
  const target = readNavigationTarget(new URL(path,'https://example.test').search);
  expect(target).toEqual({type,id:'45',companyId:'3',projectId:'7'});
  expect(targetMatchesRow(target,{id:45,companyId:3})).toBe(true);
  expect(targetMatchesRow(target,{id:45,companyId:4})).toBe(false);
});
test('invalid type, missing owner and document without project are rejected', () => {
  expect(readNavigationTarget('?view=warehouse&entityType=material&entityId=4')).toBeNull();
  expect(navigationHref({type:'document',id:4,companyId:3})).toBeNull();
  expect(navigationHref({type:'unknown',id:4,companyId:3})).toBeNull();
  expect(selectedCompanyId({mode:'all_companies'},{companyId:3})).toBe('');
});
test('back and clearing focus update subscribers while preserving object/company', () => {
  window.history.replaceState({},'',navigationHref({type:'material',id:4,companyId:3,projectId:7}));
  const {result}=renderHook(()=>useNavigationTarget());
  expect(result.current.id).toBe('4');
  act(()=>clearNavigationTarget());
  expect(result.current).toBeNull();
  expect(new URLSearchParams(window.location.search).get('appProjectId')).toBe('7');
  act(()=>{window.history.replaceState({},'',navigationHref({type:'tool',id:9,companyId:3}));window.dispatchEvent(new PopStateEvent('popstate'));});
  expect(result.current.id).toBe('9');
});

test('document return object is exact and ambiguous legacy names are rejected',()=>{
  const target={projectId:'7',companyId:'3'};
  const projects=[{id:7,companyId:3,name:'Объект'},{id:8,companyId:3,name:'Объект'}];
  expect(targetMatchesProject(target,{projectId:7},projects)).toBe(true);
  expect(targetMatchesProject(target,{projectId:8},projects)).toBe(false);
  expect(targetMatchesProject(target,{projectName:'Объект'},projects)).toBe(false);
  expect(targetMatchesProject(target,{projectName:'Объект'},projects.slice(0,1))).toBe(true);
});
