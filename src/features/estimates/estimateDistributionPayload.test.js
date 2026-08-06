import {
  buildEstimateDistributionAssignments,
  getDistributableWorkRows,
} from './estimateDistributionPayload';

test('distribution payload carries exact section and item coordinates with canonical key', () => {
  const estimate = {
    id: 9,
    workPackage: 'Отделка',
    sections: [{
      name: 'Стены',
      items: [{
        name: 'Штукатурка',
        unit: 'м2',
        quantity: 12,
        priceWork: 1000,
        estimateItemKey: 'work-1',
      }],
    }],
  };
  const rows = getDistributableWorkRows(estimate);

  const assignments = buildEstimateDistributionAssignments(
    rows,
    {[rows[0].key]: 'Бригада 1'},
    [{name: 'Бригада 1', contractorId: 41, pricelistId: 3}],
  );

  expect(assignments).toEqual([expect.objectContaining({
    sectionIndex: 0,
    itemIndex: 0,
    estimateItemKey: 'work-1',
    brigadeName: 'Бригада 1',
    contractorId: 41,
    pricelistId: 3,
  })]);
});

test('generated canonical key uses the same exact estimate coordinate', () => {
  const rows = getDistributableWorkRows({
    id: 12,
    sections: [{name: 'A', items: [{name: 'Материал', type: 'material'}]}, {
      name: 'B',
      items: [{name: 'Работа', quantity: 1, priceWork: 10}],
    }],
  });

  expect(rows).toHaveLength(1);
  expect(rows[0]).toEqual(expect.objectContaining({
    sectionIndex: 1,
    itemIndex: 0,
    estimateItemKey: '12:1:0',
  }));
});
