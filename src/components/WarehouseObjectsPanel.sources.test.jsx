import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import WarehouseObjectsPanel from './WarehouseObjectsPanel';

const stock = { id: 7, companyId: 2, name: 'Кабель', project: 'Школа', workPackage: 'Электрика', unit: 'м', quantity: 3 };
const source = (invoiceLineIndex, quantity = '1') => ({ materialName: 'Кабель', workPackage: 'Электрика', unit: 'м', quantity, invoiceId: 5, invoiceLineIndex });
function Editor({ initialItems, stockQuantity = 3 }) {
  const [form, setForm] = React.useState({ items: initialItems, invoiceId: 5, invoiceLineIndex: 2, toPerson: 'Иван', toPersonRole: 'мастер', toUserId: 1, transferDate: '2026-09-16', notes: '' });
  return <><WarehouseObjectsPanel C={{}} card={{}} inp={{}} selectedWarehouseProject="Школа"
    projects={[{ id: 1, companyId: 2, name: 'Школа' }]} visibleActiveProjects={v => v}
    materials={[{ ...stock, quantity: stockQuantity }]} user={{ role: 'кладовщик', name: 'Тест' }}
    renderMaterialReconciliationPanel={() => null}
    newTransfer={form} setNewTransfer={setForm} showTransferForm setShowTransferForm={() => {}}
    supplyRequests={[]} staff={[{ id: 1, name: 'Иван', role: 'мастер', project: 'Школа' }]}
    setMaterialTransfers={() => {}} setMaterials={() => {}} notify={() => {}} />
    <output data-testid="editor-state">{JSON.stringify(form.items)}</output></>;
}
const rows = () => JSON.parse(screen.getByTestId('editor-state').textContent);

test('editing and removing one sourced line leaves its same-name sibling unchanged', () => {
  render(<Editor initialItems={[source(2), source(5)]} />);
  fireEvent.change(screen.getAllByPlaceholderText('Кол-во *')[0], { target: { value: '2' } });
  expect(rows().map(row => row.quantity)).toEqual(['2', '1']);
  fireEvent.click(screen.getByRole('button', { name: /Удалить.*строка 3/ }));
  expect(rows()).toEqual([expect.objectContaining({ invoiceId: 5, invoiceLineIndex: 5, quantity: '1' })]);
});

test('unsourced material selection still toggles one ordinary row without removing sourced lines', () => {
  render(<Editor initialItems={[source(2)]} />);
  const checkbox = screen.getByRole('checkbox');
  expect(checkbox).not.toBeChecked();
  fireEvent.click(checkbox);
  expect(rows()).toHaveLength(2);
  expect(rows()[1]).toMatchObject({ invoiceId: null, invoiceLineIndex: null });
  fireEvent.click(checkbox);
  expect(rows()).toEqual([expect.objectContaining({ invoiceLineIndex: 2 })]);
});

test('aggregate overstock blocks every request before sequential submission', () => {
  const previousFetch = global.fetch;
  global.fetch = jest.fn().mockResolvedValue({ ok: true, json: async () => ({ ok: true, id: 1 }) });
  try {
    render(<Editor initialItems={[source(2, '2'), source(5, '2')]} />);
    expect(screen.getByRole('button', { name: 'Передать' })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: 'Передать' }));
    expect(global.fetch).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: 'Передать' })).toBeDisabled();
    expect(screen.getByText(/Нельзя выдать больше остатка/)).toBeInTheDocument();
  } finally { global.fetch = previousFetch; }
});

test('valid separate rows submit original identities; ordinary row never inherits parent source', async () => {
  const previousFetch = global.fetch;
  global.fetch = jest.fn().mockResolvedValue({ ok: true, json: async () => ({ ok: true, id: 1 }) });
  try {
    render(<Editor initialItems={[source(2), source(5), { ...source(null), invoiceId: null }]} />);
    fireEvent.click(screen.getByRole('button', { name: 'Передать' }));
    await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(3));
    expect(global.fetch.mock.calls.map(([, options]) => {
      const body = JSON.parse(options.body);
      return [body.invoiceId, body.invoiceLineIndex];
    })).toEqual([[5, 2], [5, 5], [null, null]]);
  } finally { global.fetch = previousFetch; }
});
