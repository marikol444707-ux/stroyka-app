import { estimateQualityRows, estimateUnreadableQuantityText } from './estimateReviewUtils';

const estimateWith = (items) => ({
  id: 1,
  name: 'Тестовая смета',
  projectName: 'Тестовый объект',
  sections: [{ name: 'Отделка', items }],
});

const rowStatuses = (est, itemName) => estimateQualityRows(est)
  .filter(row => row.itemName === itemName)
  .map(row => row.status);

describe('estimateUnreadableQuantityText', () => {
  test('returns the first non-numeric text that toNum would silently zero', () => {
    expect(estimateUnreadableQuantityText('по факту')).toBe('по факту');
    expect(estimateUnreadableQuantityText('1..5')).toBe('1..5');
    expect(estimateUnreadableQuantityText(0, '', 'см. примечание')).toBe('см. примечание');
  });

  test('stays silent for real numbers, real zeros and empty values', () => {
    expect(estimateUnreadableQuantityText('2,5')).toBe('');
    expect(estimateUnreadableQuantityText('0')).toBe('');
    expect(estimateUnreadableQuantityText('0,00')).toBe('');
    expect(estimateUnreadableQuantityText('')).toBe('');
    expect(estimateUnreadableQuantityText(null, undefined, 7)).toBe('');
  });
});

describe('estimateQualityRows quantity checks', () => {
  test('flags unreadable quantity text as critical instead of a generic zero warning', () => {
    const est = estimateWith([
      { name: 'Штукатурка стен', unit: 'м2', quantity: 'по факту', priceWork: 100 },
    ]);
    const rows = estimateQualityRows(est);
    const unreadable = rows.find(row => row.status === 'Нечитаемое количество');
    expect(unreadable).toBeTruthy();
    expect(unreadable.severity).toBe('critical');
    expect(unreadable.message).toContain('по факту');
    expect(rowStatuses(est, 'Штукатурка стен')).not.toContain('Нулевое количество');
  });

  test('flags imported rows whose raw file value was unreadable', () => {
    const est = estimateWith([
      {
        name: 'Кабель ВВГ',
        unit: 'м',
        quantity: 0,
        rawQuantity: 'см. примечание',
        isImported: true,
        priceMaterial: 50,
      },
    ]);
    expect(rowStatuses(est, 'Кабель ВВГ')).toContain('Нечитаемое количество');
  });

  test('keeps the plain zero warning for a genuine zero quantity', () => {
    const est = estimateWith([
      { name: 'Демонтаж плинтуса', unit: 'м', quantity: '0', priceWork: 100 },
    ]);
    const statuses = rowStatuses(est, 'Демонтаж плинтуса');
    expect(statuses).toContain('Нулевое количество');
    expect(statuses).not.toContain('Нечитаемое количество');
  });

  test('keeps the empty-quantity check and accepts normal Russian numbers', () => {
    const est = estimateWith([
      { name: 'Грунтовка стен', unit: 'м2', quantity: '', priceWork: 100 },
      { name: 'Покраска стен', unit: 'м2', quantity: '12,5', priceWork: 100 },
    ]);
    expect(rowStatuses(est, 'Грунтовка стен')).toContain('Нет количества');
    const paintStatuses = rowStatuses(est, 'Покраска стен');
    expect(paintStatuses).not.toContain('Нет количества');
    expect(paintStatuses).not.toContain('Нулевое количество');
    expect(paintStatuses).not.toContain('Нечитаемое количество');
  });
});
