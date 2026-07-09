import { materialControlRowCanCreateSupply } from './materialControlActions';

describe('materialControlRowCanCreateSupply', () => {
  const validRow = {
    name: 'Смесь штукатурная',
    toBuy: 10,
    invalidPlanCount: 0,
    reviewRequired: false,
    procurementEligible: true,
  };

  test('allows only a confirmed positive estimate shortage', () => {
    expect(materialControlRowCanCreateSupply(validRow)).toBe(true);
  });

  test.each([
    ['review state', {...validRow, reviewRequired: true}],
    ['non-procurement hint', {...validRow, procurementEligible: false}],
    ['invalid estimate row', {...validRow, invalidPlanCount: 1}],
    ['no shortage', {...validRow, toBuy: 0}],
  ])('blocks %s', (_label, row) => {
    expect(materialControlRowCanCreateSupply(row)).toBe(false);
  });
});
