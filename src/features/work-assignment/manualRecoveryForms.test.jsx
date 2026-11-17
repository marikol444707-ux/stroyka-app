import React from 'react';
import {act,fireEvent,render,screen,waitFor} from '@testing-library/react';
import ProjectBrigadeCreateForm from '../../components/ProjectBrigadeCreateForm';
import WorkAssignmentModal from './WorkAssignmentModal';
import {manualCommandScope,readManualCommand} from './manualCommandRecovery';

jest.mock('../../utils/commandUuid',()=>({commandUuid:()=> '619c59a4-88af-4c11-9e58-765f2b232680'}));
const context={mode:'company',selectedCompanyId:4};
const user={id:9,role:'директор'};
const scope=manualCommandScope(context,user,'contract',{id:17});
const json=data=>({ok:true,json:async()=>data});
const receipt=init=>({ok:true,id:70,contractId:70,companyId:4,projectId:17,
  manualRequestId:(JSON.parse(init.body).contractorRef || JSON.parse(init.body).assignee.contractorRef).requestId});
const props=()=>({project:{id:17,name:'Лицей'},user,companyContext:context,
  newBrigadeContract:{brigadeName:'Исходная бригада',contractorId:'',contractorType:'Мастер'},
  setNewBrigadeContract:jest.fn(),setBrigadeContracts:jest.fn(),setSelectedBrigadeContract:jest.fn(),
  setBrigadeContractItems:jest.fn(),setBrigadePayments:jest.fn(),setShowBrigadeForm:jest.fn(),
  openBrigadeContract:jest.fn(),card:{},inp:{},btnO:{},btnG:{}});
const workProps=()=>({show:true,user,companyContext:context,onClose:jest.fn(),API:'/api',loadAll:jest.fn(),
  selectedEstimate:{id:25,projectId:17,sections:[{name:'Монтаж',items:[
    {name:'Исходная работа',unit:'м',quantity:5,priceWork:100,estimateItemKey:'original-work'}]}]},
  staff:[],users:[],C:{},card:{},inp:{},btnO:{},btnG:{},btnB:{},isMobile:false});
beforeEach(()=>{sessionStorage.clear();localStorage.clear();window.alert=jest.fn();});

test('remount restores the contract command and retries its exact body instead of a different draft',async()=>{
  global.fetch=jest.fn().mockRejectedValueOnce(new Error('lost response'))
    .mockImplementationOnce(async(_url,init)=>json(receipt(init)))
    .mockResolvedValueOnce(json([{id:70,companyId:4,projectId:17,brigadeName:'Исходная бригада'}]));
  const view=render(<ProjectBrigadeCreateForm {...props()}/>);
  fireEvent.click(screen.getByRole('button',{name:'Создать договор'}));
  await screen.findByRole('alert');
  const body=fetch.mock.calls[0][1].body;
  view.unmount();
  const restored=props();restored.newBrigadeContract.brigadeName='Новый черновик';
  render(<ProjectBrigadeCreateForm {...restored}/>);
  expect(screen.getByRole('region',{name:'Сохранённая отправка бригады'})).toHaveTextContent('Исходная бригада');
  expect(screen.getByRole('button',{name:'Создать договор'})).toBeDisabled();
  fireEvent.click(screen.getByRole('button',{name:'Повторить сохранённую отправку'}));
  await waitFor(()=>expect(restored.openBrigadeContract).toHaveBeenCalled());
  expect(fetch.mock.calls[1][1].body).toBe(body);
  expect(readManualCommand(scope)).toBeNull();
});

test('remount restores assignment even if current estimate rows have changed',async()=>{
  global.fetch=jest.fn().mockRejectedValueOnce(new Error('lost'))
    .mockImplementationOnce(async(_url,init)=>json(receipt(init)));
  const original=workProps();
  const view=render(<WorkAssignmentModal {...original}/>);
  fireEvent.change(screen.getByRole('combobox',{name:'Исполнитель'}),{target:{value:'__manual__'}});
  fireEvent.change(screen.getByPlaceholderText('Название бригады'),{target:{value:'Исходная бригада'}});
  fireEvent.click(screen.getByRole('button',{name:'Выдать в работу'}));
  await screen.findByRole('alert');
  const body=fetch.mock.calls[0][1].body;
  view.unmount();
  const restored={...workProps(),selectedEstimate:{...original.selectedEstimate,sections:[]}};
  render(<WorkAssignmentModal {...restored}/>);
  expect(screen.getByRole('region',{name:'Сохранённая отправка бригады'})).toHaveTextContent('работ: 1');
  fireEvent.click(screen.getByRole('button',{name:'Повторить сохранённую отправку'}));
  await waitFor(()=>expect(restored.onClose).toHaveBeenCalled());
  expect(fetch.mock.calls[1][1].body).toBe(body);
  expect(JSON.parse(body).items[0].expectedSource).toEqual({name:'Исходная работа',unit:'м',quantity:5,priceSmeta:100});
});

test('changing company or actor hides another context pending command without deleting it',async()=>{
  global.fetch=jest.fn().mockRejectedValue(new Error('lost'));
  const initial=props();
  const view=render(<ProjectBrigadeCreateForm {...initial}/>);
  fireEvent.click(screen.getByRole('button',{name:'Создать договор'}));await screen.findByRole('alert');
  view.rerender(<ProjectBrigadeCreateForm {...initial} companyContext={{mode:'company',selectedCompanyId:5}}/>);
  expect(screen.queryByRole('region',{name:'Сохранённая отправка бригады'})).not.toBeInTheDocument();
  expect(readManualCommand(scope)).not.toBeNull();
  view.rerender(<ProjectBrigadeCreateForm {...initial} user={{id:10}}/>);
  expect(screen.queryByRole('region',{name:'Сохранённая отправка бригады'})).not.toBeInTheDocument();
  view.rerender(<ProjectBrigadeCreateForm {...initial}/>);
  expect(screen.getByRole('region',{name:'Сохранённая отправка бригады'})).toBeInTheDocument();
  expect(fetch).toHaveBeenCalledTimes(1);
});

test('late success cannot open or modify the next company screen',async()=>{
  let resolve;
  global.fetch=jest.fn((_url,init)=>new Promise(done=>{resolve=()=>done(json(receipt(init)));}));
  const initial=props();
  const view=render(<ProjectBrigadeCreateForm {...initial}/>);
  fireEvent.click(screen.getByRole('button',{name:'Создать договор'}));
  view.rerender(<ProjectBrigadeCreateForm {...initial} companyContext={{mode:'company',selectedCompanyId:5}}/>);
  await act(async()=>resolve());
  expect(initial.openBrigadeContract).not.toHaveBeenCalled();
  expect(initial.setBrigadeContracts).not.toHaveBeenCalled();
  expect(fetch).toHaveBeenCalledTimes(1);
  expect(readManualCommand(scope).receipt.id).toBe(70);
  expect(screen.queryByRole('region',{name:'Сохранённая отправка бригады'})).not.toBeInTheDocument();
});

test('a changed browser login blocks dispatch even before parent props catch up',async()=>{
  localStorage.setItem('user',JSON.stringify(user));
  global.fetch=jest.fn();
  render(<ProjectBrigadeCreateForm {...props()}/>);
  localStorage.setItem('user',JSON.stringify({id:10}));
  fireEvent.click(screen.getByRole('button',{name:'Создать договор'}));
  expect(await screen.findByRole('alert')).toHaveTextContent('Пользователь или компания изменились');
  expect(fetch).not.toHaveBeenCalled();
});
