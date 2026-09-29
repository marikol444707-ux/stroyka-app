import { buildWorkMaterialAvailability, allocateWorkMaterialSources } from './materialSources';
import { materialLookupText } from '../../utils/materialMatchUtils';

describe('work material source availability', () => {
  const defaults = {
    projectName: 'Объект', workPackage: 'Основная',
    canonicalMaterialMeta: (_project, name, unit) => ({ name, unit }),
    materialNameKey: materialLookupText,
  };
  const personal = (overrides = {}) => ({
    name: 'Клей', unit: 'кг', quantity: 2, project: 'Объект',
    workPackage: 'Основная', ...overrides,
  });
  const warehouse = (overrides = {}) => ({
    id: 31, name: 'Клей', unit: 'кг', quantity: 3, project: 'Объект',
    workPackage: 'Основная', ...overrides,
  });
  const availability = (overrides = {}) => buildWorkMaterialAvailability({
    ...defaults, personalRows: [], warehouseRows: [], ...overrides,
  });
  const glue = result => result[materialLookupText('Клей')];

  test('combines personal and one exact warehouse source without losing either quantity', () => {
    expect(glue(availability({ personalRows: [personal()], warehouseRows: [warehouse()] })))
      .toMatchObject({ quantity: 5, personalAvailable: 2, warehouseAvailable: 3,
        warehouseMaterialId: 31, unit: 'кг', sourceConflict: false, materialAccountingVersion: 2 });
  });

  test('does not include another project or another work package', () => {
    expect(glue(availability({
      personalRows: [personal(), personal({ quantity: 99, workPackage: 'Электрика' }),
        personal({ quantity: 99, project: 'Другой объект' })],
      warehouseRows: [warehouse(), warehouse({ id: 32, quantity: 99, workPackage: 'Электрика' }),
        warehouse({ id: 33, quantity: 99, project: 'Другой объект' })],
    }))).toMatchObject({ quantity: 5, personalAvailable: 2, warehouseAvailable: 3,
      warehouseMaterialId: 31, sourceConflict: false });
  });

  test('blank package means Основная rather than every package', () => {
    const rows = [warehouse({ workPackage: '' }), warehouse({ id: 32, workPackage: 'Электрика' })];
    expect(glue(availability({ workPackage: '', warehouseRows: rows })))
      .toMatchObject({ quantity: 3, warehouseAvailable: 3, warehouseMaterialId: 31, sourceConflict: false });
    expect(glue(availability({ workPackage: 'Электрика', warehouseRows: rows })))
      .toMatchObject({ quantity: 3, warehouseAvailable: 3, warehouseMaterialId: 32, sourceConflict: false });
  });

  test.each([undefined, null, 0, -1, 1.5, '31', true, Number.MAX_SAFE_INTEGER + 1])(
    'warehouse identifier %p cannot create available stock', id => {
      const row = glue(availability({ warehouseRows: [warehouse({ id })] }));
      expect(row?.warehouseAvailable || 0).toBe(0);
      expect(row?.warehouseMaterialId ?? null).toBeNull();
    },
  );

  test('canonical aliases and equivalent unit spellings share one available material', () => {
    const result = availability({
      canonicalMaterialMeta: (_project, name, unit) => ({ name: name === 'Клей плиточный' ? 'Клей' : name, unit }),
      personalRows: [personal({ name: 'Клей плиточный', unit: 'kg' })],
      warehouseRows: [warehouse({ unit: 'кг.' })],
    });
    expect(Object.keys(result)).toEqual([materialLookupText('Клей')]);
    expect(glue(result)).toMatchObject({ quantity: 5, personalAvailable: 2,
      warehouseAvailable: 3, warehouseMaterialId: 31, sourceConflict: false });
  });

  test('one canonical name with incompatible units is blocked', () => {
    const row = glue(availability({ personalRows: [personal({ unit: 'мешок' })],
      warehouseRows: [warehouse({ unit: 'кг' })] }));
    expect(row.sourceConflict).toBe(true);
    expect(row.warehouseAvailable).toBe(0);
    expect(row.warehouseMaterialId ?? null).toBeNull();
  });

  test('two warehouse IDs cannot silently become one selectable stock source', () => {
    const row = glue(availability({ warehouseRows: [warehouse(), warehouse({ id: 32, quantity: 7 })] }));
    expect(row.sourceConflict).toBe(true);
    expect(row.warehouseAvailable).toBe(0);
    expect(row.warehouseMaterialId ?? null).toBeNull();
  });
});

describe('work material source allocation', () => {
  const stock = { quantity: 5, personalAvailable: 2, warehouseAvailable: 3,
    warehouseMaterialId: 31, unit: 'кг', sourceConflict: false, materialAccountingVersion: 2 };

  test('uses personal stock first and copies the factual material without mutating it', () => {
    const item = Object.freeze({ name: 'Клей', unit: 'кг', quantity: 4, normQuantity: 4 });
    const result = allocateWorkMaterialSources(item, Object.freeze({ ...stock }));
    expect(result).not.toBe(item);
    expect(result).toMatchObject({ ...item, personalQuantity: 2, warehouseQuantity: 2,
      warehouseMaterialId: 31, materialAccountingVersion: 2 });
  });

  test('keeps a warehouse shortage visible instead of clipping factual consumption', () => {
    expect(allocateWorkMaterialSources({ name: 'Клей', quantity: 10 }, stock))
      .toMatchObject({ quantity: 10, personalQuantity: 2, warehouseQuantity: 8, warehouseMaterialId: 31 });
  });

  test('warehouse preference allocates the entire requested quantity to warehouse', () => {
    expect(allocateWorkMaterialSources({ name: 'Клей', quantity: 4, sourcePreference: 'warehouse' }, stock))
      .toMatchObject({ quantity: 4, personalQuantity: 0, warehouseQuantity: 4, warehouseMaterialId: 31 });
  });

  test('personal preference keeps the entire quantity personal even when insufficient', () => {
    const result = allocateWorkMaterialSources({ name: 'Клей', quantity: 4, sourcePreference: 'personal' }, stock);
    expect(result).toMatchObject({ quantity: 4, personalQuantity: 4, warehouseQuantity: 0 });
    expect(result.warehouseMaterialId ?? null).toBeNull();
  });

  test('source subtraction uses six decimal places rather than binary floating artifacts', () => {
    expect(allocateWorkMaterialSources({ name: 'Клей', quantity: 0.3 },
      { ...stock, personalAvailable: 0.1, warehouseAvailable: 0.2 }))
      .toMatchObject({ quantity: 0.3, personalQuantity: 0.1, warehouseQuantity: 0.2 });
  });

  test('missing availability exposes shortage and cannot preserve an unverified old stock ID', () => {
    const result = allocateWorkMaterialSources({ name: 'Клей', quantity: 4, warehouseMaterialId: 999 }, undefined);
    expect(result).toMatchObject({ quantity: 4, personalQuantity: 0, warehouseQuantity: 4,
      materialAccountingVersion: 2 });
    expect(result.warehouseMaterialId ?? null).toBeNull();
  });

  test('conflicted availability never supplies a warehouse identifier', () => {
    const result = allocateWorkMaterialSources({ name: 'Клей', quantity: 4 },
      { ...stock, sourceConflict: true });
    expect(result.warehouseMaterialId ?? null).toBeNull();
    expect(result.personalQuantity + result.warehouseQuantity).toBe(4);
  });
});
