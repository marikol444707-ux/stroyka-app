import {fireEvent,render,screen,waitFor} from '@testing-library/react';
import SupplierHistoryMergeDialog from './SupplierHistoryMergeDialog';

const plan={id:'00000000-0000-4000-8000-000000000001',companyId:2,sourceId:7,targetId:8,
  expiresAt:'2099-01-01T00:00:00Z',newAccess:{invoices:[101],offers:[],files:[],deliveries:[],claims:[]},
  stillClosed:{invoices:[],offers:[]},affected:{warehouse_invoices:[102]}};
const result={ok:true,planId:plan.id,companyId:2,sourceId:7,targetId:8};
const props={prefix:'/system/companies/2',sourceId:7,targetId:8,sourceName:'Из накладной',targetName:'Кабинет',onClose:jest.fn(),onDone:jest.fn()};
const response=body=>({ok:true,json:async()=>body});
beforeEach(()=>jest.clearAllMocks());
afterEach(()=>jest.restoreAllMocks());

test('requires consequences, ownership review and reason before the exact company command',async()=>{
  global.fetch=jest.fn().mockResolvedValueOnce(response(plan)).mockResolvedValueOnce(response(result));
  render(<SupplierHistoryMergeDialog {...props}/>);
  fireEvent.click(screen.getByRole('button',{name:'Проверить последствия'}));
  const confirm=await screen.findByRole('button',{name:'Подтвердить объединение'});
  expect(screen.getByText('Накладные: #102')).toBeInTheDocument();
  expect(confirm).toBeDisabled();
  fireEvent.click(screen.getByRole('checkbox'));
  expect(confirm).toBeDisabled();
  fireEvent.change(screen.getByRole('textbox',{name:'Основание объединения'}),{target:{value:'Проверено юрлицо по подписанным документам'}});
  fireEvent.click(confirm);fireEvent.click(confirm);
  expect(await screen.findByRole('status')).toHaveTextContent('Карточки объединены');
  expect(fetch).toHaveBeenCalledTimes(2);
  expect(fetch.mock.calls[1][0]).toBe('/system/companies/2/participants/7/history-merge-plans/'+plan.id+'/confirm');
  fireEvent.click(screen.getByRole('button',{name:'Закрыть'}));expect(props.onDone).toHaveBeenCalled();
  props.onDone.mockClear();
  fireEvent.keyDown(screen.getByRole('dialog'),{key:'Escape'});
  expect(props.onDone).toHaveBeenCalledTimes(1);
  expect(props.onClose).not.toHaveBeenCalled();
});

test('a stale plan requires a new review instead of repeating the grant',async()=>{
  global.fetch=jest.fn().mockResolvedValueOnce(response(plan)).mockResolvedValueOnce({ok:false,status:409,json:async()=>({detail:'Документы изменились'})});
  render(<SupplierHistoryMergeDialog {...props}/>);
  fireEvent.click(screen.getByRole('button',{name:'Проверить последствия'}));
  await screen.findByRole('checkbox');fireEvent.click(screen.getByRole('checkbox'));
  fireEvent.change(screen.getByRole('textbox'),{target:{value:'Проверено по исходным документам'}});
  fireEvent.click(screen.getByRole('button',{name:'Подтвердить объединение'}));
  expect(await screen.findByRole('alert')).toHaveTextContent('Документы изменились');
  expect(screen.queryByRole('button',{name:'Подтвердить объединение'})).not.toBeInTheDocument();
  expect(screen.getByRole('button',{name:'Проверить последствия'})).toBeEnabled();
});

test.each([401,403,404])('clears disclosed history and consent after access is rejected with %s',async status=>{
  global.fetch=jest.fn().mockResolvedValueOnce(response(plan))
    .mockResolvedValueOnce({ok:false,status,json:async()=>({detail:'План недоступен'})})
    .mockResolvedValueOnce(response({...plan,id:'00000000-0000-4000-8000-000000000002'}));
  render(<SupplierHistoryMergeDialog {...props}/>);
  fireEvent.click(screen.getByRole('button',{name:'Проверить последствия'}));
  fireEvent.click(await screen.findByRole('checkbox'));
  fireEvent.change(screen.getByRole('textbox'),{target:{value:'Проверено по исходным документам'}});
  fireEvent.click(screen.getByRole('button',{name:'Подтвердить объединение'}));
  expect(await screen.findByRole('alert')).toHaveTextContent('План недоступен');
  expect(screen.queryByText('Накладные: #102')).not.toBeInTheDocument();
  expect(screen.queryByRole('checkbox')).not.toBeInTheDocument();
  expect(screen.queryByRole('button',{name:'Подтвердить объединение'})).not.toBeInTheDocument();
  expect(props.onDone).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button',{name:'Проверить последствия'}));
  expect(await screen.findByRole('checkbox')).not.toBeChecked();
  expect(screen.getByRole('button',{name:'Подтвердить объединение'})).toBeDisabled();
  expect(fetch.mock.calls[2][0]).toBe('/system/companies/2/participants/7/history-merge-plans');
});

test.each(['network','server'])('keeps the exact plan for a retry after an uncertain %s result',async failure=>{
  global.fetch=jest.fn().mockResolvedValueOnce(response(plan));
  if(failure==='network')fetch.mockRejectedValueOnce(new Error('Связь прервана'));
  else fetch.mockResolvedValueOnce({ok:false,status:503,json:async()=>({detail:'Сервис временно недоступен'})});
  fetch.mockResolvedValueOnce(response(result));
  render(<SupplierHistoryMergeDialog {...props}/>);
  fireEvent.click(screen.getByRole('button',{name:'Проверить последствия'}));
  fireEvent.click(await screen.findByRole('checkbox'));
  fireEvent.change(screen.getByRole('textbox'),{target:{value:'Проверено по исходным документам'}});
  fireEvent.click(screen.getByRole('button',{name:'Подтвердить объединение'}));
  await screen.findByRole('alert');
  expect(screen.getByRole('checkbox')).toBeChecked();
  fireEvent.click(screen.getByRole('button',{name:'Подтвердить объединение'}));
  expect(await screen.findByRole('status')).toHaveTextContent('Карточки объединены');
  expect(fetch.mock.calls[2]).toEqual(fetch.mock.calls[1]);
});

test('closing a company panel ignores a late review response',async()=>{
  let finish;global.fetch=jest.fn(()=>new Promise(resolve=>{finish=resolve;}));
  const view=render(<SupplierHistoryMergeDialog {...props}/>);
  fireEvent.click(screen.getByRole('button',{name:'Проверить последствия'}));view.unmount();
  finish(response(plan));await waitFor(()=>expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  expect(props.onDone).not.toHaveBeenCalled();
});

test.each([
  ['missing closed records', {...plan,stillClosed:undefined}],
  ['missing closed offers', {...plan,stillClosed:{invoices:[]}}],
  ['missing invoice consequences', {...plan,newAccess:{...plan.newAccess,invoices:undefined}}],
  ['missing delivery consequences', {...plan,newAccess:{...plan.newAccess,deliveries:undefined}}],
  ['wrong record collection', {...plan,newAccess:{...plan.newAccess,files:'101'}}],
  ['invalid document ID', {...plan,newAccess:{...plan.newAccess,invoices:[null]}}],
  ['invalid affected records', {...plan,affected:{warehouse_invoices:102}}],
  ['missing affected records', {...plan,affected:undefined}],
  ['another company', {...plan,companyId:3}],
  ['another source', {...plan,sourceId:17}],
  ['another target', {...plan,targetId:18}],
  ['unsafe plan path', {...plan,id:'../another-plan'}],
  ['invalid expiry', {...plan,expiresAt:'unknown'}],
  ['expired plan', {...plan,expiresAt:'2000-01-01T00:00:00Z'}],
])('rejects %s without displaying or confirming an incomplete plan',async(_name,invalid)=>{
  global.fetch=jest.fn().mockResolvedValueOnce(response(invalid)).mockResolvedValueOnce(response(plan));
  render(<SupplierHistoryMergeDialog {...props}/>);
  fireEvent.click(screen.getByRole('button',{name:'Проверить последствия'}));
  expect(await screen.findByRole('alert')).toHaveTextContent('Результат проверки неполный');
  expect(screen.queryByRole('button',{name:'Подтвердить объединение'})).not.toBeInTheDocument();
  expect(screen.queryByRole('checkbox')).not.toBeInTheDocument();
  expect(fetch).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByRole('button',{name:'Проверить последствия'}));
  expect(await screen.findByRole('checkbox')).toBeInTheDocument();
});

test.each([
  ['another company', {...result,companyId:3}],
  ['another plan', {...result,planId:'00000000-0000-4000-8000-000000000002'}],
  ['missing plan identity', {...result,planId:undefined}],
  ['non-boolean success', {...result,ok:'true'}],
])('does not report a successful merge for %s',async(_name,invalid)=>{
  global.fetch=jest.fn().mockResolvedValueOnce(response(plan)).mockResolvedValueOnce(response(invalid));
  render(<SupplierHistoryMergeDialog {...props}/>);
  fireEvent.click(screen.getByRole('button',{name:'Проверить последствия'}));
  fireEvent.click(await screen.findByRole('checkbox'));
  fireEvent.change(screen.getByRole('textbox'),{target:{value:'Проверены исходные документы'}});
  fireEvent.click(screen.getByRole('button',{name:'Подтвердить объединение'}));
  expect(await screen.findByRole('alert')).toHaveTextContent('Проверьте результат объединения');
  expect(screen.queryByRole('status')).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button',{name:'Закрыть'}));
  expect(props.onDone).not.toHaveBeenCalled();
  expect(props.onClose).toHaveBeenCalledTimes(1);
});
