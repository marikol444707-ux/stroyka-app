import { prepareCatalogImport, catalogResponse } from './supplierCatalogImportUtils';
const header = ['Наименование', 'Ед.', 'Цена', 'Мин. партия', 'Поставка', 'Примечание'];
it('accepts Russian decimal prices and preserves zero delivery days', () => {
  expect(prepareCatalogImport([header, ['Цемент', 'шт', '1 234,50', '0,5', 0]], [], 1).items[0].item)
    .toMatchObject({ price: 1234.5, minQuantity: 0.5, deliveryDays: 0, inStock: true });
});
it.each(['нет', -1, Infinity, '12 34', '1,2,3'])('rejects invalid price %s before saving', price => {
  expect(prepareCatalogImport([header, ['Цемент', 'шт', price]]).errors).toHaveLength(1);
});
it('does not silently skip data without a header', () => {
  expect(() => prepareCatalogImport([['Цемент', 'шт', 12]])).toThrow('Первая строка');
});
it('reports missing names and fractional days with source row numbers', () => {
  expect(prepareCatalogImport([header, [], ['', 'шт', 12], ['Цемент', 'шт', 12, 1, 1.5]]).errors)
    .toEqual([expect.stringContaining('Строка 3'), expect.stringContaining('Строка 4')]);
});
it('skips duplicate names and units only within the selected supplier', () => {
  const plan = prepareCatalogImport([header, [' цемент ', 'ШТ', 12], ['Песок', 'т', 10], ['ПЕСОК', 'т', 20]],
    [{ supplierId: 1, materialName: 'Цемент', unit: 'шт' }, { supplierId: 2, materialName: 'Песок', unit: 'т' }], 1);
  expect(plan.skipped).toBe(2); expect(plan.items).toHaveLength(1);
});
it('rejects error responses and ambiguous successes', async () => {
  await expect(catalogResponse({ ok: false, status: 502, json: async () => { throw Error(); } }, true)).rejects.toThrow('502');
  await expect(catalogResponse({ ok: true, json: async () => ({ ok: true }) }, true)).rejects.toThrow('не подтвердил');
});
it('rejects swapped optional columns instead of exchanging delivery and minimum', () => {
  expect(() => prepareCatalogImport([[...header.slice(0, 3), 'Поставка', 'Мин. партия', 'Примечание'], ['Цемент', 'шт', 12, 5, 1]])).toThrow('Первая строка');
});
it('rejects values which exceed database field limits before writing', () => {
  expect(prepareCatalogImport([header, ['Цемент', 'x'.repeat(51), 12], ['Песок', 'т', 12, 1, 2147483648]]).errors).toHaveLength(2);
});
it('rejects text with NUL before any request', () => {
  expect(prepareCatalogImport([header, ['Цемент', 'шт', 12, 1, 3, 'note\u0000text']]).errors).toHaveLength(1);
});
