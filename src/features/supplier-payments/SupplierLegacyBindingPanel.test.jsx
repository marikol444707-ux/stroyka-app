import React from 'react';
import {render,screen,fireEvent,waitFor} from '@testing-library/react';
import SupplierLegacyBindingPanel from './SupplierLegacyBindingPanel';
import {paymentRequest} from './paymentClient';
jest.mock('./paymentClient',()=>({paymentRequest:jest.fn()}));
const props={API:'',userId:7,companyId:1,invoiceId:161};
const context={invoiceId:161,companyId:1,offerId:71,amount:'263000.00',boundContractId:null,
  contract:{id:8,version:1,snapshot:{number:'Д-1',date:'2026-09-28'},reviewedBy:'Директор'}};
beforeEach(()=>{process.env.REACT_APP_SUPPLIER_LEGACY_CONTRACT_BINDING_ENABLED='true';localStorage.clear();jest.clearAllMocks();
  Object.defineProperty(window.navigator,'locks',{value:{request:async(key,options,callback)=>callback({name:key})},configurable:true});
  Object.defineProperty(global,'crypto',{value:{randomUUID:()=> '11111111-1111-4111-8111-111111111111'},configurable:true});});
afterEach(()=>delete process.env.REACT_APP_SUPPLIER_LEGACY_CONTRACT_BINDING_ENABLED);
test('missing reviewed contract explains prerequisite without write action',async()=>{
  paymentRequest.mockResolvedValue({...context,contract:null});render(<SupplierLegacyBindingPanel {...props}/>);
  fireEvent.click(screen.getByText('Проверить договор для привязки'));
  expect(await screen.findByText(/Проверенной версии договора пока нет/)).toBeTruthy();
  expect(screen.queryByText('Привязать договор к счёту')).toBeNull();
});
test('explicit confirmation and reason are required; successful response clears saved request',async()=>{
  paymentRequest.mockResolvedValueOnce(context).mockImplementationOnce(async(api,company,path,{body})=>({
    invoiceId:161,companyId:1,requestId:body.requestId,contractVersionId:8,bindingStatus:'bound'}));
  const success=jest.fn();render(<SupplierLegacyBindingPanel {...props} onSuccess={success}/>);
  fireEvent.click(screen.getByText('Проверить договор для привязки'));await screen.findByText(/Договор №/);
  expect(screen.getByText('Привязать договор к счёту').disabled).toBe(true);
  fireEvent.change(screen.getByLabelText('Основание привязки'),{target:{value:'Проверено'}});
  fireEvent.click(screen.getByLabelText('Счёт и выбранная версия договора проверены'));
  fireEvent.click(screen.getByText('Привязать договор к счёту'));
  await waitFor(()=>expect(success).toHaveBeenCalledTimes(1));expect(localStorage.length).toBe(0);
});
test('lost response survives remount and repeats the same request id',async()=>{
  paymentRequest.mockResolvedValueOnce(context).mockRejectedValueOnce(new TypeError('Сеть'));
  const view=render(<SupplierLegacyBindingPanel {...props}/>);
  fireEvent.click(screen.getByText('Проверить договор для привязки'));await screen.findByText(/Договор №/);
  fireEvent.change(screen.getByLabelText('Основание привязки'),{target:{value:'Проверено'}});
  fireEvent.click(screen.getByLabelText('Счёт и выбранная версия договора проверены'));
  fireEvent.click(screen.getByText('Привязать договор к счёту'));await screen.findByRole('alert');
  const body=paymentRequest.mock.calls[1][3].body;view.unmount();
  paymentRequest.mockResolvedValueOnce({invoiceId:161,companyId:1,requestId:body.requestId,contractVersionId:8,bindingStatus:'bound'});
  render(<SupplierLegacyBindingPanel {...props}/>);
  fireEvent.click(screen.getByLabelText('Счёт и выбранная версия договора проверены'));
  fireEvent.click(screen.getByText('Повторить сохранённую привязку'));
  await waitFor(()=>expect(paymentRequest).toHaveBeenCalledTimes(3));
  expect(paymentRequest.mock.calls[2][3].body).toEqual(body);
});
test('feature remains hidden unless enabled',()=>{
  delete process.env.REACT_APP_SUPPLIER_LEGACY_CONTRACT_BINDING_ENABLED;
  const {container}=render(<SupplierLegacyBindingPanel {...props}/>);expect(container.innerHTML).toBe('');
});
test('scoped non-save rejection releases the intent for a fresh review',async()=>{
  paymentRequest.mockResolvedValueOnce(context).mockImplementationOnce(async(api,company,path,{body})=>{
    throw Object.assign(new Error('Сумма изменилась'),{status:409,detail:{code:'legacy_binding_not_saved',companyId:1,invoiceId:161,requestId:body.requestId}});
  });
  render(<SupplierLegacyBindingPanel {...props}/>);
  fireEvent.click(screen.getByText('Проверить договор для привязки'));await screen.findByText(/Договор №/);
  fireEvent.change(screen.getByLabelText('Основание привязки'),{target:{value:'Проверено'}});
  fireEvent.click(screen.getByLabelText('Счёт и выбранная версия договора проверены'));
  fireEvent.click(screen.getByText('Привязать договор к счёту'));
  expect(await screen.findByText(/Привязка не сохранена/)).toBeTruthy();expect(localStorage.length).toBe(0);
});
