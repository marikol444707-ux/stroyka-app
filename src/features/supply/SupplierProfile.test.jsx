import React from 'react';
import {render,screen,fireEvent,waitFor,act} from '@testing-library/react';
import SupplierProfile from './SupplierProfile';
const profile={fields:{name:'Поставщик',phone:'123',email:'',legalAddress:''},version:'v1',canEdit:true,
  tariff:{status:'not_configured'},team:{enabled:true,customerAssignments:true,managerLimit:null,customersPerManagerLimit:null}};
const props={API:'',user:{id:1,role:'поставщик'},suppliers:[{id:7,name:'Поставщик'}],C:{}};
beforeEach(()=>{global.fetch=jest.fn();});
test('loads actual fields and shows no invented free or paid tariff',async()=>{
  global.fetch.mockResolvedValue({ok:true,json:async()=>profile});
  render(<SupplierProfile {...props}/>);
  expect(await screen.findByLabelText('Название компании')).toHaveValue('Поставщик');
  expect(screen.getByLabelText('Тариф поставщика')).toHaveTextContent('Условия тарифа поставщика пока не заданы');
  expect(screen.getByLabelText('Тариф поставщика')).not.toHaveTextContent(/бесплатно|₽/i);
  expect(screen.getByText('Сохранить реквизиты')).toBeDisabled();
});
test('sends changed fields and version once, keeps draft on error and allows retry',async()=>{
  let resolve;
  global.fetch.mockResolvedValueOnce({ok:true,json:async()=>profile}).mockImplementationOnce(()=>new Promise(done=>{resolve=done;}))
    .mockResolvedValueOnce({ok:true,json:async()=>({...profile,fields:{...profile.fields,phone:'456'},version:'v2'})});
  render(<SupplierProfile {...props}/>);
  fireEvent.change(await screen.findByLabelText('Телефон'),{target:{value:'456'}});
  fireEvent.click(screen.getByText('Сохранить реквизиты'));fireEvent.click(screen.getByText('Сохраняем…'));
  expect(global.fetch).toHaveBeenCalledTimes(2);
  expect(JSON.parse(global.fetch.mock.calls[1][1].body)).toEqual({phone:'456',expectedProfileVersion:'v1'});
  await act(async()=>resolve({ok:false,status:503,json:async()=>({detail:'Связь потеряна'})}));
  expect(screen.getByRole('alert')).toHaveTextContent('Связь потеряна');
  expect(screen.getByLabelText('Телефон')).toHaveValue('456');
  fireEvent.click(screen.getByText('Сохранить реквизиты'));
  expect(await screen.findByText('Реквизиты сохранены')).toBeInTheDocument();
});
test('conflict preserves draft until explicit reload and blocks another save',async()=>{
  global.fetch.mockResolvedValueOnce({ok:true,json:async()=>profile})
    .mockResolvedValueOnce({ok:false,status:409,json:async()=>({detail:'Изменено другим пользователем'})})
    .mockResolvedValueOnce({ok:true,json:async()=>({...profile,fields:{...profile.fields,phone:'999'},version:'v2'})});
  render(<SupplierProfile {...props}/>);
  fireEvent.change(await screen.findByLabelText('Телефон'),{target:{value:'456'}});
  fireEvent.click(screen.getByText('Сохранить реквизиты'));
  await screen.findByRole('alert');
  expect(screen.getByText('Сохранить реквизиты')).toBeDisabled();
  expect(screen.getByLabelText('Телефон')).toHaveValue('456');
  fireEvent.click(screen.getByText('Загрузить актуальные реквизиты'));
  await waitFor(()=>expect(screen.getByLabelText('Телефон')).toHaveValue('999'));
});
test('no verified leader renders no requisites or request',()=>{
  render(<SupplierProfile {...props} suppliers={[]}/>);
  expect(global.fetch).not.toHaveBeenCalled();
  expect(screen.queryByLabelText('Банк')).not.toBeInTheDocument();
});
test('changing supplier removes previous bank details while loading',async()=>{
  global.fetch.mockResolvedValueOnce({ok:true,json:async()=>({...profile,fields:{...profile.fields,bank:'Private Bank'}})})
    .mockImplementationOnce(()=>new Promise(()=>{}));
  render(<SupplierProfile {...props} suppliers={[{id:7,name:'Первый'},{id:8,name:'Второй'}]}/>);
  expect(await screen.findByLabelText('Банк')).toHaveValue('Private Bank');
  fireEvent.change(screen.getByLabelText('Компания поставщика'),{target:{value:'8'}});
  expect(screen.queryByDisplayValue('Private Bank')).not.toBeInTheDocument();
});
test('StrictMode aborted first load cannot clear or block the replacement request',async()=>{
  let rejectFirst;
  global.fetch.mockImplementationOnce(()=>new Promise((_,reject)=>{rejectFirst=reject;}))
    .mockResolvedValueOnce({ok:true,json:async()=>({...profile,fieldLimits:{phone:100,legalAddress:4000}})});
  render(<React.StrictMode><SupplierProfile {...props}/></React.StrictMode>);
  expect(await screen.findByLabelText('Название компании')).toHaveValue('Поставщик');
  await act(async()=>rejectFirst(Object.assign(new Error('Aborted'),{name:'AbortError'})));
  expect(global.fetch).toHaveBeenCalledTimes(2);
  expect(global.fetch.mock.calls[0][1].signal.aborted).toBe(true);
  expect(screen.getByLabelText('Телефон')).toHaveAttribute('maxlength','100');
  expect(screen.getByLabelText('Юридический адрес')).toHaveAttribute('maxlength','4000');
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
});
