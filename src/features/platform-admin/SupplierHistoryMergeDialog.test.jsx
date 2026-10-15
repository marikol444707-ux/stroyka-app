import {fireEvent,render,screen,waitFor} from '@testing-library/react';
import SupplierHistoryMergeDialog from './SupplierHistoryMergeDialog';

const plan={id:'synthetic-plan',sourceId:7,targetId:8,newAccess:{invoices:[101],offers:[],files:[]},stillClosed:{invoices:[],offers:[]},affected:{warehouse_invoices:[102]}};
const props={prefix:'/system/companies/2',sourceId:7,targetId:8,sourceName:'Из накладной',targetName:'Кабинет',onClose:jest.fn(),onDone:jest.fn()};
const response=body=>({ok:true,json:async()=>body});
beforeEach(()=>jest.clearAllMocks());
afterEach(()=>jest.restoreAllMocks());

test('requires consequences, ownership review and reason before the exact company command',async()=>{
  global.fetch=jest.fn().mockResolvedValueOnce(response(plan)).mockResolvedValueOnce(response({ok:true,sourceId:7,targetId:8}));
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
  expect(fetch.mock.calls[1][0]).toBe('/system/companies/2/participants/7/history-merge-plans/synthetic-plan/confirm');
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

test('closing a company panel ignores a late review response',async()=>{
  let finish;global.fetch=jest.fn(()=>new Promise(resolve=>{finish=resolve;}));
  const view=render(<SupplierHistoryMergeDialog {...props}/>);
  fireEvent.click(screen.getByRole('button',{name:'Проверить последствия'}));view.unmount();
  finish(response(plan));await waitFor(()=>expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  expect(props.onDone).not.toHaveBeenCalled();
});
