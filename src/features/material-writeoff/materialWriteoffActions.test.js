import { createMaterialWriteoffActions } from './materialWriteoffActions';
import { materialLookupText } from '../../utils/materialMatchUtils';

describe('preparing factual material usage for a group of works', () => {
  let previousFlag;
  const item = (quantity, extra = {}) => ({
    name: 'Клей', unit: 'кг', quantity, workPackage: 'Основная', ...extra,
  });
  const stock = (extra = {}) => ({
    name: 'Клей', unit: 'кг', quantity: 5, personalAvailable: 2, warehouseAvailable: 3,
    warehouseMaterialId: 31, sourceConflict: false, materialAccountingVersion: 2, ...extra,
  });
  const actionsFor = (available = stock(), extra = {}) => createMaterialWriteoffActions({
    C: {}, MaterialWriteoffStatus: () => null, isMobile: false,
    canonicalMaterialMeta: (_project, name, unit) => ({ name, unit }),
    fmtMeasure: (quantity, unit) => `${quantity} ${unit}`,
    isPersonalMaterialRole: () => true,
    materialAvailabilityMapForWork: () => ({ [materialLookupText('Клей')]: available }),
    materialNameKey: materialLookupText,
    setEstimateWorkMaterials: jest.fn(), setSelectedWorks: jest.fn(),
    confirmFn: jest.fn(), promptFn: jest.fn(), ...extra,
  });

  beforeEach(() => {
    previousFlag = process.env.REACT_APP_WORK_MATERIAL_ACCOUNTING_ENABLED;
    process.env.REACT_APP_WORK_MATERIAL_ACCOUNTING_ENABLED = '1';
  });
  afterEach(() => {
    if (previousFlag === undefined) delete process.env.REACT_APP_WORK_MATERIAL_ACCOUNTING_ENABLED;
    else process.env.REACT_APP_WORK_MATERIAL_ACCOUNTING_ENABLED = previousFlag;
  });

  test('two work groups share one personal balance and only the remainder comes from warehouse', () => {
    const available = Object.freeze(stock());
    const groups = Object.freeze([
      Object.freeze([Object.freeze(item(2))]),
      Object.freeze([Object.freeze(item(2))]),
    ]);
    const result = actionsFor(available).prepareWorkMaterialGroups('Объект', groups);
    expect(result[0][0]).toMatchObject({ quantity: 2, personalQuantity: 2, warehouseQuantity: 0 });
    expect(result[1][0]).toMatchObject({ quantity: 2, personalQuantity: 0,
      warehouseQuantity: 2, warehouseMaterialId: 31 });
    expect(available).toEqual(stock());
    expect(groups[0][0]).toEqual(item(2));
    expect(groups[1][0]).toEqual(item(2));
  });

  test('a later aggregate shortage stops preparation before any work group can be posted', () => {
    const post = jest.fn();
    const actions = actionsFor();
    expect(() => actions.prepareWorkMaterialGroups('Объект', [[item(4)], [item(2)]]).forEach(post))
      .toThrow(/Недостаточно/);
    expect(post).not.toHaveBeenCalled();
  });

  test('explicit warehouse preference preserves personal stock for the next work', () => {
    const result = actionsFor().prepareWorkMaterialGroups('Объект', [
      [item(2, { sourcePreference: 'warehouse' })], [item(2)],
    ]);
    expect(result[0][0]).toMatchObject({ quantity: 2, personalQuantity: 0,
      warehouseQuantity: 2, warehouseMaterialId: 31 });
    expect(result[1][0]).toMatchObject({ quantity: 2, personalQuantity: 2, warehouseQuantity: 0 });
  });

  test('canonical aliases in different work groups share the same remaining source stock', () => {
    const actions = actionsFor(stock(), {
      canonicalMaterialMeta: (_project, name, unit) => ({ name: name === 'Марка клея' ? 'Клей' : name, unit }),
    });
    const result = actions.prepareWorkMaterialGroups('Объект', [[item(2)], [item(2, { name: 'Марка клея' })]]);
    expect(result[1][0]).toMatchObject({ personalQuantity: 0, warehouseQuantity: 2, warehouseMaterialId: 31 });
  });

  test('v2 keeps the full norm quantity and displays shortage rather than reducing the norm', () => {
    const actions = actionsFor();
    const quantity = actions.capMaterialWriteoffQty('Объект', 'Клей', 8, 'Основная');
    expect(quantity).toBe(8);
    expect(actions.materialWriteoffRows('Объект', [item(quantity, { normQuantity: 8 })])[0])
      .toMatchObject({ quantity: 8, qty: 8, normQty: 8, overNorm: false, overStock: true,
        personalQuantity: 2, warehouseQuantity: 6 });
  });

  test('disabled v2 keeps legacy quantity capping and does not rewrite existing material groups', () => {
    process.env.REACT_APP_WORK_MATERIAL_ACCOUNTING_ENABLED = '0';
    const actions = actionsFor();
    expect(actions.capMaterialWriteoffQty('Объект', 'Клей', 8, 'Основная')).toBe(5);
    const groups = [[item(2)], [item(2)]];
    expect(actions.prepareWorkMaterialGroups('Объект', groups)).toBe(groups);
  });

  test('valid explicit v2 sources remain exactly visible in the writeoff preview', () => {
    const actions = actionsFor(stock({ quantity: 0.3, personalAvailable: 0.1, warehouseAvailable: 0.2 }));
    const material = item(0.3, { materialAccountingVersion: 2, personalQuantity: 0.1,
      warehouseQuantity: 0.2, warehouseMaterialId: 31 });
    expect(actions.materialWriteoffRows('Объект', [material])[0]).toMatchObject({
      qty: 0.3, personalQuantity: 0.1, warehouseQuantity: 0.2, available: 0.3,
      restAfter: 0, overStock: false, sourceConflict: false,
    });
    expect(actions.materialWriteoffBlockMessage('Объект', [material])).toBe('');
  });

  test('v2 preview blocks explicit source totals that differ from factual consumption', () => {
    const actions = actionsFor();
    const material = item(2, { materialAccountingVersion: 2, personalQuantity: 1,
      warehouseQuantity: 0, warehouseMaterialId: null });
    expect(actions.materialWriteoffRows('Объект', [material])[0].overStock).toBe(true);
    expect(actions.materialWriteoffBlockMessage('Объект', [material])).not.toBe('');
  });

  test('v2 preview rejects a typed unit mismatch even when a canonical alias hides it', () => {
    const actions = actionsFor(stock(), {
      canonicalMaterialMeta: (_project, name) => ({ name, unit: 'кг' }),
    });
    const material = item(1, { unit: 'т', materialAccountingVersion: 2,
      personalQuantity: 0, warehouseQuantity: 1, warehouseMaterialId: 31 });
    expect(actions.materialWriteoffRows('Объект', [material])[0].overStock).toBe(true);
    expect(actions.materialWriteoffBlockMessage('Объект', [material])).not.toBe('');
  });

  test('equivalent normalized unit spellings remain valid for preview and allocation', () => {
    const actions = actionsFor();
    const material = item(1, { unit: 'kg', materialAccountingVersion: 2,
      personalQuantity: 0, warehouseQuantity: 1, warehouseMaterialId: 31 });
    expect(actions.materialWriteoffRows('Объект', [material])[0].overStock).toBe(false);
    expect(actions.materialWriteoffBlockMessage('Объект', [material])).toBe('');
  });

  test('v2 preview does not accept source quantities beyond six decimal places', () => {
    const actions = actionsFor();
    const material = item(0.3000001, { materialAccountingVersion: 2,
      personalQuantity: 0.1000001, warehouseQuantity: 0.2, warehouseMaterialId: 31 });
    expect(actions.materialWriteoffRows('Объект', [material])[0].overStock).toBe(true);
    expect(actions.materialWriteoffBlockMessage('Объект', [material])).not.toBe('');
  });
});
