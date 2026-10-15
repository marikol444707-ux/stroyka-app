import {act,fireEvent,render,screen,within} from '@testing-library/react';
import SupplierCorrectionPreview from './SupplierCorrectionPreview';

const data={companyName:'Компания А',sourceName:'Карточка из накладной',targetName:'Кабинет поставщика',
  connectedAt:'2026-10-13T09:00:00Z',summary:{invoices:{total:2,afterConnection:1,undated:0},
    receipts:{total:1,afterConnection:0,undated:0},offers:{total:0,afterConnection:0,undated:0},
    contracts:{total:null,afterConnection:null,undated:null},files:{total:0,afterConnection:0,undated:0}},
  items:[{id:101,createdAfterConnection:true,currentSupplierAccess:'available'}],hasMore:true,
  blockers:[{code:'HISTORY_SCHEMA_REVIEW_REQUIRED',message:'Часть реестров недоступна.'}],canApply:false};
const response=body=>({ok:true,json:async()=>body});
const props={prefix:'/system/companies/2',supplierId:7,requestId:'synthetic-request',onClose:jest.fn()};
afterEach(()=>jest.restoreAllMocks());

test('shows company, consequences and documents with no misleading confirmation',async()=>{
  global.fetch=jest.fn().mockResolvedValue(response(data));
  render(<SupplierCorrectionPreview {...props}/>);
  expect(await screen.findByText('Компания А')).toBeInTheDocument();
  expect(screen.getByText('Создан после подключения')).toBeInTheDocument();
  expect(screen.getByText('Доступ сейчас разрешён')).toBeInTheDocument();
  expect(screen.getByText(/Отключение связи само по себе не закрывает/)).toBeInTheDocument();
  expect(screen.getByText('Часть реестров недоступна.')).toBeInTheDocument();
  expect(screen.getByRole('button',{name:'Договоры: нужна проверка'})).toBeDisabled();
  expect(screen.queryByRole('button',{name:/Подтвердить|Исправить|Отключить/})).not.toBeInTheDocument();
  expect(fetch.mock.calls[0][1].cache).toBe('no-store');
});

test('pages five records and resets the page on a new category',async()=>{
  global.fetch=jest.fn().mockResolvedValue(response(data));
  render(<SupplierCorrectionPreview {...props}/>);
  fireEvent.click(await screen.findByRole('button',{name:'Далее'}));
  await screen.findByText('Компания А');
  expect(fetch.mock.calls.at(-1)[0]).toContain('offset=5');
  fireEvent.click(screen.getByRole('button',{name:'Накладные: 1'}));
  await screen.findByText('Компания А');
  expect(fetch.mock.calls.at(-1)[0]).toContain('category=receipts');
  expect(fetch.mock.calls.at(-1)[0]).toContain('offset=0');
  expect(fetch.mock.calls.at(-1)[0]).toContain('limit=5');
});

test('late old company or request response never replaces current review',async()=>{
  let finish;
  global.fetch=jest.fn().mockImplementationOnce(()=>new Promise(resolve=>{finish=resolve;}))
    .mockResolvedValue(response({...data,companyName:'Компания Б',sourceName:'Другая карточка'}));
  const view=render(<SupplierCorrectionPreview {...props}/>);
  view.rerender(<SupplierCorrectionPreview {...props} prefix="/system/companies/3" requestId="other-request"/>);
  expect(await screen.findByText('Компания Б')).toBeInTheDocument();
  await act(async()=>finish(response(data)));
  expect(screen.queryByText('Компания А')).not.toBeInTheDocument();
  expect(screen.queryByText('Карточка из накладной')).not.toBeInTheDocument();
});

test('failed preview stays visible and retry does not imply empty history',async()=>{
  global.fetch=jest.fn().mockResolvedValueOnce({ok:false,json:async()=>({detail:'Подключение недоступно'})})
    .mockResolvedValue(response({...data,items:[],hasMore:false}));
  render(<SupplierCorrectionPreview {...props}/>);
  expect(await screen.findByRole('alert')).toHaveTextContent('Подключение недоступно');
  expect(screen.queryByText('В этой группе документов нет.')).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button',{name:'Повторить проверку'}));
  expect(await screen.findByText('В этой группе документов нет.')).toBeInTheDocument();
});

test('unknown creation date is not reported as an old document',async()=>{
  global.fetch=jest.fn().mockResolvedValue(response({...data,items:[{id:101,createdAfterConnection:null,currentSupplierAccess:'needs_check'}]}));
  render(<SupplierCorrectionPreview {...props}/>);
  expect(await screen.findByText('Дата создания не подтверждена')).toBeInTheDocument();
  expect(screen.getByText('Доступ проверяется в карточке документа')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button',{name:'Скрыть последствия'}));
  expect(props.onClose).toHaveBeenCalledTimes(1);
});

test('dialog keeps keyboard focus inside, closes on Escape and restores the caller',async()=>{
  global.fetch=jest.fn().mockResolvedValue(response(data));
  const onClose=jest.fn();
  const button=document.createElement('button');document.body.append(button);button.focus();
  const view=render(<SupplierCorrectionPreview {...props} onClose={onClose}/>);
  const dialog=screen.getByRole('dialog',{name:'Последствия подключения'});
  expect(dialog).toHaveFocus();
  expect(document.body.style.overflow).toBe('hidden');
  fireEvent.keyDown(dialog,{key:'Tab'});
  expect(screen.getByRole('button',{name:'Скрыть последствия'})).toHaveFocus();
  await screen.findByText('Компания А');
  fireEvent.keyDown(dialog,{key:'Escape'});
  expect(onClose).toHaveBeenCalledTimes(1);
  view.unmount();
  expect(button).toHaveFocus();
  expect(document.body.style.overflow).not.toBe('hidden');button.remove();
});

test('Escape and Tab still work when a loading page drops focus outside the dialog',async()=>{
  global.fetch=jest.fn().mockResolvedValue(response(data));
  const onClose=jest.fn();
  render(<SupplierCorrectionPreview {...props} onClose={onClose}/>);
  await screen.findByText('Компания А');
  const outside=document.createElement('button');document.body.append(outside);
  try {
    outside.focus();
    fireEvent.keyDown(outside,{key:'Escape'});
    expect(onClose).toHaveBeenCalledTimes(1);
    fireEvent.keyDown(outside,{key:'Tab'});
    expect(screen.getByRole('button',{name:'Скрыть последствия'})).toHaveFocus();
  } finally {outside.remove();}
});

test('a pending correction cannot be closed or paged away and refreshes the list only after completion is acknowledged',async()=>{
  const previous=process.env.REACT_APP_PARTICIPANT_CORRECTIONS_ENABLED;
  process.env.REACT_APP_PARTICIPANT_CORRECTIONS_ENABLED='1';
  let finish;const onClose=jest.fn(),onCompleted=jest.fn();
  const plan={id:'plan-a',companyId:2,sourceId:7,targetId:8,companyName:'Компания А',targetName:'Кабинет поставщика',expiresAt:'2030-01-01T12:00:00Z',retainedDocuments:{invoices:2,receipts:1,offers:0}};
  try {
    Object.defineProperty(window,'crypto',{configurable:true,value:{randomUUID:jest.fn(()=> 'operation-a')}});
    global.fetch=jest.fn().mockResolvedValueOnce(response({...data,companyId:2,targetId:8}))
      .mockResolvedValueOnce(response(plan)).mockImplementationOnce(()=>new Promise(resolve=>{finish=resolve;}));
    render(<SupplierCorrectionPreview {...props} onClose={onClose} onCompleted={onCompleted}/>);
    fireEvent.click(await screen.findByRole('button',{name:'Подготовить отключение'}));
    const command=within(screen.getByRole('region',{name:'Отключение неиспользованной связи'}));
    await command.findByText('Компания А');
    const closeButton=screen.getByRole('button',{name:'Скрыть последствия'});
    closeButton.focus();
    fireEvent.keyDown(closeButton,{key:'Tab',shiftKey:true});
    expect(command.getByRole('checkbox')).toHaveFocus();
    fireEvent.change(command.getByRole('textbox',{name:'Причина отключения'}),{target:{value:'Ошибочно выбрали покупателя'}});
    fireEvent.click(command.getByRole('checkbox'));
    fireEvent.click(command.getByRole('button',{name:'Подтвердить отключение'}));
    expect(screen.getByRole('button',{name:'Скрыть последствия'})).toBeDisabled();
    expect(screen.getByRole('button',{name:'Накладные: 1'})).toBeDisabled();
    fireEvent.keyDown(document,{key:'Escape'});expect(onClose).not.toHaveBeenCalled();
    await act(async()=>finish(response({ok:true,planId:'plan-a',companyId:2,sourceId:7,targetId:8,relationshipStatus:'Неактивный',relationshipVersion:2})));
    expect(await screen.findByRole('status')).toHaveTextContent('Подключение отключено');
    expect(onCompleted).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button',{name:'Готово'}));
    expect(onClose).toHaveBeenCalledTimes(1);expect(onCompleted).toHaveBeenCalledTimes(1);
  } finally {
    if(previous===undefined)delete process.env.REACT_APP_PARTICIPANT_CORRECTIONS_ENABLED;
    else process.env.REACT_APP_PARTICIPANT_CORRECTIONS_ENABLED=previous;
  }
});

test('issued history distinguishes original card from cabinet and hides inapplicable correction commands',async()=>{
  const previous=process.env.REACT_APP_PARTICIPANT_CORRECTIONS_ENABLED;
  process.env.REACT_APP_PARTICIPANT_CORRECTIONS_ENABLED='1';
  try {
    global.fetch=jest.fn().mockResolvedValue(response({...data,financialReview:{state:'review_required',
      source:{orders:0,invoices:2,deliveries:0,receipts:1,contracts:0},connected:{orders:1,invoices:1,deliveries:1,receipts:0,contracts:0}},
      items:[{...data.items[0],context:{supplierCard:'connected',requestId:14,offerId:36,linksConfirmed:true}}]}));
    render(<SupplierCorrectionPreview {...props}/>);
    expect(await screen.findByText('Нужен разбор оформленных документов')).toBeInTheDocument();
    fireEvent.click(screen.getByText('Документы по карточкам'));
    const review=within(screen.getByRole('region',{name:'Оформленные документы'}));
    expect(review.getByText('Исходная карточка')).toBeInTheDocument();
    expect(review.getByText('Подключённый кабинет')).toBeInTheDocument();
    expect(screen.getByText('Заявка №14 · КП №36')).toBeInTheDocument();
    expect(screen.queryByRole('button',{name:'Подготовить отключение'})).not.toBeInTheDocument();
    expect(fetch).toHaveBeenCalledTimes(1);
  }finally{if(previous===undefined)delete process.env.REACT_APP_PARTICIPANT_CORRECTIONS_ENABLED;else process.env.REACT_APP_PARTICIPANT_CORRECTIONS_ENABLED=previous;}
});

test('incomplete financial review and mismatched document links are never shown as a clear archive',async()=>{
  global.fetch=jest.fn().mockResolvedValue(response({...data,financialReview:{state:'needs_check',
    source:{orders:0,invoices:0,deliveries:null,receipts:0,contracts:0},connected:{orders:0,invoices:0,deliveries:null,receipts:0,contracts:0}},
    items:[{...data.items[0],context:{supplierCard:'source',requestId:null,offerId:null,linksConfirmed:false}}]}));
  render(<SupplierCorrectionPreview {...props}/>);
  expect(await screen.findByText('Часть документов не удалось проверить')).toBeInTheDocument();
  expect(screen.getByText('Связи документа требуют проверки')).toBeInTheDocument();
  expect(screen.queryByText(/Заявка №/)).not.toBeInTheDocument();
});

test('an original card invoice allows checking an otherwise empty connected cabinet',async()=>{
  const previous=process.env.REACT_APP_PARTICIPANT_CORRECTIONS_ENABLED;
  process.env.REACT_APP_PARTICIPANT_CORRECTIONS_ENABLED='1';
  try {
    global.fetch=jest.fn().mockResolvedValue(response({...data,financialReview:{state:'clear',
      source:{orders:0,invoices:2,deliveries:0,receipts:0,contracts:0},connected:{orders:0,invoices:0,deliveries:0,receipts:0,contracts:0}}}));
    render(<SupplierCorrectionPreview {...props}/>);
    expect(await screen.findByRole('button',{name:'Подготовить отключение'})).toBeInTheDocument();
    expect(screen.getByText('Заказов, счетов и поставок у кабинета нет')).toBeInTheDocument();
  }finally{if(previous===undefined)delete process.env.REACT_APP_PARTICIPANT_CORRECTIONS_ENABLED;else process.env.REACT_APP_PARTICIPANT_CORRECTIONS_ENABLED=previous;}
});

test('malformed or inconsistent financial counts do not expose a correction command',async()=>{
  const previous=process.env.REACT_APP_PARTICIPANT_CORRECTIONS_ENABLED;
  process.env.REACT_APP_PARTICIPANT_CORRECTIONS_ENABLED='1';
  try {
    global.fetch=jest.fn().mockResolvedValue(response({...data,financialReview:{state:'clear',source:{},connected:{invoices:1}}}));
    render(<SupplierCorrectionPreview {...props}/>);
    expect(await screen.findByText('Часть документов не удалось проверить')).toBeInTheDocument();
    expect(screen.queryByRole('button',{name:'Подготовить отключение'})).not.toBeInTheDocument();
  }finally{if(previous===undefined)delete process.env.REACT_APP_PARTICIPANT_CORRECTIONS_ENABLED;else process.env.REACT_APP_PARTICIPANT_CORRECTIONS_ENABLED=previous;}
});

test('the separate issued access flag enables preserving correction and reports closure without cancelling orders',async()=>{
  const names=['REACT_APP_PARTICIPANT_CORRECTIONS_ENABLED','REACT_APP_PARTICIPANT_ISSUED_ACCESS_CORRECTIONS_ENABLED'];
  const previous=names.map(name=>process.env[name]);names.forEach(name=>{process.env[name]='1';});
  try {
    Object.defineProperty(window,'crypto',{configurable:true,value:{randomUUID:jest.fn(()=> 'operation-issued')}});
    const plan={id:'issued-plan',companyId:2,sourceId:7,targetId:8,companyName:'Компания А',targetName:'Кабинет поставщика',
      expiresAt:'2030-01-01T12:00:00Z',mode:'revoke_issued_access',retainedDocuments:{invoices:0,receipts:0,offers:0},
      affectedRequests:[{requestId:14,recipientId:25,offerIds:[36]}],affectedOffers:[{offerId:36,statusBefore:'Утверждено',statusAfter:'Утверждено'}],
      queuedNotificationCount:0,preservedIssuedDocuments:[{kind:'offer',id:36},{kind:'invoice',id:101}],preservedIssuedFileCount:1};
    global.fetch=jest.fn().mockResolvedValueOnce(response({...data,companyId:2,targetId:8,
      financialReview:{state:'review_required',source:{orders:0,invoices:0,deliveries:0,receipts:0,contracts:0},
        connected:{orders:1,invoices:1,deliveries:0,receipts:0,contracts:0}}}))
      .mockResolvedValueOnce(response(plan)).mockResolvedValueOnce(response({ok:true,planId:'issued-plan',companyId:2,sourceId:7,targetId:8,
        relationshipStatus:'Неактивный',relationshipVersion:2,revokedRequestCount:1,preservedIssuedCounts:{offers:1,invoices:1,deliveries:0,receipts:0}}));
    render(<SupplierCorrectionPreview {...props}/>);
    fireEvent.click(await screen.findByRole('button',{name:'Проверить подключение'}));
    const command=within(screen.getByRole('region',{name:'Исправление подключения'}));
    await command.findByText('Счёт №101');
    fireEvent.change(command.getByRole('textbox',{name:'Причина отключения'}),{target:{value:'Подключили ошибочный кабинет поставщика'}});
    fireEvent.click(command.getByRole('checkbox'));
    fireEvent.click(command.getByRole('button',{name:'Закрыть доступ и отключить связь'}));
    expect(await screen.findByText('Доступ к заявкам закрыт: 1. Статусы документов, оплаты и складские записи сохранены.')).toBeInTheDocument();
    expect(screen.queryByText(/Отклонено КП/)).not.toBeInTheDocument();
  }finally{names.forEach((name,i)=>{if(previous[i]===undefined)delete process.env[name];else process.env[name]=previous[i];});}
});

test('the separate invoice access flag handles direct invoices and reports preserved business records',async()=>{
  const names=['REACT_APP_PARTICIPANT_CORRECTIONS_ENABLED','REACT_APP_PARTICIPANT_INVOICE_ACCESS_CORRECTIONS_ENABLED'];
  const previous=names.map(name=>process.env[name]);names.forEach(name=>{process.env[name]='1';});
  try {
    Object.defineProperty(window,'crypto',{configurable:true,value:{randomUUID:jest.fn(()=> 'operation-issued')}});
    const plan={id:'issued-plan',companyId:2,sourceId:7,targetId:8,companyName:'Компания А',targetName:'Кабинет поставщика',
      expiresAt:'2030-01-01T12:00:00Z',mode:'revoke_invoice_access',retainedDocuments:{invoices:0,receipts:0,offers:0},
      affectedRequests:[],affectedOffers:[],
      queuedNotificationCount:0,preservedIssuedDocuments:[{kind:'invoice',id:101}],preservedIssuedFileCount:1};
    global.fetch=jest.fn().mockResolvedValueOnce(response({...data,companyId:2,targetId:8,
      financialReview:{state:'review_required',source:{orders:0,invoices:0,deliveries:0,receipts:0,contracts:0},
        connected:{orders:1,invoices:1,deliveries:0,receipts:0,contracts:0}}}))
      .mockResolvedValueOnce(response(plan)).mockResolvedValueOnce(response({ok:true,planId:'issued-plan',companyId:2,sourceId:7,targetId:8,
        relationshipStatus:'Неактивный',relationshipVersion:2,revokedRequestCount:0,preservedIssuedCounts:{offers:0,invoices:1,deliveries:0,receipts:0}}));
    render(<SupplierCorrectionPreview {...props}/>);
    fireEvent.click(await screen.findByRole('button',{name:'Проверить подключение'}));
    const command=within(screen.getByRole('region',{name:'Исправление подключения'}));
    await command.findByText('Счёт №101');
    fireEvent.change(command.getByRole('textbox',{name:'Причина отключения'}),{target:{value:'Подключили ошибочный кабинет поставщика'}});
    fireEvent.click(command.getByRole('checkbox'));
    fireEvent.click(command.getByRole('button',{name:'Закрыть доступ и отключить связь'}));
    expect(await screen.findByText('Доступ к счетам закрыт: 1. Статусы документов, оплаты и складские записи сохранены.')).toBeInTheDocument();
    expect(screen.queryByText(/Отклонено КП/)).not.toBeInTheDocument();
  }finally{names.forEach((name,i)=>{if(previous[i]===undefined)delete process.env[name];else process.env[name]=previous[i];});}
});
