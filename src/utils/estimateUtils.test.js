import {
  buildEstimateMaterialSummary,
  isEstimateMaterialItem,
  isEstimateWorkItem,
  normalizeEstimateWorkingItem,
} from './estimateUtils';

describe('estimateUtils imported item typing', () => {
  test('keeps imported work rows with material-like names in the work estimate', () => {
    const rows = [
      {
        isImported: true,
        type: 'work',
        name: 'Светильник в подвесных потолках',
        unit: 'шт',
        quantity: 915,
        totalWork: 120000,
        totalMaterial: 0,
        lineTotal: 120000,
      },
      {
        isImported: true,
        type: 'work',
        name: 'Грунтование водно-дисперсионной грунтовкой',
        unit: 'м2',
        quantity: 1846,
        totalWork: 45000,
        totalMaterial: 0,
        lineTotal: 45000,
      },
    ];

    rows.forEach(row => {
      const normalized = normalizeEstimateWorkingItem(row, 'Тестовый раздел');
      expect(normalized.itemType).toBe('work');
      expect(isEstimateWorkItem(normalized, 'Тестовый раздел')).toBe(true);
      expect(isEstimateMaterialItem(normalized, 'Тестовый раздел')).toBe(false);
    });
  });

  test('keeps imported resource rows in the material estimate', () => {
    const material = normalizeEstimateWorkingItem({
      isImported: true,
      type: 'material',
      name: 'Грунтовка акриловая НОРТЕКС-ГРУНТ',
      unit: 'кг',
      quantity: 180,
      totalWork: 0,
      totalMaterial: 22000,
      lineTotal: 22000,
    }, 'Тестовый раздел');

    expect(material.itemType).toBe('material');
    expect(isEstimateMaterialItem(material, 'Тестовый раздел')).toBe(true);
  });
});

describe('estimate material summary', () => {
  test('groups repeated positive materials without changing source rows', () => {
    const estimate = {
      id: 25,
      workPackage: 'Электрика',
      sections: [
        {
          name: 'Первый этаж',
          items: [
            {type: 'material', name: 'Краска акриловая', unit: 'кг', quantity: 10, priceMaterial: 100},
            {type: 'work', name: 'Окраска стен', unit: 'м2', quantity: 20, priceWork: 300},
          ],
        },
        {
          name: 'Второй этаж',
          items: [
            {type: 'material', name: 'краска акриловая.', unit: 'кг', quantity: 5, priceMaterial: 100},
            {type: 'material', name: 'Краска акриловая', unit: 'л', quantity: 2, priceMaterial: 120},
            {type: 'material', name: 'Краска акриловая', unit: 'кг', quantity: -1, priceMaterial: 100},
          ],
        },
      ],
    };

    const summary = buildEstimateMaterialSummary(estimate);
    const duplicate = summary.groups.find(group => group.sourceCount === 2);

    expect(summary.duplicateGroups).toBe(1);
    expect(duplicate).toMatchObject({
      name: 'Краска акриловая',
      unit: 'кг',
      quantity: 15,
      materialSum: 1500,
      sourceCount: 2,
    });
    expect(estimate.sections[0].items[0].quantity).toBe(10);
    expect(summary.totalSourceRows).toBe(3);
  });
});
