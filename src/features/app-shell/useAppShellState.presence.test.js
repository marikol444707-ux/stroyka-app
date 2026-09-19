import {requestPushPermission} from '../../utils/appRuntimeUtils';
import {renderHook,act} from '@testing-library/react';
import {useAuthenticatedAppBootstrapEffect} from './useAppShellState';
jest.mock('../../utils/appRuntimeUtils',()=>({requestPushPermission:jest.fn(async()=>false)}));
const originalFetch=global.fetch;
beforeEach(()=>{requestPushPermission.mockResolvedValue(false);});
afterEach(()=>{global.fetch=originalFetch;jest.useRealTimers();});
function props(role){return {API:'/api',user:{id:7,name:'Тест',role},mobileLoadedScopesRef:{current:new Set()},mobileApiRequestsRef:{current:new Map()},loadMobileInitial:jest.fn(async()=>{}),setInitialDataLoaded:jest.fn(),setActivePage:jest.fn(),setCompanyName:jest.fn(),setPushEnabled:jest.fn()};}
it('supplier never sends company-workforce presence on entry or on the timer',async()=>{
 jest.useFakeTimers();global.fetch=jest.fn(async()=>({ok:true}));
 const input=props('поставщик');const {unmount}=renderHook(()=>useAuthenticatedAppBootstrapEffect(input));
 await act(async()=>{jest.advanceTimersByTime(61000);});
 expect(input.loadMobileInitial).toHaveBeenCalledTimes(1);
 expect(global.fetch).not.toHaveBeenCalled();unmount();
});
it('employee presence keeps polling and stops when unmounted',async()=>{
 jest.useFakeTimers();global.fetch=jest.fn(async()=>({ok:true}));
 const input=props('директор');const {unmount}=renderHook(()=>useAuthenticatedAppBootstrapEffect(input));
 await act(async()=>{jest.advanceTimersByTime(31000);});
 expect(global.fetch).toHaveBeenCalledTimes(2);unmount();
 await act(async()=>{jest.advanceTimersByTime(31000);});expect(global.fetch).toHaveBeenCalledTimes(2);
});
