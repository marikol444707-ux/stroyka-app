import {fireEvent,render,screen,waitFor} from '@testing-library/react';
import SupplierDuplicateMerge from './SupplierDuplicateMerge';

const props={prefix:'/system/companies/2',source:{id:7,name:'Из накладной'},btnG:{},btnO:{},inp:{},onDone:jest.fn(),onClose:jest.fn()};
const response=body=>({ok:true,json:async()=>body});
afterEach(()=>jest.restoreAllMocks());
test('searches the company catalog and confirms only the reviewed pair with a reason',async()=>{
  global.fetch=jest.fn(async(url,options)=>response(!options?.method?{items:[{id:7,name:'Дубль'},{id:8,name:'Основная',inn:'2635045921'},{id:9,name:'Уже объединена',merged_into_supplier_id:'8'}],hasMore:false}:
    url.endsWith('duplicate-preview')?{sourceId:7,targetId:8,sourceName:'Из накладной',targetName:'Основная',documents:{supplier_invoices:2,warehouse_invoices:1,supplier_offers:0},reviewVersion:'a'.repeat(64)}:{ok:true,sourceId:7,targetId:8}));
  render(<SupplierDuplicateMerge {...props}/>);
  fireEvent.change(screen.getByLabelText('Название или ИНН основной карточки'),{target:{value:'Эверест'}});
  fireEvent.click(screen.getByRole('button',{name:'Найти основную карточку'}));
  fireEvent.click(await screen.findByRole('button',{name:/Основная · ИНН: 2635045921/}));
  expect(screen.queryByRole('button',{name:/Уже объединена/})).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button',{name:'Проверить последствия'}));
  const confirm=await screen.findByRole('button',{name:'Объединить карточки'});
  expect(confirm).toBeDisabled();
  fireEvent.click(screen.getByRole('checkbox'));
  fireEvent.change(screen.getByLabelText('Основание объединения'),{target:{value:'Сверены реквизиты и исходные документы'}});
  fireEvent.click(confirm);
  await waitFor(()=>expect(props.onDone).toHaveBeenCalled());
  expect(fetch.mock.calls[0][0]).toContain('/system/companies/2/participants?search=');
  expect(fetch.mock.calls.at(-1)[1].body).toBe(JSON.stringify({targetSupplierId:8,expectedReview:'a'.repeat(64),confirmed:true,reason:'Сверены реквизиты и исходные документы'}));
});
test('stale confirmation requires another review',async()=>{
  global.fetch=jest.fn().mockResolvedValueOnce(response({items:[{id:8,name:'Основная'}],hasMore:false}))
    .mockResolvedValueOnce(response({sourceId:7,targetId:8,targetName:'Основная',documents:{},reviewVersion:'b'.repeat(64)}))
    .mockResolvedValueOnce({ok:false,status:409,json:async()=>({detail:'Карточки изменились'})});
  render(<SupplierDuplicateMerge {...props}/>);
  fireEvent.click(screen.getByRole('button',{name:'Найти основную карточку'}));
  fireEvent.click(await screen.findByRole('button',{name:/Основная ·/}));
  fireEvent.click(screen.getByRole('button',{name:'Проверить последствия'}));
  fireEvent.click(await screen.findByRole('checkbox'));
  fireEvent.change(screen.getByLabelText('Основание объединения'),{target:{value:'Проверены документы'}});
  fireEvent.click(screen.getByRole('button',{name:'Объединить карточки'}));
  expect(await screen.findByRole('alert')).toHaveTextContent('Карточки изменились');
  expect(screen.queryByRole('button',{name:'Объединить карточки'})).not.toBeInTheDocument();
});

test('a registered target always uses the existing historical disclosure plan',async()=>{
  global.fetch=jest.fn().mockResolvedValueOnce(response({items:[{id:8,name:'Кабинет',has_account:true}],hasMore:false}))
    .mockResolvedValueOnce(response({sourceId:7,targetId:8,targetName:'Кабинет',documents:{},hasSupplierAccount:true,reviewVersion:'c'.repeat(64)}))
    .mockResolvedValueOnce({ok:false,status:409,json:async()=>({detail:'Сначала уточните реквизиты кабинета'})});
  render(<SupplierDuplicateMerge {...props}/>);
  fireEvent.click(screen.getByRole('button',{name:'Найти основную карточку'}));
  fireEvent.click(await screen.findByRole('button',{name:/Кабинет ·/}));
  fireEvent.click(screen.getByRole('button',{name:'Проверить последствия'}));
  fireEvent.click(await screen.findByRole('button',{name:'Проверить доступ к истории'}));
  expect(screen.queryByRole('button',{name:'Объединить карточки'})).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button',{name:'Проверить последствия'}));
  expect(await screen.findByRole('alert')).toHaveTextContent('Сначала уточните реквизиты кабинета');
  expect(fetch.mock.calls.at(-1)[0]).toBe('/system/companies/2/participants/7/history-merge-plans');
});

test('missing INN is completed only after document confirmation and requires another merge review',async()=>{
  global.fetch=jest.fn().mockResolvedValueOnce(response({items:[{id:8,name:'Кабинет',has_account:true}],hasMore:false}))
    .mockResolvedValueOnce(response({sourceId:7,targetId:8,sourceInn:'2312254452',targetInn:'',canCompleteInn:true,hasSupplierAccount:true,documents:{},reviewVersion:'d'.repeat(64)}))
    .mockResolvedValueOnce(response({ok:true,sourceId:7,targetId:8,inn:'2312254452'}));
  render(<SupplierDuplicateMerge {...props}/>);
  fireEvent.click(screen.getByRole('button',{name:'Найти основную карточку'}));
  fireEvent.click(await screen.findByRole('button',{name:/Кабинет ·/}));
  fireEvent.click(screen.getByRole('button',{name:'Проверить последствия'}));
  const save=await screen.findByRole('button',{name:'Заполнить пропущенный ИНН'});
  expect(save).toBeDisabled();
  expect(screen.queryByRole('button',{name:'Проверить доступ к истории'})).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('checkbox'));
  fireEvent.change(screen.getByLabelText('Основание объединения'),{target:{value:'ИНН сверили по счёту кабинета'}});
  fireEvent.click(save);
  expect(await screen.findByRole('status')).toHaveTextContent('ИНН сохранён');
  expect(fetch.mock.calls.at(-1)[0]).toContain('/participants/7/duplicate-complete-inn');
  expect(screen.getByRole('button',{name:'Проверить последствия'})).toBeEnabled();
});

test.each([
  'Кабинет используется другими организациями. Уточните общий профиль отдельно',
  'С этим ИНН уже есть другой кабинет. Нужна проверка реквизитов',
])('shows the INN completion blocker before offering a command: %s',async blocker=>{
  global.fetch=jest.fn().mockResolvedValueOnce(response({items:[{id:8,name:'Кабинет',has_account:true}],hasMore:false}))
    .mockResolvedValueOnce(response({sourceId:7,targetId:8,sourceInn:'7711223344',targetInn:'',canCompleteInn:false,
      innCompletionBlocker:blocker,hasSupplierAccount:true,documents:{},reviewVersion:'e'.repeat(64)}))
    .mockResolvedValueOnce(response({sourceId:7,targetId:8,sourceInn:'7711223344',targetInn:'',canCompleteInn:true,
      innCompletionBlocker:null,hasSupplierAccount:true,documents:{},reviewVersion:'f'.repeat(64)}));
  render(<SupplierDuplicateMerge {...props}/>);
  fireEvent.click(screen.getByRole('button',{name:'Найти основную карточку'}));
  fireEvent.click(await screen.findByRole('button',{name:/Кабинет ·/}));
  fireEvent.click(screen.getByRole('button',{name:'Проверить последствия'}));
  expect(await screen.findByText(blocker)).toBeInTheDocument();
  expect(screen.queryByRole('button',{name:'Заполнить пропущенный ИНН'})).not.toBeInTheDocument();
  expect(screen.queryByRole('button',{name:'Проверить доступ к истории'})).not.toBeInTheDocument();
  expect(screen.queryByRole('checkbox')).not.toBeInTheDocument();
  expect(fetch).toHaveBeenCalledTimes(2);
  fireEvent.click(screen.getByRole('button',{name:'Повторить проверку реквизитов'}));
  expect(await screen.findByRole('button',{name:'Заполнить пропущенный ИНН'})).toBeDisabled();
  expect(screen.queryByText(blocker)).not.toBeInTheDocument();
  expect(fetch.mock.calls.at(-1)[0]).toBe('/system/companies/2/participants/7/duplicate-preview');
});
