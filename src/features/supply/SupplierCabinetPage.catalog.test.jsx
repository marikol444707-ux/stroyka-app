import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import * as XLSX from 'xlsx';
import SupplierCabinetPage from './SupplierCabinetPage';

it('does not add a rejected imported row to the displayed catalog', async () => {
  const originalFetch = global.fetch;
  const book = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(book, XLSX.utils.aoa_to_sheet([
    ['Наименование', 'Ед.', 'Цена', 'Мин. партия', 'Поставка', 'Примечание'],
    ['Цемент', 'шт', 100, 1, 3, ''],
  ]), 'Каталог');
  const bytes = XLSX.write(book, { type: 'array', bookType: 'xlsx' });
  global.fetch = jest.fn(async (url, options) => {
    if (String(url).includes('corsproxy')) return { ok: true, blob: async () => new Blob([bytes]) };
    if (!options?.method) return { ok: true, json: async () => [] };
    return { ok: false, status: 403, json: async () => ({ detail: 'Нет доступа к каталогу' }) };
  });
  const alert = jest.spyOn(window, 'alert').mockImplementation(() => {});
  const setSupplierCatalog = jest.fn();
  try {
    render(<SupplierCabinetPage API="/api" C={{}} user={{ id: 7, role: 'поставщик', name: 'Поставщик' }}
      supplierTab="catalog" suppliers={[{ id: 1, userId: 7, name: 'Поставщик' }]}
      supplierRequisites={{ priceUrl: 'https://example.test/price.xlsx' }}
      supplierCatalog={[]} setSupplierCatalog={setSupplierCatalog} setSupplierRequisites={() => {}} />);
    fireEvent.click(screen.getByRole('button', { name: 'По ссылке' }));
    await waitFor(() => {
      const confirm = screen.queryByRole('button', { name: /Импортировать/ });
      if (confirm) fireEvent.click(confirm);
      expect(global.fetch.mock.calls.some(([, options]) => options?.method === 'POST')).toBe(true);
    });
    await screen.findByText(/Подтверждено сохранений: 0/);
    expect(setSupplierCatalog).not.toHaveBeenCalled();
  } finally { global.fetch = originalFetch; alert.mockRestore(); }
});
