import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import SupplierCabinetPage from './SupplierCabinetPage';
const initial = { materialName: 'Цемент', unit: 'шт', price: '100', minQuantity: '1', deliveryDays: '0', notes: 'Не терять' };
function Cabinet({ existing = [] }) {
  const [showCatalogForm, setShowCatalogForm] = React.useState(true);
  const [newCatalogItem, setNewCatalogItem] = React.useState(initial);
  const [supplierCatalog, setSupplierCatalog] = React.useState(existing);
  return <SupplierCabinetPage API="/api" C={{}} UNITS={['шт']} user={{ id: 7, role: 'поставщик', name: 'Поставщик' }}
    supplierTab="catalog" suppliers={[{ id: 1, userId: 7, name: 'Поставщик' }]} supplierRequisites={{}}
    setSupplierRequisites={() => {}} {...{showCatalogForm,setShowCatalogForm,newCatalogItem,setNewCatalogItem,supplierCatalog,setSupplierCatalog}} />;
}
const originalFetch = global.fetch;
beforeEach(() => { global.fetch = jest.fn(); jest.spyOn(window, 'alert').mockImplementation(() => {}); });
afterEach(() => { global.fetch = originalFetch; jest.restoreAllMocks(); });
test('rejected manual save keeps the filled form and never appends a phantom row', async () => {
  global.fetch.mockImplementation(async (_, options) => options?.method
    ? { ok: false, status: 403, json: async () => ({ detail: 'Нет доступа к каталогу' }) }
    : { ok: true, json: async () => [] });
  render(<Cabinet />);
  fireEvent.click(screen.getByRole('button', { name: 'Сохранить' }));
  await waitFor(() => expect(global.fetch.mock.calls.some(([, options]) => options?.method === 'POST')).toBe(true));
  await new Promise(resolve => setTimeout(resolve, 0));
  expect(screen.getByDisplayValue('Не терять')).toBeInTheDocument();
  expect(screen.queryByRole('cell', { name: 'Цемент' })).not.toBeInTheDocument();
});
test('rejected delete leaves the saved row visible', async () => {
  global.fetch.mockResolvedValue({ ok: false, status: 403, json: async () => ({ detail: 'Нет доступа' }) });
  const { container } = render(<Cabinet existing={[{ ...initial, id: 5, supplierId: 1, inStock: true }]} />);
  fireEvent.click(container.querySelector('tbody button'));
  await waitFor(() => expect(global.fetch).toHaveBeenCalled());
  await new Promise(resolve => setTimeout(resolve, 0));
  expect(screen.getByRole('cell', { name: 'Цемент' })).toBeInTheDocument();
});
test('confirmed save uses normalized numbers, displays stock and closes the draft', async () => {
  global.fetch.mockResolvedValueOnce({ ok: true, json: async () => [] })
    .mockResolvedValueOnce({ ok: true, json: async () => ({ id: 5 }) });
  render(<Cabinet />);
  fireEvent.click(screen.getByRole('button', { name: 'Сохранить' }));
  await screen.findByRole('cell', { name: 'Цемент' });
  expect(screen.getByRole('cell', { name: '✅ Есть' })).toBeInTheDocument();
  expect(screen.queryByDisplayValue('Не терять')).not.toBeInTheDocument();
  expect(JSON.parse(global.fetch.mock.calls[1][1].body)).toMatchObject({ price: 100, minQuantity: 1, deliveryDays: 0, inStock: true });
});
test('duplicate check preserves draft and sends no new POST', async () => {
  global.fetch.mockResolvedValue({ ok: true, json: async () => [{ ...initial, supplierId: 1, id: 9 }] });
  render(<Cabinet />); fireEvent.click(screen.getByRole('button', { name: 'Сохранить' }));
  await screen.findByRole('alert');
  expect(screen.getByDisplayValue('Не терять')).toBeInTheDocument();
  expect(global.fetch).toHaveBeenCalledTimes(1);
});
test('invalid quantity never reaches the server', async () => {
  render(<Cabinet />);
  fireEvent.change(screen.getByPlaceholderText('Мин. партия'), { target: { value: '-1' } });
  fireEvent.click(screen.getByRole('button', { name: 'Сохранить' }));
  await screen.findByRole('alert'); expect(global.fetch).not.toHaveBeenCalled();
});
test('confirmed delete removes only the requested row', async () => {
  global.fetch.mockResolvedValue({ ok: true, json: async () => ({ ok: true }) });
  render(<Cabinet existing={[{ ...initial, id: 5, supplierId: 1 }, { ...initial, id: 6, supplierId: 1, materialName: 'Песок' }]} />);
  fireEvent.click(screen.getByRole('button', { name: 'Удалить Цемент' }));
  await waitFor(() => expect(screen.queryByRole('cell', { name: 'Цемент' })).not.toBeInTheDocument());
  expect(screen.getByRole('cell', { name: 'Песок' })).toBeInTheDocument();
});
