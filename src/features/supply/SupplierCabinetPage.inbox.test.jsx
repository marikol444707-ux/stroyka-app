import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import SupplierCabinetPage from './SupplierCabinetPage';
const props = { API: '/api', C: {}, user: { id: 7, role: 'поставщик', name: 'Поставщик' }, supplierTab: 'requests', suppliers: [], supplierRequisites: {}, supplierOffers: [], supplyRequests: [] };
it.each(['loading', 'error'])('does not claim an empty inbox while %s', status => {
  const reload = jest.fn();
  render(<SupplierCabinetPage {...props} inboxState={{ status, error: 'Сервис недоступен', reload }} />);
  expect(screen.queryByText(/Запросов нет/)).not.toBeInTheDocument();
  expect(screen.getAllByText('—')).toHaveLength(3);
  if (status === 'error') {
    expect(screen.getByRole('alert')).toHaveTextContent('Сервис недоступен');
    fireEvent.click(screen.getByRole('button', { name: 'Обновить заявки' }));
    expect(reload).toHaveBeenCalledTimes(1);
  } else expect(screen.getByRole('status')).toHaveTextContent('Загружаем');
});
it('shows an empty message only after confirmed success', () => {
  render(<SupplierCabinetPage {...props} inboxState={{ status: 'ready', reload: jest.fn() }} />);
  expect(screen.getByText(/Запросов нет/)).toBeInTheDocument();
});
