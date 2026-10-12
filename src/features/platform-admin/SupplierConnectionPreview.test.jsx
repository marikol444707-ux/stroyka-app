import { act, fireEvent, render, screen } from '@testing-library/react';
import SupplierConnectionPreview from './SupplierConnectionPreview';
import OrganizationParticipants from './OrganizationParticipants';

const props={prefix:'/system/companies/2',supplierId:7,btnG:{},onClose:jest.fn()};
const response=body=>({ok:true,json:async()=>body});
const preview={companyId:2,platformAccountId:1,supplier:{supplierId:7,relationshipVersion:3},scenario:'connect_existing',cabinet:{supplierId:8,name:'Synthetic cabinet',inn:'7700010001',hasBuyerRelationship:false,accountState:'active',ownerUserId:15},history:{invoices:2,receipts:1,offers:0},currentVisibility:null,blockers:[{code:'OWNER_VERIFICATION_REQUIRED',message:'Подтвердите принадлежность кабинета.'}],canApply:false};
afterEach(()=>jest.restoreAllMocks());

test('connection inspection shows blockers and versions without a command to grant access',async()=>{
  global.fetch=jest.fn(async()=>response(preview));
  render(<SupplierConnectionPreview {...props}/>);
  expect(await screen.findByText('Найден существующий кабинет')).toBeInTheDocument();
  expect(screen.getByText('Подтвердите принадлежность кабинета.')).toBeInTheDocument();
  expect(screen.getByText(/счета — 2, накладные — 1, КП — 0/)).toBeInTheDocument();
  expect(screen.queryByText(/Сейчас пользователь кабинета/)).not.toBeInTheDocument();
  expect(screen.queryByRole('button',{name:/Подключить|Объединить/})).not.toBeInTheDocument();
  expect(fetch).toHaveBeenCalledWith('/system/companies/2/participants/7/connection-preview',expect.objectContaining({signal:expect.anything()}));
  fireEvent.click(screen.getByRole('button',{name:'Скрыть проверку'}));
  expect(props.onClose).toHaveBeenCalled();
});

test('unmount on company switch discards the previous inspection response',async()=>{
  let late;
  global.fetch=jest.fn(url=>url.includes('/2/')?new Promise(resolve=>{late=resolve;}):Promise.resolve(response({...preview,companyId:3,scenario:'no_cabinet',cabinet:null})));
  const view=render(<SupplierConnectionPreview key="2" {...props}/>);
  view.rerender(<SupplierConnectionPreview key="3" {...props} prefix="/system/companies/3"/>);
  expect(await screen.findByText('Существующий кабинет не найден')).toBeInTheDocument();
  await act(async()=>late(response(preview)));
  expect(screen.queryByText(/Synthetic cabinet/)).not.toBeInTheDocument();
  expect(fetch.mock.calls[0][1].signal.aborted).toBe(true);
});

test('failed inspection is retryable and never disguised as a missing cabinet',async()=>{
  global.fetch=jest.fn().mockResolvedValueOnce({ok:false,json:async()=>({detail:'Поставщик недоступен'})}).mockResolvedValue(response(preview));
  render(<SupplierConnectionPreview {...props}/>);
  expect(await screen.findByRole('alert')).toHaveTextContent('Поставщик недоступен');
  expect(screen.queryByText('Существующий кабинет не найден')).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button',{name:'Повторить проверку'}));
  expect(await screen.findByText('Найден существующий кабинет')).toBeInTheDocument();
});

test('supplier card opens its exact organization inspection and tab change cancels it',async()=>{
  let late;
  global.fetch=jest.fn(url=>url.includes('connection-preview')?new Promise(resolve=>{late=resolve;}):Promise.resolve(response(url.includes('/participants?')?{items:[{id:7,name:'Synthetic buyer supplier'}],hasMore:false}:{items:[],hasMore:false})));
  render(<OrganizationParticipants company={{id:2,name:'Synthetic A'}} API="" C={{}} btnG={{}} btnO={{}} inp={{}}/>);
  fireEvent.click(await screen.findByRole('button',{name:'Проверить кабинет'}));
  expect(await screen.findByText('Проверяю кабинет…')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button',{name:'Сотрудники и роли'}));
  expect(await screen.findByText('Подтверждённых членств в этой организации пока нет.')).toBeInTheDocument();
  await act(async()=>late(response(preview)));
  expect(screen.queryByText('Найден существующий кабинет')).not.toBeInTheDocument();
  expect(fetch.mock.calls.every(([,options])=>!options.method)).toBe(true);
});
