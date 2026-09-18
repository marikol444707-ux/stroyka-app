import {
  buildEstimateDiffDocContent,
  buildEstimateReconciliationDocContent,
  buildMaterialRequirementDocContent,
  buildProjectEstimateDiffSummaryDocContent,
  buildMaterialInspectionDocContent,
  buildCableJournalDocContent,
  buildJPRDocContent,
  buildExecPackageDocContent,
} from './printDocumentBuilders';

describe('quality journal export ownership', () => {
  const project = { id: 11, companyId: 2, name: 'Школа', client: 'Наш заказчик' };
  const other = { id: 12, companyId: 3, name: 'Школа', client: 'Чужой заказчик' };
  const rows = [
    { id: 1, companyId: 2, projectId: 11, projectName: 'Старое имя', materialName: 'OWN', cableBrand: 'OWN' },
    { id: 2, companyId: 3, projectId: 12, projectName: 'Школа', materialName: 'FOREIGN', cableBrand: 'FOREIGN' },
    { id: 3, companyId: 2, projectName: 'Школа', materialName: 'PARTIAL', cableBrand: 'PARTIAL' },
    { id: 4, projectName: 'Школа', materialName: 'LEGACY', cableBrand: 'LEGACY' },
  ];
  test.each([buildMaterialInspectionDocContent, buildCableJournalDocContent])('builder scopes explicit project and preserves identity in header', builder => {
    const html = builder(rows, project, '', '', { projects: [other, project] });
    expect(html).toContain('OWN'); expect(html).toContain('LEGACY');
    expect(html).not.toContain('FOREIGN'); expect(html).not.toContain('PARTIAL');
    expect(html).toContain('Наш заказчик'); expect(html).not.toContain('Чужой заказчик');
    expect(html).not.toContain('[object Object]');
  });
  test.each([buildMaterialInspectionDocContent, buildCableJournalDocContent])('legacy string resolves only unique project; ambiguous export refuses', builder => {
    expect(builder(rows, 'Школа', '', '', { projects: [project] })).toContain('OWN');
    expect(() => builder(rows, 'Школа', '', '', { projects: [project, other] })).toThrow(/неоднознач/i);
    const legacyHtml = builder(rows, 'Школа', '', '');
    expect(legacyHtml).toContain('LEGACY'); expect(legacyHtml).not.toContain('OWN');
    expect(legacyHtml).not.toContain('FOREIGN');
  });
  test('JPR scopes journal sections and rejects ambiguous project names', () => {
    const context = { projects: [other, project], materialInspections: rows, cableJournal: rows };
    const html = buildJPRDocContent(project, context);
    expect(html).toContain('OWN'); expect(html).toContain('LEGACY');
    expect(html).not.toContain('FOREIGN'); expect(html).not.toContain('PARTIAL');
    expect(html).toContain('Журнал кабельной продукции</td><td>2</td>');
    expect(() => buildJPRDocContent('Школа', context)).toThrow(/неоднознач/i);
  });
  test('JPR includes every loaded incoming inspection, including rows after thirty', () => {
    const inspections = Array.from({length: 35}, (_, i) => ({...rows[0], id: i + 1, materialName: `Inspection-${i + 1}-end`}));
    const html = buildJPRDocContent(project, {projects: [project], materialInspections: inspections});
    expect(html).toContain('Inspection-35-end');
  });
  test('executive package counts only selected journal ownership plus legacy', () => {
    const html = buildExecPackageDocContent(project, { materialInspections: rows, cableJournal: rows });
    for (const title of ['Журнал входного контроля материалов', 'Журнал кабельной продукции']) {
      const section = html.slice(html.indexOf(title)).split('</tr>')[0];
      expect(section).toMatch(/<td[^>]*>2<\/td>/);
    }
  });
});

const reconciliationRow = (overrides = {}) => ({
  name: 'Смесь штукатурная',
  unit: 'кг',
  planQty: 1000,
  normPlanQty: 0,
  controlPlanQty: 1000,
  requested: 0,
  inTransit: 0,
  invoiceReceived: 0,
  supplyReceived: 0,
  movedNet: 0,
  supplied: 0,
  issued: 0,
  used: 0,
  masterBalance: 0,
  stock: 0,
  expectedStock: 0,
  stockDiff: 0,
  toBuy: 0,
  shortage: 1000,
  coveredWithPipeline: 0,
  usedWithoutIssue: 0,
  usedOverControlQty: 0,
  normOverEstimateQty: 0,
  over: 0,
  planSum: 12000,
  workRefs: ['Штукатурка стен'],
  sections: ['Общестрой / Стены'],
  planDetails: [{
    estimateName: 'Локальная смета 1',
    packageName: 'Общестрой',
    sectionName: 'Стены',
    workName: 'Штукатурка стен',
    materialName: 'Смесь штукатурная',
    sourceQty: 1,
    sourceUnit: '1000 кг',
    normalizedQty: 1000,
    normalizedUnit: 'кг',
    normalizationFactor: 1000,
    conversionApplied: true,
    qty: 1000,
    unit: 'кг',
    sum: 12000,
  }],
  invalidPlanDetails: [],
  reviewRequired: true,
  reviewReasons: ['Конфликт единиц измерения'],
  unitMismatch: true,
  invalidPlanCount: 0,
  normSourceCount: 0,
  ...overrides,
});

describe('buildMaterialRequirementDocContent', () => {
  test('prints estimate conversion, review reason and norm formula trace', () => {
    const html = buildMaterialRequirementDocContent({
      projectName: 'Тестовый объект',
      activeEstimates: [{id: 1}],
      rows: [reconciliationRow()],
      normRows: [{
        name: 'Грунтовка',
        unit: 'кг',
        planQty: 20,
        normSources: ['0.2 кг/м2'],
        works: [{
          estimateName: 'Локальная смета 1',
          packageName: 'Общестрой',
          section: 'Стены',
          name: 'Грунтование стен',
          quantity: 100,
          unit: 'м2',
          requiredQty: 20,
          requiredUnit: 'кг',
          ruleId: 'primer-walls',
          ruleScope: 'base',
          formula: {
            workQty: 100,
            workUnit: 'м2',
            qtyPerUnit: 0.2,
            materialUnit: 'кг',
            requiredQty: 20,
            requiredUnit: 'кг',
          },
        }],
      }],
      normCtrl: {overRows: [], withoutNormRows: []},
    });

    expect(html).toContain('Расшифровка строк сметы');
    expect(html).toContain('1 1000 кг');
    expect(html).toMatch(/1\s*000 кг \(преобразовано x 1\s*000\)/);
    expect(html).toContain('проверить: Конфликт единиц измерения');
    expect(html).toContain('Расшифровка нормативного расчёта');
    expect(html).toContain('100 м2 x 0,2 кг/м2 = 20 кг');
    expect(html).toContain('Нормативная подсказка, не закупать автоматически');
  });
});

describe('estimate comparison documents', () => {
  const changed = {
    base: { section: 'Отделка', name: 'Штукатурка', unit: 'м2', qty: 10, unitPrice: 100, sum: 1000 },
    next: { section: 'Отделка', name: 'Штукатурка', unit: 'м2', qty: 12, unitPrice: 100, sum: 1200 },
    impact: 200,
  };

  test('shows plus, minus, reasons and the explained row balance in the comparison statement', () => {
    const html = buildEstimateDiffDocContent({
      diff: {
        baseTotal: 1500,
        nextTotal: 1600,
        impact: 100,
        changed: [changed],
        added: [],
        removed: [{ section: 'Отделка', name: 'Грунтовка', unit: 'л', qty: 1, unitPrice: 100, sum: 100, impact: -100 }],
      },
    });

    expect(html).toContain('Почему изменилась сумма');
    expect(html).toContain('Плюсовые изменения');
    expect(html).toContain('+200 ₽');
    expect(html).toContain('Минусовые изменения');
    expect(html).toContain('-100 ₽');
    expect(html).toContain('Изменился объём');
    expect(html).toContain('Позиция исключена');
    expect(html).toContain('Разница полностью объяснена позициями');
  });

  test('warns when the reconciliation total cannot be explained by its rows', () => {
    const html = buildEstimateReconciliationDocContent({
      baseTotal: 1000,
      nextTotal: 1200,
      impact: 200,
      items: [{
        itemType: 'changed', sectionName: 'Отделка', itemName: 'Штукатурка', unit: 'м2',
        baseQuantity: 10, nextQuantity: 11, baseUnitPrice: 100, nextUnitPrice: 100,
        baseTotal: 1000, nextTotal: 1100, impact: 100, decision: 'Сопоставлено',
      }],
    });

    expect(html).toContain('Почему изменилась сумма');
    expect(html).toContain('Не распределено по позициям');
    expect(html).toContain('+100 ₽');
    expect(html).toContain('Проверьте итоговые строки');
  });

  test('omits zero technical rows but keeps a changed volume with zero financial impact', () => {
    const html = buildEstimateDiffDocContent({
      diff: {
        baseTotal: 1000,
        nextTotal: 1000,
        impact: 0,
        changed: [{
          base: { section: 'Отделка', name: 'Работа с новой ценой', unit: 'м2', qty: 10, unitPrice: 100, sum: 1000 },
          next: { section: 'Отделка', name: 'Работа с новой ценой', unit: 'м2', qty: 20, unitPrice: 50, sum: 1000 },
          impact: 0,
        }],
        added: [{ section: 'Итоги', name: 'Пустая техническая строка', unit: '', qty: 0, unitPrice: 0, sum: 0, impact: 0 }],
        removed: [],
      },
    });

    expect(html).toContain('Работа с новой ценой');
    expect(html).toContain('Изменились объём и цена');
    expect(html).not.toContain('Пустая техническая строка');
    expect(html).not.toContain('Добавлено в новую смету');
    expect(html).not.toContain('Исключено из новой сметы');
  });

  test('prints one compact project table with the estimate package on each changed row', () => {
    const html = buildProjectEstimateDiffSummaryDocContent({
      projectName: 'Лицей',
      packageCount: 2,
      changedPackageCount: 1,
      baseTotal: 100000,
      nextTotal: 110000,
      impact: 10000,
      rows: [{
        kind: 'changed', workPackage: 'Отделка', section: 'Стены', name: 'Штукатурка', unit: 'м2',
        baseQty: 80, nextQty: 90, baseUnitPrice: 1000, nextUnitPrice: 1000,
        baseSum: 80000, nextSum: 90000, impact: 10000,
      }],
    });

    expect(html).toContain('СВОД ИЗМЕНЕНИЙ СМЕТ ПО ОБЪЕКТУ');
    expect(html).toContain('Отделка');
    expect(html).toContain('Штукатурка');
    expect(html).toContain('80 м2');
    expect(html).toContain('90 м2');
    expect(html).toContain('80 000 ₽');
    expect(html).toContain('90 000 ₽');
  });
});
