import React from 'react';
import {render,screen,fireEvent,waitFor} from '@testing-library/react';
import Panel from './SupplierContractReviewPanel';
import {createContractReviewClient,legalDraft} from './contractReviewClient';
jest.mock('./contractReviewClient',()=>({...jest.requireActual('./contractReviewClient'),createContractReviewClient:jest.fn()}));
const props={API:'',userId:7,companyId:1,offerId:71};
const ctx={offerId:71,companyId:1,partyVersion:1,expectedVersion:0,
 buyer:{fullName:'Заказчик',inn:'7701111111',companyId:1},payer:{fullName:'Заказчик',inn:'7701111111',companyId:1},supplier:{fullName:'ВИСТ тест',inn:'7702222222',supplierId:159}};
let client;
beforeEach(()=>{client={pending:jest.fn(()=>null),load:jest.fn(async()=>({parties:{version:0},companies:[{companyId:1,companyName:'Наша компания'}]})),
 reviewContext:jest.fn(async()=>ctx),save:jest.fn(async()=>({id:8})),upload:jest.fn(async()=>({companyId:1,fileId:10}))};createContractReviewClient.mockReturnValue(client);});
test('explicit parties then original and reviewed legal identities are required',async()=>{
 const saved=jest.fn();render(<Panel {...props} onSaved={saved}/>);
 await screen.findByLabelText('Покупатель');
 fireEvent.change(screen.getByLabelText('Основание выбора сторон'),{target:{value:'По договору'}});
 fireEvent.submit(screen.getByText('Сохранить выбранные стороны').closest('form'));
 await screen.findByLabelText('Оригинал договора');
 expect(client.save).toHaveBeenCalledWith('parties',{buyerCompanyId:1,payerCompanyId:1,expectedVersion:0,reason:'По договору'});
 expect(screen.getByText('Сохранить проверенную версию договора').disabled).toBe(true);
 expect(screen.getAllByLabelText('ФИО подписанта').every(e=>e.value==='')).toBe(true);
 expect(screen.getAllByLabelText('ИНН').every(e=>e.readOnly)).toBe(true);
 fireEvent.change(screen.getByLabelText('Оригинал договора'),{target:{files:[new File(['contract'],'original.txt',{type:'text/plain'})]}});
 await screen.findByText('Загружен: original.txt');
 fireEvent.change(screen.getByLabelText('Номер договора'),{target:{value:'Д-1'}});
 fireEvent.change(screen.getByLabelText('Дата договора'),{target:{value:'2026-09-28'}});
 fireEvent.change(screen.getByLabelText('Основание проверки'),{target:{value:'Сверено'}});
 fireEvent.click(screen.getByLabelText('Реквизиты и условия сверены с загруженным оригиналом'));
 fireEvent.submit(screen.getByText('Сохранить проверенную версию договора').closest('form'));
 await waitFor(()=>expect(saved).toHaveBeenCalledTimes(1));
 expect(client.save.mock.calls[1][1]).toEqual({partyVersion:1,expectedVersion:0,sourceFileId:10,number:'Д-1',date:'2026-09-28',reviewConfirmed:true,paymentTerms:'',reason:'Сверено',
 buyer:legalDraft(ctx.buyer),payer:legalDraft(ctx.payer),supplier:legalDraft(ctx.supplier)});
});
test('retained command replaces editing until it is resolved',async()=>{
 const command={kind:'contract',body:{reason:'Сверено'}};client.pending.mockReturnValue(command);
 render(<Panel {...props}/>);await screen.findByText(/Есть сохранённый запрос/);
 expect(screen.queryByLabelText('Покупатель')).toBeNull();
 fireEvent.click(screen.getByText('Проверить и повторить сохранённый запрос'));
 await waitFor(()=>expect(client.save).toHaveBeenCalledWith('contract',command.body));
});
test('existing parties can continue without creating another version',async()=>{
 client.load.mockResolvedValue({parties:{version:2,buyerCompanyId:1,payerCompanyId:1},companies:[{companyId:1,companyName:'Наша компания'}]});
 render(<React.StrictMode><Panel {...props}/></React.StrictMode>);
 fireEvent.click(await screen.findByText('Перейти к проверке договора'));
 await screen.findByLabelText('Оригинал договора');expect(client.save).not.toHaveBeenCalled();
});
test('upload recognizes matched requisites without confirming or replacing manual fields',async()=>{
 const flag=process.env.REACT_APP_SUPPLIER_CONTRACT_RECOGNITION_ENABLED;process.env.REACT_APP_SUPPLIER_CONTRACT_RECOGNITION_ENABLED='true';
 try{
  client.load.mockResolvedValue({parties:{version:1,buyerCompanyId:1,payerCompanyId:1},companies:[{companyId:1,companyName:'Наша компания'}]});
  client.recognize=jest.fn(async()=>({sourceContentHash:'a'.repeat(64),parties:{buyer:{status:'missing',fields:{}},payer:{status:'missing',fields:{}},supplier:{status:'matched',fields:{inn:{value:ctx.supplier.inn},bankName:{value:'Распознанный банк'},directorName:{value:'Из оригинала'}}}}}));
  render(<Panel {...props}/>);fireEvent.click(await screen.findByText('Перейти к проверке договора'));await screen.findByLabelText('Оригинал договора');
  fireEvent.change(screen.getAllByLabelText('ФИО подписанта')[2],{target:{value:'Введено вручную'}});
  fireEvent.change(screen.getByLabelText('Оригинал договора'),{target:{files:[new File(['test'],'scan.png')]}});
  await screen.findByText(/Найденные реквизиты/);
  expect(client.recognize).toHaveBeenCalledWith(10,ctx);
  expect(screen.getAllByLabelText('Банк')[2].value).toBe('Распознанный банк');
  expect(screen.getAllByLabelText('ФИО подписанта')[2].value).toBe('Введено вручную');
  expect(screen.getByLabelText('Реквизиты и условия сверены с загруженным оригиналом').checked).toBe(false);
  client.recognize.mockRejectedValueOnce(new Error('Нечитаемый скан'));
  fireEvent.change(screen.getByLabelText('Оригинал договора'),{target:{files:[new File(['test'],'replacement.png')]}});
  await screen.findByText(/Нечитаемый скан/);
  expect(screen.getAllByLabelText('Банк')[2].value).toBe('');
  expect(screen.getAllByLabelText('ФИО подписанта')[2].value).toBe('Введено вручную');
 }finally{if(flag===undefined)delete process.env.REACT_APP_SUPPLIER_CONTRACT_RECOGNITION_ENABLED;else process.env.REACT_APP_SUPPLIER_CONTRACT_RECOGNITION_ENABLED=flag;}
});
