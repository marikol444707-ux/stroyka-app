import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import WarehouseOperationsPanel from './WarehouseOperationsPanel';

test.each([false, true])('movement history includes source and unlinked states, compact=%s', isMobile => {
  render(<WarehouseOperationsPanel warehouseTab="move" isMobile={isMobile} C={{}} card={{}} inp={{}}
    projects={[]} visibleActiveProjects={value => value} warehouseMain={[]} materials={[]}
    newMovement={{ fromLocation: 'Основной склад', toLocation: '', notes: '', selectedMaterials: [] }}
    warehouseInvoices={[{ id: 5, companyId: 2, number: 'НК-5', supplierName: 'Без кабинета', items: [{ name: 'Кабель', invoiceLineIndex: 0 }] }]}
    warehouseMovements={[
      { id: 1, companyId: 2, sourceInvoiceId: 5, sourceInvoiceLineIndex: 0, materialName: 'Кабель', fromLocation: 'Основной склад', toLocation: 'Школа', quantity: 10, unit: 'м' },
      { id: 2, companyId: 2, materialName: 'Краска', fromLocation: 'Основной склад', toLocation: 'Школа', quantity: 3, unit: 'л' },
    ]} />);
  expect(screen.getByText(/НК-5/)).toHaveTextContent('строка 1');
  expect(screen.getByText('Без кабинета')).toBeInTheDocument();
  expect(screen.getByText('Источник поступления не указан')).toBeInTheDocument();
  expect(screen.getByText(/не создаёт новый долг/)).toBeInTheDocument();
});

test('selector excludes unidentified and duplicate indices and sends original visible line index', () => {
  const material = { id: 1, name: 'Кабель', unit: 'м', quantity: 10 };
  const state = { fromLocation: 'Основной склад', toLocation: '', notes: '', selectedMaterials: [{ ...material, quantity: '1' }] };
  const setNewMovement = jest.fn();
  const indices = [2, undefined, null, -1, 1.5, '0', true, Number.MAX_SAFE_INTEGER + 1, 4, 4];
  render(<WarehouseOperationsPanel warehouseTab="move" C={{}} card={{}} inp={{}}
    projects={[]} visibleActiveProjects={v => v} warehouseMain={[material]} materials={[]}
    newMovement={state} setNewMovement={setNewMovement} warehouseMovements={[]}
    warehouseInvoices={[{ id: 5, companyId: 2, location: 'Основной склад', items: indices.map(invoiceLineIndex => ({ ...material, invoiceLineIndex })) }]} />);
  const option = screen.getByRole('option', { name: /Накладная/ });
  expect(option).toHaveValue('5:2');
  fireEvent.change(option.parentElement, { target: { value: '5:2' } });
  expect(setNewMovement.mock.calls[0][0](state).selectedMaterials[0]).toMatchObject({ invoiceId: 5, invoiceLineIndex: 2 });
});

test('unidentified source offers no selector and explains why', () => {
  const material = { id: 1, name: 'Кабель', unit: 'м', quantity: 10 };
  render(<WarehouseOperationsPanel warehouseTab="move" C={{}} card={{}} inp={{}}
    projects={[]} visibleActiveProjects={v => v} warehouseMain={[material]} materials={[]}
    newMovement={{ fromLocation: 'Основной склад', selectedMaterials: [{ ...material, quantity: '1' }] }} warehouseMovements={[]}
    warehouseInvoices={[{ id: 5, location: 'Основной склад', items: [material] }]} />);
  expect(screen.queryByRole('option', { name: /Накладная/ })).not.toBeInTheDocument();
  expect(screen.getByText(/Нет доступных строк с подтверждённым индексом/)).toBeInTheDocument();
});
