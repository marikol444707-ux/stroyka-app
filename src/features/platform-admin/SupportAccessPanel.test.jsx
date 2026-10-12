import {act, fireEvent, render, screen, waitFor} from '@testing-library/react';
import SupportAccessPanel from './SupportAccessPanel';

const props={prefix:'/system/companies/2',ticketId:9,btnG:{},btnO:{},inp:{}};
const response=body=>({ok:true,json:async()=>body});
afterEach(()=>jest.restoreAllMocks());

test('grants exact diagnostic scope and revokes without exposing archive actions',async()=>{
  let issued=false,revoked=false;
  global.fetch=jest.fn(async(url,options={})=>{
    if(options.method==='POST'){if(url.endsWith('/revoke'))revoked=true;else issued=true;return response({id:'grant'});}
    if(url.endsWith('support-assignees'))return response({items:[{id:17,name:'Поддержка'}]});
    return response({items:issued?[{id:'grant',assigneeId:17,assigneeName:'Поддержка',active:!revoked,revokedAt:revoked?'2026-10-13T12:00:00Z':null,expiresAt:'2026-10-13T13:00:00Z',reason:'Проверить приглашение',history:[]}]:[],hasMore:false});
  });
  render(<SupportAccessPanel {...props}/>);
  const grant=await screen.findByRole('button',{name:'Дать доступ к диагностике'});
  expect(grant).toBeDisabled();
  fireEvent.change(screen.getByLabelText('Сотрудник поддержки'),{target:{value:'17'}});
  fireEvent.change(screen.getByLabelText('Зачем нужен доступ'),{target:{value:'Проверить приглашение'}});
  fireEvent.click(grant);fireEvent.click(grant);
  await screen.findByText('Действует');
  expect(fetch.mock.calls.filter(([,o])=>o.method==='POST')).toHaveLength(1);
  expect(fetch).toHaveBeenCalledWith('/system/companies/2/participant-tickets/9/support-access',expect.objectContaining({body:JSON.stringify({assigneeId:17,action:'diagnostic.read',expiresInMinutes:60,reason:'Проверить приглашение'})}));
  fireEvent.click(screen.getByRole('button',{name:'Отозвать доступ'}));
  expect(await screen.findByText('Отозван')).toBeInTheDocument();
  expect(screen.queryByRole('button',{name:'Отозвать доступ'})).not.toBeInTheDocument();
});

test('company switch ignores late grant list and removes previous assignee',async()=>{
  let late;
  global.fetch=jest.fn(url=>url.includes('/2/')?new Promise(resolve=>{late=resolve;}):Promise.resolve(response({items:[],hasMore:false})));
  const view=render(<SupportAccessPanel key="2" {...props}/>);
  view.rerender(<SupportAccessPanel key="3" {...props} prefix="/system/companies/3"/>);
  await screen.findByText('Доступ к этому обращению ещё не выдавался.');
  await act(async()=>late(response({items:[{id:1,name:'PRIVATE OTHER ORGANIZATION'}]})));
  expect(screen.queryByText('PRIVATE OTHER ORGANIZATION')).not.toBeInTheDocument();
});

test('grant failure remains visible and does not show a successful grant',async()=>{
  global.fetch=jest.fn(async(url,options={})=>options.method==='POST'?{ok:false,json:async()=>({detail:'Обращение изменилось'})}:response(url.endsWith('support-assignees')?{items:[{id:17,name:'Поддержка'}]}:{items:[],hasMore:false}));
  render(<SupportAccessPanel {...props}/>);
  await screen.findByRole('button',{name:'Дать доступ к диагностике'});
  fireEvent.change(screen.getByLabelText('Сотрудник поддержки'),{target:{value:'17'}});
  fireEvent.change(screen.getByLabelText('Зачем нужен доступ'),{target:{value:'Проверить приглашение'}});
  fireEvent.click(screen.getByRole('button',{name:'Дать доступ к диагностике'}));
  expect(await screen.findByRole('alert')).toHaveTextContent('Обращение изменилось');
  await waitFor(()=>expect(screen.getByRole('button',{name:'Дать доступ к диагностике'})).not.toBeDisabled());
});

test('refused diagnostic attempts appear beside the exact grant history',async()=>{
  global.fetch=jest.fn(async url=>response(url.endsWith('support-assignees')?{items:[]}:{items:[{
    id:'grant',assigneeId:17,assigneeName:'Поддержка',active:false,revokedAt:'2026-10-13T12:00:00Z',
    expiresAt:'2026-10-13T13:00:00Z',reason:'Проверить приглашение',history:[],
    denials:[{actor_id:17,status_code:403,created_at:'2026-10-13T12:01:00Z'}],
  }],hasMore:false}));
  render(<SupportAccessPanel {...props}/>);
  expect(await screen.findByText('Попытки открыть без доступа · 1')).toBeInTheDocument();
  expect(screen.getByText(/В доступе отказано/)).toBeInTheDocument();
});
