import React from 'react';
import { act, fireEvent, render, screen } from '@testing-library/react';
import SupplierRequestRegistry from './SupplierRequestRegistry';

it('groups quotes by request and opens the selected request without inventing a deadline', () => {
  const open = jest.fn();
  render(<SupplierRequestRegistry C={{}} requests={[{id:31,companyName:'Заказчик Альфа',project:'Лицей',materialName:'Труба'}]}
    offers={[{id:1,requestId:31,status:'Получено'}, {id:2,requestId:31,status:'Отозвано'}, {id:3,requestId:99,status:'Ожидает ответа'}]} onOpen={open} />);
  expect(screen.getAllByRole('button', {name:'Открыть заявку №31'})).toHaveLength(1);
  expect(screen.getByText('Заказчик Альфа')).toBeInTheDocument();
  expect(screen.getByText('Ждём решения заказчика · Отозвано')).toBeInTheDocument();
  expect(screen.queryByText(/№99/)).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', {name:'Открыть заявку №31'}));
  expect(open).toHaveBeenCalledWith(31);
});
it('shows unknown customer and date honestly', () => {
  render(<SupplierRequestRegistry C={{}} requests={[{id:5,companyId:8,createdAt:'2026-01-01'}]} offers={[{id:1,requestId:5,status:'Новый статус'}]} onOpen={()=>{}} />);
  expect(screen.getByText('Компания №8',{selector:'div'})).toBeInTheDocument();
  expect(screen.getByText('Не указано')).toBeInTheDocument();
  expect(screen.getByText('Новый статус',{selector:'td'})).toBeInTheDocument();
});

it('filters all pages, resets pagination and clamps it when access shrinks', () => {
  const requests=Array.from({length:25},(_,i)=>({id:i+1,companyId:i===24?3:2,companyName:i===24?'Бета':'Альфа',materialName:i===24?'Кабель':'Труба'}));
  const offers=requests.map(r=>({requestId:r.id,status:r.id===25?'Получено':'Ожидает ответа'}));
  const props={C:{},requests,offers,onOpen:()=>{}};
  const {rerender}=render(<SupplierRequestRegistry {...props}/>);
  expect(screen.getAllByRole('button',{name:/Открыть заявку №/})).toHaveLength(20);
  expect(screen.getByText('Найдено: 25 из 25')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button',{name:'Следующая страница'}));
  expect(screen.getAllByRole('button',{name:/Открыть заявку №/})).toHaveLength(5);
  fireEvent.change(screen.getByRole('searchbox'),{target:{value:'кабель'}});
  expect(screen.getByRole('button',{name:'Открыть заявку №25'})).toBeInTheDocument();
  expect(screen.getByText('Найдено: 1 из 25')).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('Заказчик'),{target:{value:'2'}});
  expect(screen.getByText('По выбранным условиям заявок нет.')).toBeInTheDocument();
  expect(screen.getByRole('button',{name:'Выгрузить CSV'})).toBeDisabled();
  fireEvent.click(screen.getByRole('button',{name:'Сбросить фильтры'}));
  fireEvent.click(screen.getByRole('button',{name:'Следующая страница'}));
  rerender(<SupplierRequestRegistry {...props} requests={requests.slice(0,2)} offers={offers.slice(0,2)}/>);
  expect(screen.getAllByRole('button',{name:/Открыть заявку №/})).toHaveLength(2);
  expect(screen.getByText('Страница 1 из 1')).toBeInTheDocument();
});
it('downloads all filtered rows across pages using the same visible data projection', async () => {
  const requests=Array.from({length:25},(_,i)=>({id:i+1,companyId:2,materialName:'Материал '+(i+1)}));
  const offers=requests.map(r=>({requestId:r.id,status:'Получено'}));
  const create=jest.fn(()=>'blob:test');const revoke=jest.fn();
  const oldCreate=URL.createObjectURL,oldRevoke=URL.revokeObjectURL;
  URL.createObjectURL=create;URL.revokeObjectURL=revoke;
  const click=jest.spyOn(HTMLAnchorElement.prototype,'click').mockImplementation(()=>{});
  jest.useFakeTimers();
  try {
    render(<SupplierRequestRegistry C={{}} requests={requests} offers={offers} onOpen={()=>{}}/>);
    fireEvent.click(screen.getByRole('button',{name:'Выгрузить CSV'}));
    const blob=create.mock.calls[0][0];
    const text=await new Promise(resolve=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.readAsText(blob);});
    expect(text).toContain('Материал 25');
    expect(text.split('\r\n').filter(Boolean)).toHaveLength(26);
    expect(click).toHaveBeenCalledTimes(1);
    act(()=>jest.advanceTimersByTime(1000));expect(revoke).toHaveBeenCalledWith('blob:test');
  } finally { click.mockRestore();URL.createObjectURL=oldCreate;URL.revokeObjectURL=oldRevoke;jest.useRealTimers(); }
});
it('attention cards count distinct requests and filter rows without including answered deadlines',()=>{
  const requests=[{id:1},{id:2},{id:3}];
  const offers=[{id:1,requestId:1,status:'Ожидает ответа',responseDueAt:'2000-01-01T00:00:00Z'}, {id:2,requestId:1,status:'Ожидает ответа',responseDueAt:'2000-01-01T00:00:00Z'}, {id:3,requestId:2,status:'Получено',responseDueAt:'2000-01-01T00:00:00Z'}, {id:4,requestId:3,status:'Отозвано',responseDueAt:'2000-01-01T00:00:00Z'}];
  render(<SupplierRequestRegistry C={{}} requests={requests} offers={offers} onOpen={()=>{}}/>);
  fireEvent.click(screen.getByRole('button',{name:/Просрочено\s*1/}));
  expect(screen.getAllByRole('button',{name:/Открыть заявку №/})).toHaveLength(1);
  expect(screen.getByRole('button',{name:'Открыть заявку №1'})).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button',{name:/Ждём заказчика\s*1/}));
  expect(screen.getByRole('button',{name:'Открыть заявку №2'})).toBeInTheDocument();
});
