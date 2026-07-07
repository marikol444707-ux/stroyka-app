import {
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
