import {
  buildPublicProjectComparisonItem,
  buildPublicProjectComparisonUrl,
  parsePublicProjectComparisonCodes,
  serializePublicProjectComparison,
} from './publicProjectComparison';

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

test('keeps only unique project codes from the opened direction', () => {
  const projects = [{ code: 'H1-01' }, { code: 'H1-02' }, { code: 'H1-03' }];

  expect(parsePublicProjectComparisonCodes('H1-01,H1-02,H1-01,B2-01,H1-03,H1-04', projects))
    .toEqual(['H1-01', 'H1-02', 'H1-03']);
});

test('builds a shareable comparison URL without carrying unrelated query data', () => {
  const url = new URL(buildPublicProjectComparisonUrl({
    origin: 'https://stroyka26.pro',
    pathname: '/',
    selectedCode: 'H1-02',
    comparedCodes: ['H1-01', 'H1-02'],
  }));

  expect(url.searchParams.get('project')).toBe('H1-02');
  expect(url.searchParams.get('compare')).toBe('H1-01,H1-02');
  expect(url.hash).toBe('#projects');
});

test('serializes a compact customer shortlist for the CRM lead', () => {
  const comparison = serializePublicProjectComparison([
    buildPublicProjectComparisonItem({
      project: { code: 'H1-01', title: 'Дом 110 м2', area: '110 м2', floors: '1 этаж' },
      estimate: { rangeLabel: '9-11 млн ₽' },
    }),
    buildPublicProjectComparisonItem({
      project: { code: 'H1-02', title: 'Дом 116 м2', area: '116 м2', floors: '1 этаж' },
      estimate: { rangeLabel: '10-12 млн ₽' },
    }),
  ], 'H1-02', 'https://stroyka26.pro/?project=H1-02&compare=H1-01%2CH1-02#projects');

  expect(comparison).toEqual({
    status: 'customer_shortlist',
    selectedCode: 'H1-02',
    comparisonUrl: 'https://stroyka26.pro/?project=H1-02&compare=H1-01%2CH1-02#projects',
    items: [
      { code: 'H1-01', title: 'Дом 110 м2', area: '110 м2', floors: '1 этаж', estimateRange: '9-11 млн ₽' },
      { code: 'H1-02', title: 'Дом 116 м2', area: '116 м2', floors: '1 этаж', estimateRange: '10-12 млн ₽' },
    ],
  });
});
