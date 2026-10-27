import React from 'react';
import {render,screen,waitFor,fireEvent} from '@testing-library/react';
import WorkReviewQueue from './WorkReviewQueue';
jest.mock('./WorkAcceptancePanel',()=>()=>null);
const row=(id,companyId=2)=>({id,companyId,status:'На проверке',project:'Object',description:'Work '+id,masterName:'Worker',quantity:2,unit:'м²',date:'2026-10-27'});
const props={API:'/api',companyContext:{selectedCompanyId:2},user:{id:9,role:'директор'},C:{}};
const ok=data=>({ok:true,json:async()=>data});
afterEach(()=>jest.restoreAllMocks());
test('independent pending queue fetches scoped status with pagination; accountant sees pending but cannot approve',async()=>{
 global.fetch=jest.fn().mockResolvedValueOnce(ok(Array.from({length:50},(_,i)=>row(i+1)))).mockResolvedValueOnce(ok([row(51)]));
 render(<WorkReviewQueue {...props} user={{id:9,role:'бухгалтер'}}/>);
 await screen.findByText('Work 1');expect(fetch.mock.calls[0][0]).toContain('status='+encodeURIComponent('На проверке'));
 expect(fetch.mock.calls[0][1].headers['X-Company-Id']).toBe('2');
 fireEvent.click(screen.getByText('Показать ещё'));await screen.findByText('Work 51');expect(fetch.mock.calls[1][0]).toContain('offset=50');expect(screen.queryByText('Проверить работу')).not.toBeInTheDocument();
});
test('company switch hides previous rows and ignores late response; server error is not empty success',async()=>{
 let finish;global.fetch=jest.fn().mockReturnValueOnce(new Promise(resolve=>finish=resolve)).mockResolvedValueOnce({ok:false,json:async()=>({detail:'Нет доступа'})});
 const {rerender}=render(<WorkReviewQueue {...props}/>);rerender(<WorkReviewQueue {...props} companyContext={{selectedCompanyId:3}}/>);
 await screen.findByRole('alert');finish(ok([row(1)]));await waitFor(()=>expect(screen.queryByText('Work 1')).not.toBeInTheDocument());expect(screen.queryByText('Работ на проверке не найдено.')).not.toBeInTheDocument();
});
test('StrictMode still loads queue and suppresses rows of another company',async()=>{
 global.fetch=jest.fn().mockResolvedValue(ok([row(1),row(2,3)]));render(<React.StrictMode><WorkReviewQueue {...props}/></React.StrictMode>);await screen.findByText('Work 1');expect(screen.queryByText('Work 2')).not.toBeInTheDocument();
});
