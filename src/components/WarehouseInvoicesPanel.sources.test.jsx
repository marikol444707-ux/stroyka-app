import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import WarehouseInvoicesPanel from './WarehouseInvoicesPanel';

jest.mock('./warehouse/WarehouseInvoicesParts', () => ({
  WarehouseInvoiceCard: ({ onPrepareTransfer }) => <button onClick={onPrepareTransfer}>Prepare transfer</button>,
  WarehouseInvoiceForm: () => null,
}));

const item = { name: 'Кабель', unit: 'м', quantity: 2, workPackage: 'Электрика' };
const show = (indices, stockQuantity = 10) => {
  const setNewTransfer = jest.fn();
  render(<WarehouseInvoicesPanel newInvoice={{ items: [] }} suppliers={[]} projects={[]} C={{}} card={{}} inp={{}}
    invoices={[{ id: 5, companyId: 2, project: 'Школа', items: indices.map(invoiceLineIndex => ({ ...item, invoiceLineIndex })) }]}
    warehouseInvoiceItems={inv => ({ items: inv.items })} materials={[{ ...item, project: 'Школа', quantity: stockQuantity }]}
    setNewTransfer={setNewTransfer} setShowTransferForm={jest.fn()} />);
  fireEvent.click(screen.getByRole('button', { name: 'Prepare transfer' }));
  return setNewTransfer;
};

test('worker transfer preserves separate same-name original receipt lines', () => {
  const callback = show([2, 5]);
  expect(callback).toHaveBeenCalledTimes(1);
  expect(callback.mock.calls[0][0].items).toEqual([
    expect.objectContaining({ materialName: 'Кабель', quantity: '2', invoiceId: 5, invoiceLineIndex: 2 }),
    expect.objectContaining({ materialName: 'Кабель', quantity: '2', invoiceId: 5, invoiceLineIndex: 5 }),
  ]);
});

test('suggestions share the available stock budget across distinct receipt lines', () => {
  const callback = show([2, 5, 8], 3);
  expect(callback.mock.calls[0][0].items.map(row => row.quantity)).toEqual(['2', '1', '']);
});

test('worker transfer excludes missing, invalid and ambiguous receipt indices', () => {
  const callback = show([undefined, null, '0', true, -1, 0.5, Number.MAX_SAFE_INTEGER + 1, 4, 4, 2]);
  expect(callback.mock.calls[0][0].items).toEqual([expect.objectContaining({ invoiceLineIndex: 2 })]);
});

test('unidentified receipt cannot prepare a transfer', () => {
  const alert = jest.spyOn(window, 'alert').mockImplementation(() => {});
  try {
    expect(show([undefined])).not.toHaveBeenCalled();
    expect(alert).toHaveBeenCalled();
  } finally { alert.mockRestore(); }
});

const showPackaging = indices => render(<WarehouseInvoicesPanel
  user={{ role: 'директор' }} newInvoice={{ items: [] }} suppliers={[]} projects={[]} C={{}} card={{}} inp={{}}
  invoices={[{ id: 5, companyId: 2, project: 'Школа', items: indices.map(invoiceLineIndex => ({ ...item, invoiceLineIndex, conversionStatus: 'needs_review' })) }]}
  warehouseInvoiceItems={inv => ({ items: inv.items })} />);

test('packaging preview and saved review send original filtered index', async () => {
  const previousFetch = global.fetch;
  global.fetch = jest.fn().mockResolvedValue({ ok: true, json: async () => ({ preview: { stored: { quantity: 2, unit: 'уп' }, proposed: { quantity: 20, unit: 'м' } } }) });
  try {
    showPackaging([2]);
    fireEvent.click(screen.getByRole('button', { name: 'Предпросмотр' }));
    await screen.findByRole('button', { name: 'Зафиксировать сверку' });
    expect(JSON.parse(global.fetch.mock.calls[0][1].body)).toEqual({ warehouseInvoiceId: 5, itemIndex: 2 });
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'confirmed' } });
    fireEvent.change(screen.getByPlaceholderText('Итог ручной сверки'), { target: { value: 'Проверено' } });
    fireEvent.click(screen.getByRole('button', { name: 'Зафиксировать сверку' }));
    await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(3));
    expect(JSON.parse(global.fetch.mock.calls[1][1].body)).toMatchObject({ warehouseInvoiceId: 5, itemIndex: 2 });
    await screen.findByText(/Сверка сохранена/);
  } finally { global.fetch = previousFetch; }
});

test('packaging missing, invalid and duplicate indices are non-actionable with visible hint', () => {
  showPackaging([undefined, null, '0', -1, 0.5, true, 4, 4, 2]);
  expect(screen.getAllByRole('button', { name: 'Предпросмотр' })).toHaveLength(1);
  expect(screen.getAllByRole('button', { name: 'Создать правило' })).toHaveLength(1);
  expect(screen.getByText(/Строк упаковок без однозначного индекса: 8/)).toBeInTheDocument();
});
