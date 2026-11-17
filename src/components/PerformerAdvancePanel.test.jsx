import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import PerformerAdvancePanel from './PerformerAdvancePanel';

const payment = { id:1,companyId:4,projectName:'Объект',givenToId:100,givenTo:'Иван',amount:10000,paymentKind:'salary_advance',revision:0,allocations:[] };
const savedAct = { id:10,companyId:4,masterId:100,project:'Объект',workPackage:'Отделка',totalAmount:10000,paidAmount:0,advanceAmount:0,remainingAmount:10000 };
const show = (props={}) => <PerformerAdvancePanel payments={[payment]} acts={[savedAct]} C={{}} {...props} />;
beforeEach(()=>{global.fetch=jest.fn();});
afterEach(()=>jest.restoreAllMocks());

test('manual amount is sent once; conflict preserves input and requires deliberate revision choice', async()=>{
  let finish;global.fetch.mockReturnValueOnce(new Promise(resolve=>{finish=resolve;}));
  const refreshData=jest.fn();const {rerender}=render(show({refreshData}));
  fireEvent.click(screen.getByText(/Подотчёт и зарплатные авансы/));
  fireEvent.change(screen.getByLabelText('Акт для аванса 1'),{target:{value:'10'}});
  fireEvent.change(screen.getByLabelText('Сумма зачёта 1'),{target:{value:'6000'}});
  const save=screen.getByText('Сохранить сумму зачёта');fireEvent.click(save);fireEvent.click(save);
  expect(global.fetch).toHaveBeenCalledTimes(1);
  expect(JSON.parse(global.fetch.mock.calls[0][1].body)).toEqual({actId:10,amount:6000,expectedRevision:0});
  await act(async()=>finish({ok:false,status:409,json:async()=>({detail:'Выдача изменена в другой вкладке'})}));
  expect(screen.getByRole('alert')).toHaveTextContent('другой вкладке');
  expect(screen.getByLabelText('Сумма зачёта 1')).toHaveValue(6000);
  expect(refreshData).not.toHaveBeenCalled();
  rerender(show({refreshData,payments:[{...payment,revision:1}]}));
  expect(save).toBeDisabled();expect(global.fetch).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByText('Использовать загруженную версию после сверки'));
  expect(screen.getByLabelText('Сумма зачёта 1')).toHaveValue(6000);
  global.fetch.mockResolvedValue({ok:true,json:async()=>({ok:true,revision:2})});
  fireEvent.click(save);await waitFor(()=>expect(refreshData).toHaveBeenCalledTimes(1));
  expect(JSON.parse(global.fetch.mock.calls[1][1].body).expectedRevision).toBe(1);
});

test('late response after closing does not refresh the next screen', async()=>{
  let finish;global.fetch.mockReturnValue(new Promise(resolve=>{finish=resolve;}));
  const refreshData=jest.fn();const {unmount}=render(show({refreshData}));
  fireEvent.click(screen.getByText(/Подотчёт и зарплатные авансы/));
  fireEvent.change(screen.getByLabelText('Акт для аванса 1'),{target:{value:'10'}});
  fireEvent.change(screen.getByLabelText('Сумма зачёта 1'),{target:{value:'100'}});
  fireEvent.click(screen.getByText('Сохранить сумму зачёта'));unmount();
  await act(async()=>finish({ok:true,json:async()=>({ok:true,revision:1})}));
  expect(refreshData).not.toHaveBeenCalled();
});

test('unclassified history requires explicit type; foreign company and namesake acts are not offered', async()=>{
  const {rerender}=render(show({payments:[{...payment,paymentKind:'unclassified'}]}));
  fireEvent.click(screen.getByText(/Подотчёт и зарплатные авансы/));
  expect(screen.getByText('Сохранить тип')).toBeDisabled();
  expect(screen.queryByLabelText('Акт для аванса 1')).not.toBeInTheDocument();
  expect(global.fetch).not.toHaveBeenCalled();
  rerender(show({acts:[{...savedAct,id:11,companyId:5},{...savedAct,id:12,masterId:101},savedAct]}));
  const select=screen.getByLabelText('Акт для аванса 1');
  expect([...select.options].map(o=>o.value)).toEqual(['','10']);
});

test('malformed success does not adopt an assumed revision or refresh',async()=>{
  global.fetch.mockResolvedValue({ok:true,json:async()=>({ok:true})});
  const refreshData=jest.fn();render(show({refreshData}));
  fireEvent.click(screen.getByText(/Подотчёт и зарплатные авансы/));
  fireEvent.change(screen.getByLabelText('Акт для аванса 1'),{target:{value:'10'}});
  fireEvent.change(screen.getByLabelText('Сумма зачёта 1'),{target:{value:'50'}});
  fireEvent.click(screen.getByText('Сохранить сумму зачёта'));
  expect(await screen.findByRole('alert')).toHaveTextContent('не подтверждает новую версию');
  expect(screen.getByLabelText('Сумма зачёта 1')).toHaveValue(50);expect(refreshData).not.toHaveBeenCalled();
});
