import { buildEstimateWorkNormRequirementRows } from './materialNormSelectors';
import { materialLookupText } from './materialMatchUtils';

describe('buildEstimateWorkNormRequirementRows traceability', () => {
  test('keeps estimate, work, rule and formula for every norm calculation', () => {
    const rows = buildEstimateWorkNormRequirementRows({
      projectName: 'Тестовый объект',
      projects: [{ id: 1, name: 'Тестовый объект' }],
      activeEstimatesForProject: () => [{
        id: 10,
        name: 'Активная смета',
        workPackage: 'Общестрой',
        sections: [{
          name: 'Стены',
          items: [{
            id: 100,
            itemType: 'work',
            name: 'Штукатурка наружных стен',
            quantity: 10,
            unit: 'м2',
          }],
        }],
      }],
      normRequirementsForWork: () => [{
        ruleId: 'plaster_mix',
        scope: 'base',
        name: 'Штукатурная смесь',
        quantity: 85,
        unit: 'кг',
        normSource: 'штукатурная смесь 8.5 кг/м2 на 10 мм',
        rule: {
          ruleKey: 'plaster_mix',
          qtyPerUnit: 8.5,
          workUnit: 'м2',
          materialUnit: 'кг',
          thicknessBaseMm: 10,
          defaultThicknessMm: 10,
        },
      }],
      materialNameKey: materialLookupText,
    });

    expect(rows).toHaveLength(1);
    expect(rows[0]).toMatchObject({
      sourceType: 'norm_hint',
      procurementEligible: false,
      planQty: 85,
    });
    expect(rows[0].works).toHaveLength(1);
    expect(rows[0].works[0]).toMatchObject({
      estimateId: 10,
      estimateName: 'Активная смета',
      itemId: 100,
      name: 'Штукатурка наружных стен',
      section: 'Стены',
      packageName: 'Общестрой',
      requiredQty: 85,
      requiredUnit: 'кг',
      ruleId: 'plaster_mix',
      ruleScope: 'base',
      formula: {
        workQty: 10,
        workUnit: 'м2',
        qtyPerUnit: 8.5,
        materialUnit: 'кг',
        thicknessBaseMm: 10,
        thicknessMm: 10,
        requiredQty: 85,
        requiredUnit: 'кг',
      },
    });
  });
});
