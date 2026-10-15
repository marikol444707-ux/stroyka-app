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

const originalSupportFlag=process.env.REACT_APP_PARTICIPANT_SUPPORT_ACCESS_ENABLED;
afterEach(()=>{if(originalSupportFlag===undefined)delete process.env.REACT_APP_PARTICIPANT_SUPPORT_ACCESS_ENABLED;else process.env.REACT_APP_PARTICIPANT_SUPPORT_ACCESS_ENABLED=originalSupportFlag;localStorage.clear();});
it('dedicated support skips business bootstrap, cached records, push and presence',async()=>{
 process.env.REACT_APP_PARTICIPANT_SUPPORT_ACCESS_ENABLED='1';jest.useFakeTimers();
 requestPushPermission.mockClear();global.fetch=jest.fn(async()=>({ok:true}));
 const input=props('platform_support');const cached=jest.fn();input.storageSetters={privateCache:cached};
 localStorage.setItem('privateCache','["old business data"]');localStorage.setItem('companyName','Old company');
 const {unmount}=renderHook(()=>useAuthenticatedAppBootstrapEffect(input));
 await act(async()=>{jest.advanceTimersByTime(61000);});
 expect(input.loadMobileInitial).not.toHaveBeenCalled();expect(cached).not.toHaveBeenCalled();
 expect(input.setCompanyName).not.toHaveBeenCalled();expect(requestPushPermission).not.toHaveBeenCalled();
 expect(global.fetch).not.toHaveBeenCalled();expect(input.setInitialDataLoaded).toHaveBeenCalledWith(true);unmount();
});
it('late prior bootstrap callbacks cannot change the new actor state',async()=>{
 let pushReply;let loaderFailure;
 requestPushPermission.mockImplementation(()=>new Promise(resolve=>{pushReply=resolve;}));
 global.fetch=jest.fn(async()=>({ok:true}));
 const input=props('директор');input.loadMobileInitial.mockImplementation(()=>new Promise((_resolve,reject)=>{loaderFailure=reject;}));
 const support={...props('platform_support'),setPushEnabled:input.setPushEnabled,setInitialDataLoaded:input.setInitialDataLoaded};
 process.env.REACT_APP_PARTICIPANT_SUPPORT_ACCESS_ENABLED='1';
 const {rerender}=renderHook(props=>useAuthenticatedAppBootstrapEffect(props),{initialProps:input});
 rerender(support);input.setInitialDataLoaded.mockClear();
 await act(async()=>{pushReply(true);loaderFailure(new Error('Late old request'));});
 expect(input.setPushEnabled).not.toHaveBeenCalled();expect(input.setInitialDataLoaded).not.toHaveBeenCalled();
});
