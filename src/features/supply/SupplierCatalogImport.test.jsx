import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import * as XLSX from 'xlsx';
import SupplierCatalogImport from './SupplierCatalogImport';
const header = ['Наименование', 'Ед.', 'Цена', 'Мин. партия', 'Поставка', 'Примечание'];
function file(rows) {
  const book = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(book, XLSX.utils.aoa_to_sheet([header, ...rows]), 'Каталог');
  return new File([XLSX.write(book, { type: 'array', bookType: 'xlsx' })], 'Каталог.xlsx');
}
const reply = data => ({ ok: true, json: async () => data });
function mount() {
  const onSaved = jest.fn();
  const result = render(<SupplierCatalogImport API="/api" supplierId={1} supplierName="Поставщик" catalog={[]} onSaved={onSaved} />);
  return { ...result, onSaved };
}
async function upload(rows) {
  fireEvent.change(screen.getByLabelText('Файл каталога'), { target: { files: [file(rows)] } });
  await screen.findByRole('button', { name: /Импортировать/ });
}
const originalFetch = global.fetch;
beforeEach(() => { global.fetch = jest.fn(); });
afterEach(() => { global.fetch = originalFetch; });
it('blocks the whole file for an invalid row and never sends a POST', async () => {
  mount(); await upload([['Цемент', 'шт', 100], ['Песок', 'т', 'сто']]);
  expect(screen.getByRole('alert')).toHaveTextContent('Строка 3');
  expect(screen.getByRole('button', { name: /Импортировать/ })).toBeDisabled();
  expect(global.fetch).not.toHaveBeenCalled();
});
it('refreshes duplicates before writing and counts only confirmed saves', async () => {
  const { onSaved } = mount();
  global.fetch.mockResolvedValueOnce(reply([{ id: 1, supplierId: 1, materialName: 'Цемент', unit: 'шт' }]))
    .mockResolvedValueOnce(reply({ id: 2 }));
  await upload([['Цемент', 'шт', 100], ['Песок', 'т', 200]]);
  fireEvent.click(screen.getByRole('button', { name: /Импортировать/ }));
  await screen.findByText('Импортировано: 1. Пропущено совпадений: 1.');
  expect(global.fetch).toHaveBeenCalledTimes(2);
  expect(onSaved.mock.calls[0][0]([])).toMatchObject([{ id: 2, materialName: 'Песок', inStock: true }]);
});
it('stops after a lost response and does not claim the unknown row succeeded', async () => {
  const { onSaved } = mount();
  global.fetch.mockResolvedValueOnce(reply([])).mockResolvedValueOnce(reply({ id: 1 }))
    .mockRejectedValueOnce(new Error('Соединение потеряно'));
  await upload([['Цемент', 'шт', 100], ['Песок', 'т', 200], ['Кирпич', 'шт', 300]]);
  fireEvent.click(screen.getByRole('button', { name: /Импортировать/ }));
  await screen.findByText(/Подтверждено сохранений: 1\. Строка 3:/);
  expect(onSaved).toHaveBeenCalledTimes(1);
  expect(global.fetch).toHaveBeenCalledTimes(3);
  expect(screen.queryByRole('button', { name: /Импортировать/ })).not.toBeInTheDocument();
});
it('disables import while pending and stops remaining writes after unmount', async () => {
  const { unmount, onSaved } = mount();
  let finish;
  global.fetch.mockResolvedValueOnce(reply([])).mockImplementationOnce(() => new Promise(resolve => { finish = resolve; }));
  await upload([['Цемент', 'шт', 100], ['Песок', 'т', 200]]);
  fireEvent.click(screen.getByRole('button', { name: /Импортировать/ }));
  await waitFor(() => expect(finish).toBeDefined());
  expect(screen.getByLabelText('Файл каталога')).toBeDisabled();
  unmount(); finish(reply({ id: 1 }));
  await new Promise(resolve => setTimeout(resolve, 0));
  expect(onSaved).not.toHaveBeenCalled(); expect(global.fetch).toHaveBeenCalledTimes(2);
});
it('keeps UTF-8 CSV names and comma decimal prices intact', async () => {
  const { onSaved } = mount();
  const csv = new File(['Наименование;Ед.;Цена;Мин. партия;Поставка;Примечание\nПесок CSV;т;120,50;1;0;Тест'], 'catalog.csv');
  global.fetch.mockResolvedValueOnce(reply([])).mockResolvedValueOnce(reply({ id: 10 }));
  fireEvent.change(screen.getByLabelText('Файл каталога'), { target: { files: [csv] } });
  const button = await screen.findByRole('button', { name: 'Импортировать 1 позиций' });
  fireEvent.click(button);
  await screen.findByText('Импортировано: 1. Пропущено совпадений: 0.');
  expect(onSaved.mock.calls[0][0]([])).toMatchObject([{ materialName: 'Песок CSV', price: 120.5 }]);
});
it('does not write while a manual catalogue operation owns the lock', async () => {
  const mutationLock = { current: true };
  render(<SupplierCatalogImport API="/api" supplierId={1} catalog={[]} onSaved={jest.fn()} mutationLock={mutationLock} />);
  await upload([['Цемент', 'шт', 100]]);
  fireEvent.click(screen.getByRole('button', { name: /Импортировать/ }));
  await screen.findByText('Дождитесь завершения другой операции с каталогом.');
  expect(global.fetch).not.toHaveBeenCalled(); expect(mutationLock.current).toBe(true);
});
