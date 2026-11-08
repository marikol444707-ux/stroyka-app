import { createMaterialRuntime } from '../features/material-control/materialRuntime';
import { projectMaterialCost } from './projectEconomyUtils';

const project = { id: 11, companyId: 7, name: 'Тестовый корпус' };
const delivery = (overrides = {}) => ({
  id: 31, companyId: 7, project: project.name,
  materialName: 'Кабель ВВГ', unit: 'м', workPackage: 'Электрика',
  status: 'Проблема', shippedQuantity: 10, receivedQuantity: 4,
  pricePerUnit: 100, totalPrice: 1000,
  ...overrides,
});
const receipt = (overrides = {}, lineOverrides = {}) => ({
  id: 51, companyId: 7, project: project.name, location: project.name,
  sourceType: 'supply_delivery', sourceId: 31, supplyDeliveryId: 31,
  status: 'Принята', totalWithVat: 480, workPackage: 'Электрика',
  items: [{ name: 'Кабель ВВГ', quantity: 4, unit: 'м', price: 100,
    total: 480, deliveryId: 31, workPackage: 'Электрика', ...lineOverrides }],
  ...overrides,
});

// Exercise the real application selector, including invoice classification and
// receipt-item extraction, then follow its result into the economy consumer.
const runtime = (overrides = {}) => createMaterialRuntime({
  activeEstimatesForProject: () => [], estimateWorkNormRequirementRows: () => [],
  canonicalCompanyName: '', companyRequisites: {},
  companyContext: { mode: 'company', selectedCompanyId: 7 }, materialAliasesError: '',
  history: [], invoices: [], materialAliases: [], materialInspections: [],
  materialNormOverrides: [], materialNorms: [], materials: [], materialTransfers: [],
  parseSupplyItems: () => [], projects: [project], supplyDeliveries: [delivery()],
  supplyHistory: [], supplyRequests: [], user: {}, warehouseMain: [],
  warehouseMovements: [], workJournal: [], ...overrides,
});

const assertAccepted = (app, quantity, amount) => {
  const rows = app.materialReconciliationRows(project);
  expect(rows).toHaveLength(1);
  expect(rows[0]).toMatchObject({ received: quantity, supplyReceived: quantity, receivedSum: amount });
  expect(app.materialControlSummaryForProject(project).suppliedSum).toBe(amount);
  expect(projectMaterialCost(project, app.materialControlSummaryForProject)).toBe(amount);
  return rows[0];
};

describe('accepted material cost through the real application selectors', () => {
  test('10 shipped and 4 accepted at 100 cost 400, not the 1000 shipment face value', () => {
    const source = delivery();
    assertAccepted(runtime({ supplyDeliveries: [source] }), 4, 400);
    expect(source.totalPrice).toBe(1000);
    expect(source.receivedQuantity).toBe(4);
  });

  test('one exact saved receipt gross amount wins without double counting quantity or adding VAT again', () => {
    const invoice = receipt();
    const before = JSON.stringify(invoice);
    const row = assertAccepted(runtime({ invoices: [invoice] }), 4, 480);
    expect(row.invoiceDetails).toEqual([]);
    expect(row.supplyDetails).toHaveLength(1);
    expect(row.supplyDetails[0]).toMatchObject({ id: 31, total: 480, qty: 4 });
    expect(JSON.stringify(invoice)).toBe(before);
  });

  test('sourceType/sourceId linkage works when the older API has no supplyDeliveryId', () => {
    assertAccepted(runtime({ invoices: [receipt({ supplyDeliveryId: undefined })] }), 4, 480);
  });

  test.each([
    ['company', { companyId: 8 }, {}],
    ['project', { project: 'Другой корпус', location: 'Другой корпус' }, {}],
    ['delivery', { sourceId: 99, supplyDeliveryId: 99 }, {}],
    ['conflicting delivery identifiers', { sourceId: 99 }, {}],
    ['cancelled receipt', { status: 'Аннулирована' }, {}],
    ['material', {}, { name: 'Другой кабель' }],
    ['unit', {}, { unit: 'шт' }],
    ['quantity', {}, { quantity: 10 }],
    ['package', {}, { workPackage: 'Общестрой' }],
    ['line delivery', {}, { deliveryId: 99 }],
    ['absent amount', {}, { total: null }],
    ['invalid amount', {}, { total: 'неизвестно' }],
  ])('does not use mismatching %s as receipt amount evidence', (_case, invoiceChanges, lineChanges) => {
    assertAccepted(runtime({ invoices: [receipt(invoiceChanges, lineChanges)] }), 4, 400);
  });

  test('two matching receipt IDs are ambiguous instead of summing or choosing an arbitrary gross amount', () => {
    assertAccepted(runtime({ invoices: [receipt(), receipt({ id: 52 }, { total: 600 })] }), 4, 400);
  });

  test('multi-line receipt totals are not assigned wholesale to one delivery', () => {
    const invoice = receipt();
    invoice.items.push({ name: 'Крепёж', unit: 'шт', quantity: 1, total: 200 });
    assertAccepted(runtime({ invoices: [invoice] }), 4, 400);
  });

  test('an empty saved receipt is not reconstructed from today\'s stock to establish a gross amount', () => {
    assertAccepted(runtime({
      invoices: [receipt({ items: [] })],
      materials: [{ id: 61, project: project.name, name: 'Кабель ВВГ', unit: 'м',
        workPackage: 'Электрика', quantity: 4, price: 999 }],
    }), 4, 400);
  });

  test('recorded zero accepted quantity suppresses older delivered history and stock-value fallback', () => {
    const row = assertAccepted(runtime({
      supplyDeliveries: [delivery({ receivedQuantity: 0 })],
      supplyHistory: [{ id: 71, project: project.name, materialName: 'Кабель ВВГ',
        unit: 'м', workPackage: 'Электрика', status: 'Доставлено', quantity: 10, totalPrice: 1000 }],
      materials: [{ id: 61, project: project.name, name: 'Кабель ВВГ', unit: 'м',
        workPackage: 'Электрика', quantity: 10, price: 100 }],
    }), 0, 0);
    expect(row.stock).toBe(10);
    expect(row.supplyDetails).toHaveLength(1);
    expect(row.supplyDetails[0]).toMatchObject({ id: 31, qty: 0, total: 0 });
  });

  test('a saved zero gross amount remains zero even with a priced stock balance', () => {
    assertAccepted(runtime({
      invoices: [receipt({}, { total: 0 })],
      materials: [{ id: 61, project: project.name, name: 'Кабель ВВГ', unit: 'м',
        workPackage: 'Электрика', quantity: 4, price: 100 }],
    }), 4, 0);
  });

  test.each([null, undefined, '', 'неизвестно', -1, Infinity, true])(
    'invalid or absent accepted quantity %p does not become accepted quantity or money', quantity => {
      const app = runtime({ supplyDeliveries: [delivery({ receivedQuantity: quantity })] });
      expect(app.materialReconciliationRows(project)).toEqual([]);
      expect(app.materialControlSummaryForProject(project).suppliedSum).toBe(0);
    },
  );

  test.each([
    [0.015, 0.01], [0.125, 0.12], [0.375, 0.38], [1.225, 1.23], [2.675, 2.67],
  ])('fallback price %s matches the existing receipt writer round(float, 2) = %s', (price, amount) => {
    assertAccepted(runtime({ supplyDeliveries: [delivery({ receivedQuantity: 1, pricePerUnit: price })] }), 1, amount);
  });

  test('pending delivery does not establish accepted cost from shipment quantity', () => {
    const app = runtime({ supplyDeliveries: [delivery({ status: 'В пути', receivedQuantity: 0 })] });
    const [row] = app.materialReconciliationRows(project);
    expect(row).toMatchObject({ inTransit: 10, received: 0, receivedSum: 0 });
    expect(app.materialControlSummaryForProject(project).suppliedSum).toBe(0);
  });
});
