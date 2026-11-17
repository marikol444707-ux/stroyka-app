import { ks2ItemsFromActiveEstimates } from './projectEstimateItemsUtils';
import { createDocumentActions } from '../features/documents/documentActions';

const project = { id: 12, companyId: 2, name: 'Тестовый объект' };
const entry = { project: project.name, estimateItemKey: '7:0:0', status: 'Подтверждено', quantity: 0.25 };
const item = { type: 'work', name: 'Бетонирование', unit: 'м3', quantity: 0.5, priceWork: 80, priceMaterial: 20 };
const estimate = row => [{ id: 7, sections: [{ name: 'Работы', items: [row] }] }];
const rows = (row = item, journal = [entry]) => ks2ItemsFromActiveEstimates({ project, activeEstimates: estimate(row), workJournal: journal });

test.each([0.5, 0.25, 1, 2])('unit price is not reduced for planned volume %s', quantity => {
  expect(rows({ ...item, quantity })[0]).toMatchObject({ pricePerUnit: 100, quantity: 0.25, total: 25 });
});

test('imported amount is divided by the actual fractional volume', () => {
  expect(rows({ ...item, isImported: true, totalWork: 60, totalMaterial: 40 })[0])
    .toMatchObject({ pricePerUnit: 200, quantity: 0.25, total: 50 });
});

test('saved customer amount remains authoritative; pending works are excluded', () => {
  expect(rows(item, [{ ...entry, customerTotal: 35 }, { ...entry, status: 'На проверке', quantity: 100 }])[0])
    .toMatchObject({ pricePerUnit: 100, quantity: 0.25, total: 35 });
});

test('legacy doneQuantity without a journal retains the same calculation', () => {
  expect(rows({ ...item, doneQuantity: 0.25 }, [])[0]).toMatchObject({ pricePerUnit: 100, quantity: 0.25, total: 25 });
});

test.each([0, -1, 'bad', Infinity])('invalid planned volume %s never invents a unit price', quantity => {
  const result = rows({ ...item, isImported: true, totalWork: 50, totalMaterial: 0, quantity });
  expect(result[0]).toMatchObject({ pricePerUnit: 0, total: 0 });
});

test('confirmed fractional work reaches both actual KS document actions with the same total', () => {
  const showPreview = jest.fn();
  const actions = createDocumentActions({ workJournal: [entry],
    ks2ItemsFromEstimate: () => rows(), estimateChangeRowsForDocs: () => [], showPreview });
  actions.showKS2(project);
  const ks2 = new DOMParser().parseFromString(showPreview.mock.calls[0][0], 'text/html');
  const row = [...ks2.querySelectorAll('tr')].find(tr => tr.textContent.includes(item.name));
  expect([...row.cells].slice(3).map(cell => cell.textContent)).toEqual(['0.25', '100', '25']);
  expect(ks2.body.textContent).toContain('ВСЕГО к оплате: 25 руб.');
  const ks3 = new DOMParser().parseFromString(actions.buildKS3Content(project), 'text/html');
  const total = [...ks3.querySelectorAll('tr')].find(tr => tr.textContent.includes('ИТОГО выполнено работ:'));
  expect(total.cells[1].textContent).toBe('25 руб.');
});
