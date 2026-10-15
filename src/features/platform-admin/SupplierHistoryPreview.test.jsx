import {act,fireEvent,render,screen} from '@testing-library/react';
import SupplierHistoryPreview from './SupplierHistoryPreview';

const data={sourceName:'Карточка из накладной',targetName:'Кабинет поставщика',
  summary:{invoices:27,receipts:1,offers:0,contracts:0,files:0},
  items:[{id:101,currentSupplierAccess:'unavailable'}],hasMore:true,canApply:false};
const response=body=>({ok:true,json:async()=>body});
afterEach(()=>jest.restoreAllMocks());

test('shows exact company history and current access with paging, without a grant button',async()=>{
  global.fetch=jest.fn().mockResolvedValueOnce(response(data)).mockResolvedValueOnce(response({...data,items:[],hasMore:false}));
  render(<SupplierHistoryPreview prefix="/system/companies/2" sourceId={7} targetId={8}/>);
  expect(await screen.findByText('Сейчас недоступно поставщику')).toBeInTheDocument();
  expect(screen.queryByRole('button',{name:/Подтвердить|Объединить|Выдать доступ/})).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button',{name:'Далее'}));
  expect(await screen.findByText('В этой группе документов нет.')).toBeInTheDocument();
  expect(fetch.mock.calls.at(-1)[0]).toContain('offset=5');
  expect(fetch.mock.calls.at(-1)[0]).toContain('limit=5');
  expect(fetch.mock.calls.at(-1)[0]).toContain('targetSupplierId=8');
});

test('a late old company reply cannot populate another company history',async()=>{
  let finish;
  global.fetch=jest.fn().mockImplementationOnce(()=>new Promise(resolve=>{finish=resolve;}))
    .mockResolvedValue(response({...data,sourceName:'Карточка другой компании',items:[]}));
  const view=render(<SupplierHistoryPreview prefix="/system/companies/2" sourceId={7} targetId={8}/>);
  view.rerender(<SupplierHistoryPreview prefix="/system/companies/3" sourceId={9} targetId={10}/>);
  expect(await screen.findByText('Карточка другой компании')).toBeInTheDocument();
  await act(async()=>finish(response(data)));
  expect(screen.queryByText('Карточка из накладной')).not.toBeInTheDocument();
});

test('failed history is not an empty success; switching document kind resets pagination',async()=>{
  global.fetch=jest.fn().mockResolvedValueOnce(response(data))
    .mockResolvedValueOnce(response(data)).mockResolvedValueOnce({ok:false,json:async()=>({detail:'История недоступна'})});
  render(<SupplierHistoryPreview prefix="/system/companies/2" sourceId={7} targetId={8}/>);
  fireEvent.click(await screen.findByRole('button',{name:'Далее'}));
  await screen.findByText('Сейчас недоступно поставщику');
  fireEvent.click(screen.getByRole('button',{name:'Накладные: 1'}));
  expect(await screen.findByRole('alert')).toHaveTextContent('История недоступна');
  expect(fetch.mock.calls.at(-1)[0]).toContain('offset=0');
  expect(fetch.mock.calls.at(-1)[0]).toContain('category=receipts');
  expect(screen.queryByText('В этой группе документов нет.')).not.toBeInTheDocument();
});
