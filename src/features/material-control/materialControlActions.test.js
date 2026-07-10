import { materialControlRowCanCreateSupply } from './materialControlActions';

describe('materialControlRowCanCreateSupply', () => {
  const validRow = {
    name: 'Смесь штукатурная',
    toBuy: 10,
    invalidPlanCount: 0,
    reviewRequired: false,
    procurementEligible: true,
    planningSource: 'estimate',
    planDetails: [{ sourceType: 'estimate_material', includedInProcurement: true }],
  };

  test('allows only a confirmed positive estimate shortage', () => {
    expect(materialControlRowCanCreateSupply(validRow)).toBe(true);
  });

  test.each([
    ['review state', {...validRow, reviewRequired: true}],
    ['non-procurement hint', {...validRow, procurementEligible: false}],
    ['invalid estimate row', {...validRow, invalidPlanCount: 1}],
    ['no shortage', {...validRow, toBuy: 0}],
    ['work-derived row', {...validRow, planDetails: [{sourceType: 'estimate_work'}]}],
    ['norm-only row', {...validRow, planningSource: 'norm_hint'}],
    ['row without estimate trace', {...validRow, planDetails: []}],
  ])('blocks %s', (_label, row) => {
    expect(materialControlRowCanCreateSupply(row)).toBe(false);
  });
});
