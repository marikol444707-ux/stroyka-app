import React from 'react';
import {render, screen, fireEvent, waitFor} from '@testing-library/react';
import SupplyFileLink from './SupplyFileLink';
import SupplierAttachmentInput from './SupplierAttachmentInput';

beforeEach(()=>{global.fetch=jest.fn();URL.createObjectURL=jest.fn(()=> 'blob:test');URL.revokeObjectURL=jest.fn();});
afterEach(()=>jest.restoreAllMocks());
test('denied download stays visible and retries with credentials without opening an unsafe URL',async()=>{
  global.fetch.mockResolvedValueOnce({ok:false,status:403}).mockResolvedValueOnce({ok:true,blob:async()=>new Blob(['pdf']),headers:{get:()=>"attachment; filename*=UTF-8''quote.pdf"}});
  const click=jest.spyOn(HTMLAnchorElement.prototype,'click').mockImplementation(()=>{});
  render(<SupplyFileLink url="/tenant-files/7/content">Скачать файл</SupplyFileLink>);
  fireEvent.click(screen.getByText('Скачать файл'));
  expect(await screen.findByRole('alert')).toHaveTextContent('Доступ');
  expect(click).not.toHaveBeenCalled();
  fireEvent.click(screen.getByText('Скачать файл'));
  await waitFor(()=>expect(click).toHaveBeenCalledTimes(1));
  expect(global.fetch).toHaveBeenLastCalledWith('/tenant-files/7/content',expect.objectContaining({credentials:'include',cache:'no-store'}));
});
test('never fetches an external or script URL',()=>{
  render(<SupplyFileLink url="javascript:alert(1)">Файл</SupplyFileLink>);
  fireEvent.click(screen.getByText('Файл'));
  expect(screen.getByRole('alert')).toHaveTextContent('Ссылка устарела');
  expect(global.fetch).not.toHaveBeenCalled();
});
test('supplier upload binds offer and displays failure without claiming success',async()=>{
  const uploadPhoto=jest.fn().mockResolvedValueOnce('').mockResolvedValueOnce('/tenant-files/8/content');
  const onUploaded=jest.fn();
  render(<SupplierAttachmentInput offerId={7} label="Прикрепить КП" uploadPhoto={uploadPhoto} onUploaded={onUploaded}/>);
  const file=new File(['pdf'],'quote.pdf',{type:'application/pdf'});
  fireEvent.change(screen.getByLabelText('Прикрепить КП'),{target:{files:[file]}});
  expect(await screen.findByRole('alert')).toHaveTextContent('Не удалось');
  expect(onUploaded).not.toHaveBeenCalled();
  fireEvent.change(screen.getByLabelText('Прикрепить КП'),{target:{files:[file]}});
  await waitFor(()=>expect(onUploaded).toHaveBeenCalledWith('/tenant-files/8/content'));
  expect(uploadPhoto).toHaveBeenCalledWith(file,expect.objectContaining({supplierOfferId:7,projectScoped:false}));
});
test('late upload from a previous offer never attaches to the new offer',async()=>{
  let resolve;
  const uploadPhoto=jest.fn(()=>new Promise(done=>{resolve=done;}));
  const onUploaded=jest.fn();
  const view=render(<SupplierAttachmentInput offerId={7} label="Файл" uploadPhoto={uploadPhoto} onUploaded={onUploaded}/>);
  fireEvent.change(screen.getByLabelText('Файл'),{target:{files:[new File(['pdf'],'q.pdf')]}});
  view.rerender(<SupplierAttachmentInput offerId={8} label="Файл" uploadPhoto={uploadPhoto} onUploaded={onUploaded}/>);
  await require('@testing-library/react').act(async()=>resolve('/tenant-files/9/content'));
  expect(onUploaded).not.toHaveBeenCalled();
});
