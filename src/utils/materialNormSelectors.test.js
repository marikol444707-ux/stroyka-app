import { buildEstimateWorkNormRequirementRows, buildPersonalMaterialRowsForProject } from './materialNormSelectors';
import { materialLookupText } from './materialMatchUtils';

describe('buildEstimateWorkNormRequirementRows traceability', () => {
  test('keeps estimate, work, rule and formula for every norm calculation', () => {
    const rows = buildEstimateWorkNormRequirementRows({
      project: { companyId: 1, projectId: 1, projectName: 'Тестовый объект' },
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

describe('personal material balance identity', () => {
  const base = {
    projectName: 'Объект', personName: 'Иван Петров', personId: 41,
    canonicalMaterialMeta: (_project, name, unit) => ({name, unit}),
    parseJournalMaterials: value => value || [],
    materialNameKey: materialLookupText,
    materialTransfers: [{projectName: 'Объект', toPerson: 'Иван Петров', toUserId: 41,
      materialName: 'Кабель', unit: 'м', quantity: 10, signed: true}],
  };
  const row = overrides => buildPersonalMaterialRowsForProject({...base, ...overrides})[0];

  test('a journal user ID excludes another worker with the same name', () => {
    expect(row({workJournal: [{project: 'Объект', masterId: 42, masterName: 'Иван Петров',
      materialsUsed: [{name: 'Кабель', unit: 'м', quantity: 4}]}]})).toMatchObject({quantity: 10, used: 0});
  });

  test.each([
    {sourceType: 'material_return_user', sourceId: 42},
    {source_type: 'material_return_user', source_id: 42},
    {sourceType: 'material_return_user'},
  ])('an identified return cannot fall back to a matching name: %p', source => {
    expect(row({history: [{project: 'Объект', type: 'возврат от мастера', issuedBy: 'Иван Петров',
      material: 'Кабель', unit: 'м', quantity: 3, ...source}]})).toMatchObject({quantity: 10, returned: 0});
  });

  test('renamed workers retain consumption and returns linked to their user ID', () => {
    expect(row({
      workJournal: [{project: 'Объект', master_id: '41', master_name: 'Прежняя фамилия',
        materials_used: [{name: 'Кабель', unit: 'м', quantity: 2}]}],
      history: [{project: 'Объект', type: 'возврат от мастера', issued_by: 'Прежняя фамилия',
        source_type: 'material_return_user', source_id: '41', material: 'Кабель', unit: 'м', quantity: 3}],
    })).toMatchObject({quantity: 5, used: 2, returned: 3});
  });

  test('historical name-only consumption and returns remain visible', () => {
    expect(row({
      workJournal: [{project: 'Объект', masterName: 'Иван Петров', materialsUsed: [{name: 'Кабель', unit: 'м', quantity: 2}]}],
      history: [{project: 'Объект', type: 'возврат от мастера', issuedBy: 'Иван Петров', material: 'Кабель', unit: 'м', quantity: 3}],
    })).toMatchObject({quantity: 5, used: 2, returned: 3});
  });

  test.each(['Отклонено', 'Аннулировано'])(
    'v2 work with status %s still consumes only its personal source', status => {
      expect(row({workJournal: [{
        project: 'Объект', masterId: 41, masterName: 'Иван Петров',
        status, materialAccountingVersion: 2,
        materialsUsed: [{name: 'Кабель', unit: 'м', quantity: 7,
          personalQuantity: 2, warehouseQuantity: 5, warehouseMaterialId: 31}],
      }]})).toMatchObject({quantity: 8, used: 2});
    },
  );

  test.each(['Отклонено', 'Аннулировано'])(
    'legacy work with status %s contributes no personal consumption', status => {
      expect(row({workJournal: [{
        project: 'Объект', masterId: 41, masterName: 'Иван Петров', status,
        materialsUsed: [{name: 'Кабель', unit: 'м', quantity: 7}],
      }]})).toMatchObject({quantity: 10, used: 0});
    },
  );

  test('v2 database field names preserve personal consumption after annulment', () => {
    expect(row({workJournal: [{
      project: 'Объект', master_id: 41, master_name: 'Иван Петров',
      status: 'Аннулировано', material_accounting_version: 2,
      materials_used: [{name: 'Кабель', unit: 'м', quantity: 7,
        personalQuantity: 2, warehouseQuantity: 5, warehouseMaterialId: 31}],
    }]})).toMatchObject({quantity: 8, used: 2});
  });
});
