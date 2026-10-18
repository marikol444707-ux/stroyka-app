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

test('memberships show the company role and typed diagnostics; invite purpose and filters stay separate',async()=>{
  global.fetch=jest.fn(async url=>response(url.includes('/participant-memberships?')?{items:[{membershipId:31,userId:7,name:'Synthetic colleague',role:'мастер',status:'review',activeRoleCount:2}],hasMore:false}:url.includes('/participant-invitations?')?{items:[{inviteId:12,purpose:'supplier_registration',role:'поставщик',status:'expired',expiresAt:'2026-01-01T12:00:00'}],hasMore:false}:{items:[],hasMore:false}));
  render(<OrganizationParticipants {...props}/>);
  fireEvent.click(screen.getByRole('button',{name:'Сотрудники и роли'}));
  expect(await screen.findByText('Synthetic colleague')).toBeInTheDocument();
  expect(screen.getByText('Мастер')).toBeInTheDocument();
  expect(screen.getByText(/Несколько включённых ролей/)).toBeInTheDocument();
  expect(screen.getByText(/Членство: 31 · Пользователь: 7/)).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('Имя или роль'),{target:{value:'мастер'}});
  fireEvent.click(screen.getByRole('button',{name:'Найти'}));
  await waitFor(()=>expect(fetch.mock.calls.some(([url])=>url.includes('participant-memberships?search='+encodeURIComponent('мастер')))).toBe(true));
  fireEvent.click(screen.getByRole('button',{name:'Приглашения'}));
  expect(await screen.findByText('Приглашение №12')).toBeInTheDocument();
  expect(screen.getByText('Регистрация поставщика')).toBeInTheDocument();
  expect(screen.queryByText('Synthetic colleague')).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('Состояние приглашения'),{target:{value:'expired'}});
  await waitFor(()=>expect(fetch.mock.calls.some(([url])=>url.includes('participant-invitations?status=expired'))).toBe(true));
  expect(fetch.mock.calls.every(([,options])=>!options.method)).toBe(true);
});

test('switching tabs aborts late membership response and resets previous search',async()=>{
  let late;
  global.fetch=jest.fn(url=>url.includes('/participant-memberships?')?new Promise(resolve=>{late=resolve;}):Promise.resolve(response({items:[],hasMore:false})));
  render(<OrganizationParticipants {...props}/>);
  fireEvent.click(screen.getByRole('button',{name:'Сотрудники и роли'}));
  fireEvent.click(screen.getByRole('button',{name:'Приглашения'}));
  expect(await screen.findByText('Сохранённых приглашений этой организации пока нет.')).toBeInTheDocument();
  await act(async()=>late(response({items:[{membershipId:3,name:'LATE PRIVATE EMPLOYEE'}],hasMore:false})));
  expect(screen.queryByText('LATE PRIVATE EMPLOYEE')).not.toBeInTheDocument();
});

test('duplicate correction is offered only for unowned unmerged company cards',async()=>{
  const previous=process.env.REACT_APP_PARTICIPANT_HISTORY_MERGE_ENABLED;
  process.env.REACT_APP_PARTICIPANT_HISTORY_MERGE_ENABLED='1';
  try {
    global.fetch=jest.fn(async()=>response({items:[{id:7,name:'Из накладной',has_account:false},
      {id:8,name:'С кабинетом',has_account:true},{id:9,name:'Архивная',has_account:false,merged_into_supplier_id:'8'}],hasMore:false}));
    render(<OrganizationParticipants {...props}/>);
    expect(await screen.findAllByRole('button',{name:'Объединить дубли'})).toHaveLength(1);
    fireEvent.click(screen.getByRole('button',{name:'Объединить дубли'}));
    expect(screen.getByRole('region',{name:'Объединение дубля'})).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button',{name:'Закрыть объединение'}));
    expect(screen.queryByRole('region',{name:'Объединение дубля'})).not.toBeInTheDocument();
  } finally {
    if(previous===undefined)delete process.env.REACT_APP_PARTICIPANT_HISTORY_MERGE_ENABLED;
    else process.env.REACT_APP_PARTICIPANT_HISTORY_MERGE_ENABLED=previous;
  }
});
