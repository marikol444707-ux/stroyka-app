import { buildPublicProjectComparisonItem } from './publicProjectComparison';

test('builds a comparable project summary from public project fields', () => {
  const item = buildPublicProjectComparisonItem({
    project: {
      code: 'H1-02',
      title: 'Дом 116 м2 с кухней-гостиной',
      area: '116 м2',
      floors: '1 этаж',
      calcPatch: { type: 'house', rooms: 4, bedrooms: 3, wallType: 'brick' },
    },
    estimate: { rangeLabel: '10-12 млн ₽' },
  });

  expect(item.code).toBe('H1-02');
  expect(item.facts).toEqual([
    ['Площадь', '116 м2'],
    ['Этажность / формат', '1 этаж'],
    ['Комнат / зон', '4'],
    ['Спален', '3'],
    ['Материал стен', 'Кирпич'],
    ['Ориентир', '10-12 млн ₽'],
  ]);
});

test('omits house-only facts for a repair project', () => {
  const item = buildPublicProjectComparisonItem({
    project: {
      code: 'APT-01',
      title: 'Ремонт квартиры 45 м2',
      area: '45 м2',
      floors: 'квартира',
      calcPatch: { type: 'repair', rooms: 2 },
    },
    estimate: { rangeLabel: 'после замера' },
  });

  expect(item.facts).not.toEqual(expect.arrayContaining([
    expect.arrayContaining(['Материал стен']),
  ]));
});
