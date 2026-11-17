import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import PerformerRetentionPanel from './PerformerRetentionPanel';

const savedAct = {id:10,companyId:4,masterName:'Иван',project:'Объект',workPackage:'Отделка',totalAmount:10000,paidAmount:0,retentionAmount:0,retentionReleased:0,retentionRevision:0};
const show = props => <PerformerRetentionPanel acts={[savedAct]} {...props}/>;
const fill = () => {
  fireEvent.click(screen.getByText(/Гарантийные удержания по актам/));
  fireEvent.change(screen.getByLabelText('Удержание 10'),{target:{value:'500'}});
  fireEvent.change(screen.getByLabelText('Основание удержания 10'),{target:{value:'Договор, п. 5'}});
  fireEvent.click(screen.getByLabelText('Подтверждаю сумму удержания по договору'));
};
beforeEach(()=>{global.fetch=jest.fn();});
afterEach(()=>jest.restoreAllMocks());

test('zero by default and explicit confirmation; 409 keeps draft without refresh or automatic retry',async()=>{
  let finish;fetch.mockReturnValue(new Promise(resolve=>{finish=resolve;}));
  const refreshData=jest.fn();const {rerender}=render(show({refreshData}));
  expect(screen.getByLabelText('Удержание 10')).toHaveValue(0);
  expect(screen.getByText('Сохранить удержание')).toBeDisabled();
  fill();const save=screen.getByText('Сохранить удержание');fireEvent.click(save);fireEvent.click(save);
  expect(fetch).toHaveBeenCalledTimes(1);
  expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({amount:'500',basis:'Договор, п. 5',confirmed:true,expectedRevision:0});
  await act(async()=>finish({ok:false,status:409,json:async()=>({detail:'Удержание изменено в другой вкладке'})}));
  expect(screen.getByRole('alert')).toHaveTextContent('другой вкладке');
  expect(screen.getByLabelText('Удержание 10')).toHaveValue(500);
  expect(refreshData).not.toHaveBeenCalled();
  rerender(show({refreshData,acts:[{...savedAct,retentionRevision:1,retentionAmount:400}]}));
  expect(save).toBeDisabled();expect(fetch).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByText('Сверено: использовать загруженную версию'));
  expect(save).toBeDisabled(); // New confirmation after reviewing the fresh server amount.
  expect(screen.getByLabelText('Удержание 10')).toHaveValue(500);
});

test('release is explicitly confirmed separately and never calls payment endpoint',async()=>{
  fetch.mockResolvedValue({ok:true,json:async()=>({ok:true,actId:10,revision:2,paymentCreated:false})});
  const refreshData=jest.fn();render(show({refreshData,acts:[{...savedAct,retentionRevision:1,retentionAmount:500,paidAmount:9500}]}));
  fireEvent.click(screen.getByText(/Гарантийные удержания по актам/));
  expect(screen.queryByText('Сохранить удержание')).not.toBeInTheDocument();
  const save=screen.getByText('Подтвердить освобождение удержания');expect(save).toBeDisabled();
  fireEvent.change(screen.getByLabelText('Освобождение 10'),{target:{value:'500'}});
  fireEvent.change(screen.getByLabelText('Основание освобождения 10'),{target:{value:'Срок завершён'}});
  fireEvent.click(screen.getByLabelText('Условия договора для освобождения суммы проверены'));
  fireEvent.click(save);await waitFor(()=>expect(refreshData).toHaveBeenCalledTimes(1));
  expect(fetch).toHaveBeenCalledTimes(1);expect(fetch.mock.calls[0][0]).toMatch(/\/10\/retention-release$/);
  expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({amount:'500',basis:'Срок завершён',confirmed:true,expectedRevision:1});
  expect(screen.getByRole('status')).toHaveTextContent('Денежная выплата не создана');
});

test.each(['closed','newer revision','company switched'])('late response after %s cannot change UI or refresh',async scenario=>{
  let finish;fetch.mockReturnValue(new Promise(resolve=>{finish=resolve;}));
  const refreshData=jest.fn();const view=render(show({refreshData}));fill();fireEvent.click(screen.getByText('Сохранить удержание'));
  if(scenario==='closed')view.unmount();
  else view.rerender(show({refreshData,acts:[{...savedAct,...(scenario==='newer revision'?{retentionRevision:2}:{companyId:5})}]}));
  await act(async()=>finish({ok:true,json:async()=>({ok:true,actId:10,revision:1})}));
  expect(refreshData).not.toHaveBeenCalled();expect(screen.queryByRole('status')).not.toBeInTheDocument();
});

test('malformed success keeps input and does not assume a revision',async()=>{
  fetch.mockResolvedValue({ok:true,json:async()=>({ok:true})});
  const refreshData=jest.fn();render(show({refreshData}));fill();fireEvent.click(screen.getByText('Сохранить удержание'));
  expect(await screen.findByRole('alert')).toHaveTextContent('не подтверждает сохранение');
  expect(screen.getByLabelText('Удержание 10')).toHaveValue(500);expect(refreshData).not.toHaveBeenCalled();
});
