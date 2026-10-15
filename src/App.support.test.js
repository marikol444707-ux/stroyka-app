import {act,render,screen} from '@testing-library/react';
import App from './App';
let mockActivePage='dashboard';
jest.mock('./features/app-shell/useAppMainState',()=>{
 const actual=jest.requireActual('./features/app-shell/useAppMainState');
 return {...actual,useAppMainState:()=>({...actual.useAppMainState(),activePage:mockActivePage,estimatesTab:'norms'})};
});
const originalFlag=process.env.REACT_APP_PARTICIPANT_SUPPORT_ACCESS_ENABLED;
const originalFetch=global.fetch;
afterEach(()=>{localStorage.clear();window.history.replaceState({},'', '/');global.fetch=originalFetch;if(originalFlag===undefined)delete process.env.REACT_APP_PARTICIPANT_SUPPORT_ACCESS_ENABLED;else process.env.REACT_APP_PARTICIPANT_SUPPORT_ACCESS_ENABLED=originalFlag;});
test.each(['dashboard','estimates','activitylog'])('full App support entry with previous page %s only requests the assigned workspace',async previousPage=>{
 mockActivePage=previousPage;
 process.env.REACT_APP_PARTICIPANT_SUPPORT_ACCESS_ENABLED='1';
 window.history.replaceState({},'', '/app?page=estimates');
 localStorage.setItem('user',JSON.stringify({id:12,role:'platform_support',name:'Synthetic support'}));
 global.fetch=jest.fn(async()=>({ok:true,json:async()=>({items:[],hasMore:false})}));
 render(<App/>);
 expect(await screen.findByText(/Назначенных обращений нет/)).toBeInTheDocument();
 await act(async()=>{await new Promise(resolve=>setTimeout(resolve,350));});
 expect(fetch.mock.calls.length).toBeGreaterThan(0);
 expect(fetch.mock.calls.every(([url])=>String(url).includes('/participant-support/workspace?'))).toBe(true);
});
