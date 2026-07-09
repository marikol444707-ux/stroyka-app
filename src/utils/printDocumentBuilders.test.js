import { buildMaterialRequirementDocContent } from './printDocumentBuilders';

const reconciliationRow = (overrides = {}) => ({
  name: 'Смесь штукатурная',
  unit: 'кг',
  planQty: 1000,
  normPlanQty: 0,
  controlPlanQty: 1000,
  requested: 0,
  inTransit: 0,
  invoiceReceived: 0,
  supplyReceived: 0,
  movedNet: 0,
  supplied: 0,
  issued: 0,
  used: 0,
  masterBalance: 0,
  stock: 0,
  expectedStock: 0,
  stockDiff: 0,
  toBuy: 0,
  shortage: 1000,
  coveredWithPipeline: 0,
  usedWithoutIssue: 0,
  usedOverControlQty: 0,
  normOverEstimateQty: 0,
  over: 0,
  planSum: 12000,
  workRefs: ['Штукатурка стен'],
  sections: ['Общестрой / Стены'],
  planDetails: [{
    estimateName: 'Локальная смета 1',
    packageName: 'Общестрой',
    sectionName: 'Стены',
    workName: 'Штукатурка стен',
    materialName: 'Смесь штукатурная',
    sourceQty: 1,
    sourceUnit: '1000 кг',
    normalizedQty: 1000,
    normalizedUnit: 'кг',
    normalizationFactor: 1000,
    conversionApplied: true,
    qty: 1000,
    unit: 'кг',
    sum: 12000,
  }],
  invalidPlanDetails: [],
  reviewRequired: true,
  reviewReasons: ['Конфликт единиц измерения'],
  unitMismatch: true,
  invalidPlanCount: 0,
  normSourceCount: 0,
  ...overrides,
});

describe('buildMaterialRequirementDocContent', () => {
  test('prints estimate conversion, review reason and norm formula trace', () => {
    const html = buildMaterialRequirementDocContent({
      projectName: 'Тестовый объект',
      activeEstimates: [{id: 1}],
      rows: [reconciliationRow()],
      normRows: [{
        name: 'Грунтовка',
        unit: 'кг',
        planQty: 20,
        normSources: ['0.2 кг/м2'],
        works: [{
          estimateName: 'Локальная смета 1',
          packageName: 'Общестрой',
          section: 'Стены',
          name: 'Грунтование стен',
          quantity: 100,
          unit: 'м2',
          requiredQty: 20,
          requiredUnit: 'кг',
          ruleId: 'primer-walls',
          ruleScope: 'base',
          formula: {
            workQty: 100,
            workUnit: 'м2',
            qtyPerUnit: 0.2,
            materialUnit: 'кг',
            requiredQty: 20,
            requiredUnit: 'кг',
          },
        }],
      }],
      normCtrl: {overRows: [], withoutNormRows: []},
    });

    expect(html).toContain('Расшифровка строк сметы');
    expect(html).toContain('1 1000 кг');
    expect(html).toMatch(/1\s*000 кг \(преобразовано x 1\s*000\)/);
    expect(html).toContain('проверить: Конфликт единиц измерения');
    expect(html).toContain('Расшифровка нормативного расчёта');
    expect(html).toContain('100 м2 x 0,2 кг/м2 = 20 кг');
    expect(html).toContain('Нормативная подсказка, не закупать автоматически');
  });
});
