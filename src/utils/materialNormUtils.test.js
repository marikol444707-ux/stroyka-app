import {
  WORK_MATERIAL_NORM_RULES,
  buildMaterialNormRulesForCalculation,
  workNormRulesForCalculation,
} from './materialNormUtils';

const matchingRuleIds = (workName, workUnit = 'м2', options = {}) => workNormRulesForCalculation({
  workName,
  sectionName: options.sectionName || '',
  projectName: options.projectName || 'Тестовый объект',
  estimateId: options.estimateId || 10,
  materialNorms: options.materialNorms || [],
  materialNormOverrides: options.materialNormOverrides || [],
  baseRules: options.baseRules || WORK_MATERIAL_NORM_RULES,
}).filter(rule => rule.workUnit === workUnit).map(rule => rule.ruleKey);

describe('material norm work matching safety', () => {
  test('does not match brick masonry rule to air-duct installation', () => {
    expect(matchingRuleIds(
      'Прокладка воздуховодов из листовой оцинкованной стали',
      'м2',
    )).not.toContain('brick_masonry');
    expect(matchingRuleIds('Кладка стен из кирпича', 'м2')).toContain('brick_masonry');
  });

  test('does not calculate plaster mix for painting over plaster', () => {
    expect(matchingRuleIds(
      'Окраска водно-дисперсионными составами по штукатурке стен',
      'м2',
    )).not.toContain('plaster_mix');
    expect(matchingRuleIds(
      'Окраска водно-дисперсионными составами по штукатурке стен',
      'м2',
    )).not.toContain('plaster_mesh');
    expect(matchingRuleIds(
      'Штукатурка поверхностей внутри здания цементным раствором',
      'м2',
    )).toContain('plaster_mix');
    expect(matchingRuleIds('Высококачественная штукатурка наружных стен', 'м2')).toContain('plaster_mix');
    expect(matchingRuleIds('Окраска оштукатуренных поверхностей стен', 'м2')).not.toContain('plaster_mix');
  });

  test('does not treat screed thickness adjustment as an independent base work', () => {
    expect(matchingRuleIds(
      'Устройство стяжки: на каждые 5 мм изменения толщины добавлять или исключать',
      'м2',
    )).not.toContain('screed_mix');
    expect(matchingRuleIds('Устройство цементной стяжки пола', 'м2')).toContain('screed_mix');
  });

  test('does not confuse pipelines with cable conductors', () => {
    expect(matchingRuleIds(
      'Гидравлическое испытание трубопроводов систем отопления',
      'м',
    )).not.toContain('cable_fasteners');
    expect(matchingRuleIds('Прокладка кабеля по стене', 'м')).toContain('cable_fasteners');
  });

  test('does not add thermal-insulation fasteners to vapor barrier work', () => {
    expect(matchingRuleIds(
      'Устройство пароизоляции из полиэтиленовой пленки',
      'м2',
    )).not.toContain('thermal_insulation_fasteners');
    expect(matchingRuleIds(
      'Теплоизоляция стен минераловатными плитами',
      'м2',
    )).toContain('thermal_insulation_fasteners');
  });

  test('requires the full AI work signature instead of one generic word', () => {
    const aiRule = {
      id: 501,
      ruleKey: 'ai_facade_screws',
      name: 'Шурупы для фасадной облицовки',
      work: ['наружная', 'облицовка', 'поверхности', 'стен', 'горизонтальном'],
      blockWork: ['демонтаж', 'разбор'],
      material: ['шуруп'],
      workUnit: 'м2',
      materialUnit: 'шт',
      qtyPerUnit: 15,
      active: true,
    };

    expect(matchingRuleIds(
      'Окраска поверхностей стен',
      'м2',
      { materialNorms: [aiRule], baseRules: [] },
    )).not.toContain('ai_facade_screws');
    expect(matchingRuleIds(
      'Наружная облицовка поверхности стен в горизонтальном исполнении',
      'м2',
      { materialNorms: [aiRule], baseRules: [] },
    )).toContain('ai_facade_screws');
  });

  test('scoped override matches its source work and replaces linked base norm', () => {
    const baseRule = {
      id: 153,
      ruleKey: 'ai_beacon_profile',
      name: 'Маячный профиль',
      work: ['прибивка', 'маячных', 'реек'],
      blockWork: [],
      material: ['маяк'],
      workUnit: 'м2',
      materialUnit: 'м',
      qtyPerUnit: 1.2,
      active: true,
    };
    const override = {
      id: 2,
      baseNormId: 153,
      projectName: 'Тестовый объект',
      estimateId: 10,
      workName: 'Прибивка по стенам маячных реек',
      materialName: 'Маячный профиль',
      work: ['маяк', 'маяч'],
      blockWork: [],
      material: ['маяк'],
      workUnit: 'м2',
      materialUnit: 'м',
      qtyPerUnit: 0.85,
      active: true,
    };

    const rules = buildMaterialNormRulesForCalculation({
      projectName: 'Тестовый объект',
      estimateId: 10,
      materialNorms: [baseRule],
      materialNormOverrides: [override],
      baseRules: [],
    });
    expect(rules.map(rule => rule.ruleKey)).toEqual(['override_2']);

    expect(matchingRuleIds('Прибивка по стенам маячных реек', 'м2', {
      materialNorms: [baseRule],
      materialNormOverrides: [override],
      baseRules: [],
    })).toEqual(['override_2']);
    expect(matchingRuleIds('Установка штукатурных маяков', 'м2', {
      materialNorms: [baseRule],
      materialNormOverrides: [override],
      baseRules: [],
    })).toEqual([]);
  });
});
