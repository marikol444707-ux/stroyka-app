import {StrictMode} from 'react';
import {act,fireEvent,render,screen} from '@testing-library/react';
import SupplierConnectionCorrection from './SupplierConnectionCorrection';

const plan={id:'plan-a',companyId:2,sourceId:7,targetId:8,companyName:'Компания А',targetName:'Кабинет поставщика',
  expiresAt:'2030-01-01T12:00:00Z',retainedDocuments:{invoices:1,receipts:2,offers:0}};
const result={ok:true,planId:'plan-a',companyId:2,sourceId:7,targetId:8,relationshipStatus:'Неактивный',relationshipVersion:2};
const props={prefix:'/system/companies/2',companyId:2,supplierId:7,targetId:8,requestId:'request-a'};
const response=(body,ok=true,status=200)=>({ok,status,json:async()=>body});
beforeEach(()=>{Object.defineProperty(window,'crypto',{configurable:true,value:{randomUUID:jest.fn(()=> 'operation-a')}});});
afterEach(()=>jest.restoreAllMocks());

async function prepare(){fireEvent.click(screen.getByRole('button',{name:'Подготовить отключение'}));await screen.findByText('Компания А');}
function confirmFields(){fireEvent.change(screen.getByRole('textbox',{name:'Причина отключения'}),{target:{value:'Ошибочно выбрали покупателя'}});fireEvent.click(screen.getByRole('checkbox'));}

test('prepares the exact plan and requires reason and explicit confirmation before a single mutation',async()=>{
  let finish;const onApplied=jest.fn();
  global.fetch=jest.fn().mockResolvedValueOnce(response(plan)).mockImplementationOnce(()=>new Promise(resolve=>{finish=resolve;}));
  render(<SupplierConnectionCorrection {...props} onApplied={onApplied}/>);
  await prepare();
  expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({operationId:'operation-a'});
  const button=screen.getByRole('button',{name:'Подтвердить отключение'});expect(button).toBeDisabled();
  confirmFields();fireEvent.click(button);fireEvent.click(button);
  expect(fetch).toHaveBeenCalledTimes(2);
  expect(fetch.mock.calls[1][0]).toBe('/system/companies/2/participants/7/connection-requests/request-a/correction-plans/plan-a/confirm');
  expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({confirmed:true,reason:'Ошибочно выбрали покупателя'});
  await act(async()=>finish(response(result)));
  expect(onApplied).toHaveBeenCalledWith(result);
});

test('a used connection stays blocked and never offers a confirmation',async()=>{
  global.fetch=jest.fn().mockResolvedValue(response({detail:'Кабинет уже получил документы'},false,409));
  render(<SupplierConnectionCorrection {...props}/>);
  fireEvent.click(screen.getByRole('button',{name:'Подготовить отключение'}));
  expect(await screen.findByRole('alert')).toHaveTextContent('Кабинет уже получил документы');
  expect(screen.queryByRole('button',{name:'Подтвердить отключение'})).not.toBeInTheDocument();
});

test.each(['network','server'])('an uncertain confirmation keeps the same plan and reason for a safe retry (%s)',async kind=>{
  const onApplied=jest.fn();
  global.fetch=jest.fn().mockResolvedValueOnce(response(plan));
  if(kind==='network')global.fetch.mockRejectedValueOnce(new Error('Network failed'));
  else global.fetch.mockResolvedValueOnce(response({detail:'Synthetic server error'},false,500));
  global.fetch.mockResolvedValueOnce(response(result));
  render(<SupplierConnectionCorrection {...props} onApplied={onApplied}/>);
  await prepare();confirmFields();fireEvent.click(screen.getByRole('button',{name:'Подтвердить отключение'}));
  expect(await screen.findByRole('alert')).toHaveTextContent(kind==='network'?'Ответ сервера не получен':'Сервер не подтвердил результат');
  expect(screen.getByRole('textbox',{name:'Причина отключения'})).toBeDisabled();
  fireEvent.click(screen.getByRole('button',{name:'Повторить подтверждение'}));
  await screen.findByText('Подключение отключено.');
  expect(fetch.mock.calls[1][0]).toBe(fetch.mock.calls[2][0]);
  expect(fetch.mock.calls[1][1].body).toBe(fetch.mock.calls[2][1].body);
  expect(onApplied).toHaveBeenCalledTimes(1);
});

test('conflict discards the stale plan and requires a new review',async()=>{
  global.fetch=jest.fn().mockResolvedValueOnce(response(plan)).mockResolvedValueOnce(response({detail:'Документы изменились'},false,409));
  render(<SupplierConnectionCorrection {...props}/>);
  await prepare();confirmFields();fireEvent.click(screen.getByRole('button',{name:'Подтвердить отключение'}));
  expect(await screen.findByRole('alert')).toHaveTextContent('Документы изменились');
  expect(screen.getByRole('button',{name:'Подготовить отключение'})).toBeInTheDocument();
  expect(screen.queryByRole('button',{name:'Подтвердить отключение'})).not.toBeInTheDocument();
});

test('late confirmation from an old company cannot populate a new company or refresh it',async()=>{
  let finish;const onApplied=jest.fn();
  global.fetch=jest.fn().mockResolvedValueOnce(response(plan)).mockImplementationOnce(()=>new Promise(resolve=>{finish=resolve;}));
  const view=render(<SupplierConnectionCorrection {...props} onApplied={onApplied}/>);
  await prepare();confirmFields();fireEvent.click(screen.getByRole('button',{name:'Подтвердить отключение'}));
  view.rerender(<SupplierConnectionCorrection {...props} prefix="/system/companies/3" companyId={3} requestId="request-b" onApplied={onApplied}/>);
  expect(screen.queryByText('Компания А')).not.toBeInTheDocument();
  await act(async()=>finish(response(result)));
  expect(onApplied).not.toHaveBeenCalled();
  expect(screen.queryByText('Подключение отключено.')).not.toBeInTheDocument();
});

test('a mismatched server result never reports success',async()=>{
  const onApplied=jest.fn();
  global.fetch=jest.fn().mockResolvedValueOnce(response(plan)).mockResolvedValueOnce(response({...result,targetId:99}));
  render(<SupplierConnectionCorrection {...props} onApplied={onApplied}/>);
  await prepare();confirmFields();fireEvent.click(screen.getByRole('button',{name:'Подтвердить отключение'}));
  expect(await screen.findByRole('alert')).toHaveTextContent('не подтвердил результат');
  expect(onApplied).not.toHaveBeenCalled();
});

test('the plan loads under the application StrictMode lifecycle',async()=>{
  global.fetch=jest.fn().mockResolvedValue(response(plan));
  render(<StrictMode><SupplierConnectionCorrection {...props}/></StrictMode>);
  await prepare();expect(screen.getByRole('button',{name:'Подтвердить отключение'})).toBeDisabled();
});

test('RFQ correction shows exact affected requests and requires explicit withdrawal confirmation',async()=>{
  const previous=process.env.REACT_APP_PARTICIPANT_RFQ_CORRECTIONS_ENABLED;
  process.env.REACT_APP_PARTICIPANT_RFQ_CORRECTIONS_ENABLED='1';
  try {
    const onApplied=jest.fn();
    global.fetch=jest.fn().mockResolvedValueOnce(response({...plan,mode:'withdraw_unanswered_rfq',
      affectedRequests:[{requestId:14,recipientId:25,offerIds:[36]}],queuedNotificationCount:2}))
      .mockResolvedValueOnce(response({...result,withdrawnRequestCount:1}));
    render(<SupplierConnectionCorrection {...props} onApplied={onApplied}/>);
    fireEvent.click(screen.getByRole('button',{name:'Проверить подключение'}));
    expect(await screen.findByText('Заявка №14')).toBeInTheDocument();
    expect(screen.getByText('Только у этого поставщика. Заявки и ответы других поставщиков сохранятся.')).toBeInTheDocument();
    expect(screen.getByText(/Уже отправленные письма/)).toBeInTheDocument();
    expect(screen.getByText('Уведомлений в очереди будет отменено: 2.')).toBeInTheDocument();
    expect(fetch.mock.calls[0][0]).toContain('/rfq-correction-plans');
    fireEvent.change(screen.getByRole('textbox',{name:'Причина отключения'}),{target:{value:'Ошибочно выбрали покупателя'}});
    fireEvent.click(screen.getByRole('checkbox',{name:'Отозвать указанные заявки и отключить эту связь'}));
    fireEvent.click(screen.getByRole('button',{name:'Отозвать заявки и отключить'}));
    await screen.findByText('Подключение отключено.');
    expect(onApplied).toHaveBeenCalledWith({...result,withdrawnRequestCount:1});
  } finally {
    if(previous===undefined)delete process.env.REACT_APP_PARTICIPANT_RFQ_CORRECTIONS_ENABLED;
    else process.env.REACT_APP_PARTICIPANT_RFQ_CORRECTIONS_ENABLED=previous;
  }
});

test('RFQ mode rejects an incomplete plan instead of hiding its consequences',async()=>{
  const previous=process.env.REACT_APP_PARTICIPANT_RFQ_CORRECTIONS_ENABLED;
  process.env.REACT_APP_PARTICIPANT_RFQ_CORRECTIONS_ENABLED='1';
  try {
    global.fetch=jest.fn().mockResolvedValue(response(plan));
    render(<SupplierConnectionCorrection {...props}/>);
    fireEvent.click(screen.getByRole('button',{name:'Проверить подключение'}));
    expect(await screen.findByRole('alert')).toHaveTextContent('не подтвердил план');
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument();
  } finally {
    if(previous===undefined)delete process.env.REACT_APP_PARTICIPANT_RFQ_CORRECTIONS_ENABLED;
    else process.env.REACT_APP_PARTICIPANT_RFQ_CORRECTIONS_ENABLED=previous;
  }
});

test('RFQ success must confirm the exact number of withdrawn requests',async()=>{
  const previous=process.env.REACT_APP_PARTICIPANT_RFQ_CORRECTIONS_ENABLED;
  process.env.REACT_APP_PARTICIPANT_RFQ_CORRECTIONS_ENABLED='1';
  try {
    const onApplied=jest.fn();
    global.fetch=jest.fn().mockResolvedValueOnce(response({...plan,mode:'withdraw_unanswered_rfq',
      affectedRequests:[{requestId:14,recipientId:25,offerIds:[36]}],queuedNotificationCount:0}))
      .mockResolvedValueOnce(response({...result,withdrawnRequestCount:0}));
    render(<SupplierConnectionCorrection {...props} onApplied={onApplied}/>);
    fireEvent.click(screen.getByRole('button',{name:'Проверить подключение'}));
    await screen.findByText('Заявка №14');confirmFields();
    fireEvent.click(screen.getByRole('button',{name:'Отозвать заявки и отключить'}));
    expect(await screen.findByRole('alert')).toHaveTextContent('не подтвердил результат');
    expect(onApplied).not.toHaveBeenCalled();
    expect(screen.getByRole('button',{name:'Повторить подтверждение'})).toBeInTheDocument();
  } finally {
    if(previous===undefined)delete process.env.REACT_APP_PARTICIPANT_RFQ_CORRECTIONS_ENABLED;
    else process.env.REACT_APP_PARTICIPANT_RFQ_CORRECTIONS_ENABLED=previous;
  }
});

const quotePlan={...plan,mode:'reject_received_quotes',affectedRequests:[{requestId:14,recipientId:25,offerIds:[36]}],
  affectedOffers:[{offerId:36,statusBefore:'Получено',statusAfter:'Отклонено'}],queuedNotificationCount:0,preservedQuoteFileCount:1};
async function withQuoteMode(check){
  const previous=process.env.REACT_APP_PARTICIPANT_QUOTE_CORRECTIONS_ENABLED;
  process.env.REACT_APP_PARTICIPANT_QUOTE_CORRECTIONS_ENABLED='1';
  try{await check();}finally{
    if(previous===undefined)delete process.env.REACT_APP_PARTICIPANT_QUOTE_CORRECTIONS_ENABLED;
    else process.env.REACT_APP_PARTICIPANT_QUOTE_CORRECTIONS_ENABLED=previous;
  }
}

test('received quote correction shows rejection and preservation before explicit confirmation',async()=>withQuoteMode(async()=>{
  const onApplied=jest.fn();
  const completed={...result,withdrawnRequestCount:1,rejectedQuoteCount:1};
  global.fetch=jest.fn().mockResolvedValueOnce(response(quotePlan)).mockResolvedValueOnce(response(completed));
  render(<SupplierConnectionCorrection {...props} onApplied={onApplied}/>);
  fireEvent.click(screen.getByRole('button',{name:'Проверить подключение'}));
  expect(await screen.findByText('КП №36 — будет отклонено')).toBeInTheDocument();
  expect(screen.getByText('Цены, состав, реквизиты и оригиналы КП сохранятся в архиве компании.')).toBeInTheDocument();
  expect(fetch.mock.calls[0][0]).toContain('/quote-correction-plans');
  fireEvent.change(screen.getByRole('textbox',{name:'Причина отключения'}),{target:{value:'Ошибочно подключили кабинет поставщика'}});
  fireEvent.click(screen.getByRole('checkbox',{name:'Отклонить указанные КП и отключить эту связь'}));
  fireEvent.click(screen.getByRole('button',{name:'Отклонить КП и отключить'}));
  await screen.findByText('Подключение отключено.');expect(onApplied).toHaveBeenCalledWith(completed);
}));

test('a quote plan cannot omit the consequences for one of its offers',async()=>withQuoteMode(async()=>{
  global.fetch=jest.fn().mockResolvedValue(response({...quotePlan,affectedOffers:[]}));
  render(<SupplierConnectionCorrection {...props}/>);
  fireEvent.click(screen.getByRole('button',{name:'Проверить подключение'}));
  expect(await screen.findByRole('alert')).toHaveTextContent('не подтвердил план');
  expect(screen.queryByRole('checkbox')).not.toBeInTheDocument();
}));

test('quote rejection requires an exact confirmed count in the result',async()=>withQuoteMode(async()=>{
  const onApplied=jest.fn();
  global.fetch=jest.fn().mockResolvedValueOnce(response(quotePlan))
    .mockResolvedValueOnce(response({...result,withdrawnRequestCount:1,rejectedQuoteCount:0}));
  render(<SupplierConnectionCorrection {...props} onApplied={onApplied}/>);
  fireEvent.click(screen.getByRole('button',{name:'Проверить подключение'}));await screen.findByText('КП №36 — будет отклонено');
  confirmFields();fireEvent.click(screen.getByRole('button',{name:'Отклонить КП и отключить'}));
  expect(await screen.findByRole('alert')).toHaveTextContent('не подтвердил результат');expect(onApplied).not.toHaveBeenCalled();
}));
