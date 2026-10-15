import {act,fireEvent,render,screen} from '@testing-library/react';
import SupportWorkspace from './SupportWorkspace';
const props={API:'',C:{},btnG:{}};
const response=body=>({ok:true,json:async()=>body});
const access={id:'grant',companyId:2,companyName:'Организация А',ticketId:9,reasonLabel:'Приглашение недоступно',expiresAt:'2099-10-13T12:00:00Z'};
afterEach(()=>jest.restoreAllMocks());

test('only assigned diagnostics are offered and every open uses the capability path',async()=>{
  global.fetch=jest.fn(async url=>response(url.includes('/diagnostic')?{...access,comment:'Помогите подключиться',context:{participantName:'Поставщик'},result:''}:{items:[access],hasMore:false}));
  render(<SupportWorkspace {...props}/>);
  fireEvent.click(await screen.findByRole('button',{name:'Открыть диагностику №9'}));
  expect(await screen.findByText('Помогите подключиться')).toBeInTheDocument();
  expect(fetch).toHaveBeenCalledWith('/participant-support/workspace/grant/diagnostic',{cache:'no-store'});
  expect(screen.queryByRole('button',{name:/счёт|файл|оплат|объедин/i})).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button',{name:'Закрыть диагностику'}));
  expect(screen.queryByText('Помогите подключиться')).not.toBeInTheDocument();
});

test('revoked access does not retain an earlier diagnostic',async()=>{
  let denied=false;
  global.fetch=jest.fn(async url=>url.includes('/diagnostic')?(denied?{ok:false,json:async()=>({detail:'Доступ отозван'})}:response({...access,comment:'OLD CONTEXT',context:{}})):response({items:[access],hasMore:false}));
  render(<SupportWorkspace {...props}/>);
  const open=await screen.findByRole('button',{name:'Открыть диагностику №9'});
  fireEvent.click(open);await screen.findByText('OLD CONTEXT');denied=true;fireEvent.click(open);
  expect(await screen.findByRole('alert')).toHaveTextContent('Доступ отозван');
  expect(screen.queryByText('OLD CONTEXT')).not.toBeInTheDocument();
});

test('leaving the workspace ignores late diagnostics from the previous scope',async()=>{
  let late;
  global.fetch=jest.fn(url=>url.includes('/diagnostic')?new Promise(resolve=>{late=resolve;}):Promise.resolve(response({items:[access],hasMore:false})));
  const view=render(<SupportWorkspace {...props}/>);
  fireEvent.click(await screen.findByRole('button',{name:'Открыть диагностику №9'}));
  global.fetch=jest.fn(async()=>response({items:[],hasMore:false}));
  view.rerender(<SupportWorkspace {...props} API="/new-session"/>);
  expect(await screen.findByText(/Назначенных обращений нет/)).toBeInTheDocument();
  await act(async()=>late(response({...access,comment:'PRIVATE OLD CONTEXT',context:{}})));
  expect(screen.queryByText('PRIVATE OLD CONTEXT')).not.toBeInTheDocument();
});

 test('expired diagnostic is cleared even while the device stays open',async()=>{
  jest.useFakeTimers();
  try {
    const expiring={...access,expiresAt:new Date(Date.now()+1000).toISOString(),comment:'EXPIRED CONTEXT',context:{}};
    global.fetch=jest.fn(async url=>response(url.includes('/diagnostic')?expiring:{items:[expiring],hasMore:false}));
    render(<SupportWorkspace {...props}/>);
    await act(async()=>{});
    fireEvent.click(screen.getByRole('button',{name:'Открыть диагностику №9'}));
    await act(async()=>{});
    expect(screen.getByText('EXPIRED CONTEXT')).toBeInTheDocument();
    act(()=>jest.advanceTimersByTime(1100));
    expect(screen.queryByText('EXPIRED CONTEXT')).not.toBeInTheDocument();
    expect(screen.getByRole('alert')).toHaveTextContent('Срок доступа закончился');
  } finally {jest.useRealTimers();}
});
