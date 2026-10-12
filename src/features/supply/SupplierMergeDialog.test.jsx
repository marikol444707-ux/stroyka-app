import React from 'react';
import {fireEvent, render, screen, waitFor} from '@testing-library/react';
import SupplierMergeDialog from './SupplierMergeDialog';

const originalFetch=global.fetch;
const supplier={id:12,companyId:2,name:'Поставщик с кабинетом',hasSupplierAccount:true,_supplierIds:[4,12]};
const sources=[supplier,{id:4,companyId:2,name:'Поставщик из накладной'}];
const review={targetId:12,sourceId:4,targetVersion:3,sourceVersion:1,targetName:supplier.name,sourceName:sources[1].name,hasSupplierAccount:true,documents:{supplier_invoices:2,warehouse_invoices:1,supplier_offers:0}};
const response=data=>({ok:true,json:async()=>data});
afterEach(()=>{global.fetch=originalFetch;jest.restoreAllMocks();});

test('previews before confirmation and does not repeat a pending merge',async()=>{
  let finish;
  global.fetch=jest.fn().mockResolvedValueOnce(response(review)).mockImplementationOnce(()=>new Promise(resolve=>{finish=resolve;}));
  const onClose=jest.fn(), loadAll=jest.fn();
  render(<SupplierMergeDialog supplier={supplier} suppliers={sources} API="/api" C={{}} onClose={onClose} loadAll={loadAll}/>);
  fireEvent.change(screen.getByRole('combobox',{name:'Карточка из накладной'}),{target:{value:'4'}});
  fireEvent.click(screen.getByRole('button',{name:'Проверить карточки'}));
  const confirm=await screen.findByRole('button',{name:'Подтвердить объединение'});
  expect(global.fetch.mock.calls[0][0]).toBe('/api/suppliers/12/merge-preview');
  expect(JSON.parse(global.fetch.mock.calls[0][1].body)).toEqual({companyId:2,sourceId:4});
  fireEvent.click(confirm);fireEvent.click(confirm);
  expect(global.fetch).toHaveBeenCalledTimes(2);
  expect(JSON.parse(global.fetch.mock.calls[1][1].body)).toEqual({companyId:2,sourceId:4,targetVersion:3,sourceVersion:1,confirmed:true});
  finish(response({ok:true}));
  await waitFor(()=>expect(onClose).toHaveBeenCalledTimes(1));
  expect(loadAll).toHaveBeenCalledTimes(1);
});

test('requires a fresh review after stale confirmation and retains selected card',async()=>{
  global.fetch=jest.fn().mockResolvedValueOnce(response(review)).mockResolvedValueOnce({ok:false,status:409,json:async()=>({detail:'Карточки изменились'})});
  render(<SupplierMergeDialog supplier={supplier} suppliers={sources} API="/api" C={{}} onClose={jest.fn()} loadAll={jest.fn()}/>);
  fireEvent.change(screen.getByRole('combobox',{name:'Карточка из накладной'}),{target:{value:'4'}});
  fireEvent.click(screen.getByRole('button',{name:'Проверить карточки'}));
  fireEvent.click(await screen.findByRole('button',{name:'Подтвердить объединение'}));
  expect(await screen.findByRole('alert')).toHaveTextContent('Карточки изменились');
  expect(screen.queryByRole('button',{name:'Подтвердить объединение'})).not.toBeInTheDocument();
  expect(screen.getByRole('combobox',{name:'Карточка из накладной'})).toHaveValue('4');
});

test('a successful merge with failed refresh cannot be submitted again',async()=>{
  global.fetch=jest.fn().mockResolvedValueOnce(response(review)).mockResolvedValueOnce(response({ok:true}));
  render(<SupplierMergeDialog supplier={supplier} suppliers={sources} API="/api" C={{}} onClose={jest.fn()} loadAll={jest.fn().mockRejectedValue(new Error('offline'))}/>);
  fireEvent.change(screen.getByRole('combobox',{name:'Карточка из накладной'}),{target:{value:'4'}});
  fireEvent.click(screen.getByRole('button',{name:'Проверить карточки'}));
  fireEvent.click(await screen.findByRole('button',{name:'Подтвердить объединение'}));
  expect(await screen.findByRole('alert')).toHaveTextContent('Карточки объединены, но список не обновился');
  expect(screen.queryByRole('button',{name:'Подтвердить объединение'})).not.toBeInTheDocument();
  expect(global.fetch).toHaveBeenCalledTimes(2);
});
