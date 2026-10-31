import { useState } from 'react';
import { act, renderHook } from '@testing-library/react';
import { useAppNavigationRuntime } from './appNavigationRuntime';
const user={id:1,role:'директор',companyId:3};
const projects=[{id:7,name:'Учебный объект'}];
function useHarness() {
  const [activePage,setActivePage]=useState('projects');
  const [expandedProject,setExpandedProject]=useState(7);
  const [activeProjectTab,setActiveProjectTab]=useState('Общее');
  const [warehouse,setSelectedWarehouseProject]=useState('Учебный объект');
  const actions=new Proxy({setActivePage,setExpandedProject,setActiveProjectTab,setSelectedWarehouseProject}, {get:(target,key)=>target[key] || (()=>{})});
  const runtime=useAppNavigationRuntime({ROLES:{директор:['projects','estimates','warehouse']},data:{projects},
    state:{activePage,expandedProject,activeProjectTab,user,globalSearch:'учебный'},actions});
  return {...runtime,activePage,expandedProject,activeProjectTab,warehouse};
}
beforeEach(()=>window.history.replaceState({},'','/app'));
afterEach(()=>window.history.replaceState({},'','/app'));
test('navigation preserves object and selected warehouse; search carries exact project identity',()=>{
  const {result}=renderHook(()=>useHarness());
  expect(result.current.searchResults[0].projectId).toBe(7);
  act(()=>result.current.navigateTo('estimates'));
  expect(result.current.expandedProject).toBe(7);
  expect(result.current.warehouse).toBe('Учебный объект');
  expect(new URLSearchParams(window.location.search).get('view')).toBe('estimates');
});
test('refresh restores allowed project route and popstate restores page',()=>{
  window.history.replaceState({},'','/app?view=estimates&appProjectId=7&projectTab=Материалы');
  const {result}=renderHook(()=>useHarness());
  expect(result.current.activePage).toBe('estimates');
  expect(result.current.activeProjectTab).toBe('Материалы');
  act(()=>{
    window.history.replaceState({},'','/app?view=projects&appProjectId=7');
    window.dispatchEvent(new PopStateEvent('popstate'));
  });
  expect(result.current.activePage).toBe('projects');
});
test('unknown project ID is never restored as selected entity',()=>{
  window.history.replaceState({},'','/app?view=projects&appProjectId=999');
  const {result}=renderHook(()=>useHarness());
  expect(result.current.expandedProject).toBeNull();
});
