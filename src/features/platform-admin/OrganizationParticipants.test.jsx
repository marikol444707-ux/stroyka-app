import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import OrganizationParticipants from './OrganizationParticipants';

const props = {company:{id:2,name:'Synthetic organization A'},API:'',C:{},btnG:{},btnO:{},inp:{}};
const response = body => ({ok:true,json:async()=>body});
afterEach(()=>jest.restoreAllMocks());

test('organization-scoped registry, ticket reason and guarded closure',async()=>{
  global.fetch=jest.fn(async url=>response(url.includes('/participants?')?{items:[{id:7,name:'Synthetic supplier',source_type:'warehouse_invoice',has_account:true,open_tickets:1}],hasMore:false}:url.includes('participant-tickets?')?{items:[{id:9,status:'resolved',reason:'Cabinet already exists',context:{participantName:'Synthetic supplier'}}],hasMore:false}:{id:9,status:'resolved',version:3,reason:'Cabinet already exists',comment:'Connect existing account',recommendedAction:'Review connection',context:{participantName:'Synthetic supplier',sourceType:'warehouse_invoice',applicationVersion:'test',role:'директор'},history:[]}));
  render(<OrganizationParticipants {...props}/>);
  expect(await screen.findByText('Synthetic supplier')).toBeInTheDocument();
  expect(fetch.mock.calls[0][0]).toContain('/system/companies/2/participants?');
  fireEvent.click(screen.getByText('Проблемы и обращения'));
  fireEvent.click(await screen.findByText('Разобрать обращение'));
  expect(await screen.findByText('Review connection')).toBeInTheDocument();
  const close=screen.getByRole('button',{name:'Проверено и закрыто'});
  expect(close).toBeDisabled();
  fireEvent.change(screen.getByLabelText('Сообщение о результате — видно автору обращения'),{target:{value:'Verified original scenario'}});
  fireEvent.click(screen.getByLabelText('Исходный сценарий проверен'));
  fireEvent.click(close);
  await waitFor(()=>expect(fetch).toHaveBeenCalledWith('/system/companies/2/participant-tickets/9',expect.objectContaining({method:'PATCH',body:JSON.stringify({status:'closed',expectedVersion:3,result:'Verified original scenario',verified:true})})));
});

test('company switch drops previous data and ignores late response',async()=>{
  let resolveOld;
  global.fetch=jest.fn(url=>url.includes('/2/')?new Promise(resolve=>{resolveOld=resolve;}):Promise.resolve(response({items:[],hasMore:false})));
  const view=render(<OrganizationParticipants key="2" {...props}/>);
  view.rerender(<OrganizationParticipants key="3" {...props} company={{id:3,name:'Synthetic organization B'}}/>);
  expect(await screen.findByText('Поставщики этой организации пока не подключены.')).toBeInTheDocument();
  await act(async()=>resolveOld(response({items:[{id:7,name:'PRIVATE A'}],hasMore:false})));
  expect(screen.queryByText('PRIVATE A')).not.toBeInTheDocument();
});

test('loading failure differs from empty list and can be retried',async()=>{
  global.fetch=jest.fn().mockResolvedValueOnce({ok:false,json:async()=>({detail:'Раздел пока не включён'})}).mockResolvedValue(response({items:[],hasMore:false}));
  render(<OrganizationParticipants {...props}/>);
  expect(await screen.findByText('Раздел пока не включён')).toBeInTheDocument();
  expect(screen.queryByText('Поставщики этой организации пока не подключены.')).not.toBeInTheDocument();
  fireEvent.click(screen.getByText('Повторить загрузку'));
  expect(await screen.findByText('Поставщики этой организации пока не подключены.')).toBeInTheDocument();
});
