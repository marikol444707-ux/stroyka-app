import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
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
  expect(screen.getByText('Компания №8')).toBeInTheDocument();
  expect(screen.getByText('Не указано')).toBeInTheDocument();
  expect(screen.getByText('Новый статус')).toBeInTheDocument();
});
