import { templateItemsForProject, templatePayload } from './templateItems';

const row = { materialName: 'Цемент', quantity: '1', unit: 'меш', workPackage: 'Стены' };

test('section mapping preserves valid sections, clears invalid ones and uses a sole section as fallback', () => {
  expect(templateItemsForProject([row, { ...row, workPackage: 'Чужой' }], ['Стены', 'Кровля']))
    .toEqual([row, { ...row, workPackage: '' }]);
  expect(templateItemsForProject([{ ...row, workPackage: 'Чужой' }], ['Единственный']))
    .toEqual([{ ...row, workPackage: 'Единственный' }]);
});

test.each([
  ['quantity with more than six decimals', { ...row, quantity: '1.0000001' }],
  ['section longer than 255 characters', { ...row, workPackage: 'Р'.repeat(256) }],
])('template payload rejects %s', (_case, invalidRow) => {
  expect(() => templatePayload('Набор', { category: '', items: [invalidRow] })).toThrow();
});

test('template payload rejects a category longer than the request category limit', () => {
  expect(() => templatePayload('Набор', { category: 'К'.repeat(101), items: [row] })).toThrow();
});
