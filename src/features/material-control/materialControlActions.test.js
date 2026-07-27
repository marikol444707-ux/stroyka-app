import {
  buildMaterialControlSupplyItem,
  materialControlRowCanCreateSupply,
} from './materialControlActions';

describe('materialControlRowCanCreateSupply', () => {
  const validRow = {
    name: 'Смесь штукатурная',
    unit: 'кг',
    toBuy: 10,
    invalidPlanCount: 0,
    reviewRequired: false,
    procurementEligible: true,
    planningSource: 'estimate',
    workPackage: 'Отделка',
    planDetails: [{
      sourceType: 'estimate_material',
      includedInProcurement: true,
      estimateId: 14,
      estimateName: 'Общестрой',
      packageName: 'Отделка',
      sectionIndex: 2,
      itemIndex: 7,
      sectionName: 'Штукатурные работы',
      materialName: 'Смесь штукатурная',
      normalizedQty: 25,
      normalizedUnit: 'кг',
    }],
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

  test.each([
    ['estimate id', {estimateId: null}],
    ['section index', {sectionIndex: null}],
    ['item index', {itemIndex: null}],
  ])('blocks a row without source %s', (_label, detailPatch) => {
    const row = {
      ...validRow,
      planDetails: [{...validRow.planDetails[0], ...detailPatch}],
    };
    expect(materialControlRowCanCreateSupply(row)).toBe(false);
  });

  test('builds a versioned item lineage from exact estimate rows', () => {
    expect(buildMaterialControlSupplyItem('Школа 1', validRow, 10)).toEqual({
      materialName: 'Смесь штукатурная',
      quantity: 10,
      unit: 'кг',
      workPackage: 'Отделка',
      sourceType: 'estimate_material_control',
      estimateLineage: {
        version: 1,
        projectName: 'Школа 1',
        workPackage: 'Отделка',
        sources: [{
          estimateId: 14,
          estimateName: 'Общестрой',
          sectionIndex: 2,
          itemIndex: 7,
          sectionName: 'Штукатурные работы',
          materialName: 'Смесь штукатурная',
          unit: 'кг',
          quantity: 25,
        }],
      },
    });
  });
});
