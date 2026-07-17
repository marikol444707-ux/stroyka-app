import {
  buildAllProjectsMaterialProjectionReview,
  buildLegacyMaterialProjection,
  buildMaterialProjectionDryRun,
  buildSupplyRequestProjectionReview,
} from './materialProjectionDryRunUtils';

const row = (name, planQty, overrides = {}) => ({
  name,
  materialKey: name.toLowerCase(),
  unit: 'шт',
  workPackage: 'Электрика',
  planQty,
  ...overrides,
});

const projectionRequest = overrides => ({
  notes: 'Создано из контроля материалов',
  ...overrides,
});

describe('buildMaterialProjectionDryRun', () => {
  test('reconstructs unsafe legacy family aggregation from corrected source rows', () => {
    const correctedRows = [
      row('Дюбель распорный 8х60', 100, {
        planDetails: [{estimateId: 10, packageName: 'Электрика', sectionName: 'Крепёж', materialName: 'Дюбель распорный 8х60', qty: 100, unit: 'шт'}],
      }),
      row('Шуруп самонарезающий 3,5х35', 200, {
        planDetails: [{estimateId: 10, packageName: 'Электрика', sectionName: 'Крепёж', materialName: 'Шуруп самонарезающий 3,5х35', qty: 200, unit: 'шт'}],
      }),
    ];

    const legacyRows = buildLegacyMaterialProjection(correctedRows);

    expect(legacyRows).toHaveLength(1);
    expect(legacyRows[0]).toMatchObject({planQty: 300, unit: 'шт', workPackage: 'Электрика'});
    expect(legacyRows[0].planDetails).toHaveLength(2);
  });

  test('compares quantities without mutating either projection', () => {
    const legacyRows = [row('Кабель ВВГ 3х1,5', 100)];
    const correctedRows = [row('Кабель ВВГ 3х1,5', 80)];
    const legacySnapshot = JSON.stringify(legacyRows);
    const correctedSnapshot = JSON.stringify(correctedRows);

    const report = buildMaterialProjectionDryRun([{
      projectId: 7,
      projectName: 'Лицей',
      legacyRows,
      correctedRows,
    }]);

    expect(report).toMatchObject({
      ok: true,
      dryRun: true,
      writesAttempted: 0,
      summary: {
        projects: 1,
        legacyRows: 1,
        correctedRows: 1,
        unchanged: 0,
        quantityChanged: 1,
        legacyOnly: 0,
        correctedOnly: 0,
        splitRows: 0,
      },
    });
    expect(report.projects[0].changes[0]).toMatchObject({
      status: 'quantity_changed',
      legacyQty: 100,
      correctedQty: 80,
      deltaQty: -20,
    });
    expect(JSON.stringify(legacyRows)).toBe(legacySnapshot);
    expect(JSON.stringify(correctedRows)).toBe(correctedSnapshot);
  });

  test('reports rows that exist on only one side', () => {
    const report = buildMaterialProjectionDryRun([{
      projectName: 'Школа',
      legacyRows: [row('Старый материал', 5)],
      correctedRows: [row('Новый материал', 7)],
    }]);

    expect(report.summary).toMatchObject({legacyOnly: 1, correctedOnly: 1});
    expect(report.projects[0].changes.map(change => change.status)).toEqual([
      'corrected_only',
      'legacy_only',
    ]);
    expect(report.projects[0].changes).toEqual([
      expect.objectContaining({status: 'corrected_only', correctedQty: 7}),
      expect.objectContaining({status: 'legacy_only', legacyQty: 5}),
    ]);
  });

  test('detects when one legacy aggregate splits into corrected material identities', () => {
    const sourceA = {estimateId: 10, packageName: 'Электрика', sectionName: 'Кабели', materialName: 'Кабель ВВГ 3х1,5'};
    const sourceB = {estimateId: 10, packageName: 'Электрика', sectionName: 'Кабели', materialName: 'Кабель ВВГ 3х2,5'};
    const report = buildMaterialProjectionDryRun([{
      projectName: 'Больница',
      legacyRows: [row('Кабель ВВГ', 300, {planDetails: [sourceA, sourceB]})],
      correctedRows: [
        row('Кабель ВВГ 3х1,5', 100, {planDetails: [sourceA]}),
        row('Кабель ВВГ 3х2,5', 200, {planDetails: [sourceB]}),
      ],
    }]);

    expect(report.summary).toMatchObject({
      splitRows: 1,
      legacyOnly: 0,
      correctedOnly: 0,
    });
    expect(report.projects[0].changes).toEqual([
      expect.objectContaining({
        status: 'split',
        legacyName: 'Кабель ВВГ',
        correctedNames: ['Кабель ВВГ 3х1,5', 'Кабель ВВГ 3х2,5'],
      }),
    ]);
  });

  test('reviews active requests created from a split legacy aggregate without changing requests', () => {
    const sourceA = {estimateId: 10, packageName: 'Электрика', sectionName: 'Крепёж', materialName: 'Дюбель распорный 8х60', qty: 100, unit: 'шт'};
    const sourceB = {estimateId: 10, packageName: 'Электрика', sectionName: 'Крепёж', materialName: 'Шуруп самонарезающий 3,5х35', qty: 200, unit: 'шт'};
    const correctedRows = [
      row('Дюбель распорный 8х60', 100, {planDetails: [sourceA]}),
      row('Шуруп самонарезающий 3,5х35', 200, {planDetails: [sourceB]}),
      row('Кабель ВВГ 3х1,5', 80, {unit: 'м'}),
    ];
    const requests = [
      {id: 21, project: 'Лицей', status: 'Новая', materialName: 'Дюбель распорный 8х60', quantity: 300, unit: 'шт', workPackage: 'Электрика', notes: 'Создано из контроля материалов: строка `Докупить`.'},
      {id: 22, project: 'Лицей', status: 'Утверждена', materialName: 'Кабель ВВГ 3х1,5', quantity: 20, unit: 'м', workPackage: 'Электрика'},
      {id: 23, project: 'Лицей', status: 'Новая', materialName: 'Неизвестный материал', quantity: 5, unit: 'шт', workPackage: 'Электрика'},
      {id: 24, project: 'Лицей', status: 'Доставлено', materialName: 'Старый закрытый материал', quantity: 1, unit: 'шт'},
    ];
    const snapshot = JSON.stringify(requests);

    const review = buildSupplyRequestProjectionReview({
      projectName: 'Лицей',
      requests,
      correctedRows,
      parseSupplyItems: request => [{
        materialName: request.materialName,
        quantity: request.quantity,
        unit: request.unit,
        workPackage: request.workPackage,
      }],
    });

    expect(review).toMatchObject({
      ok: true,
      dryRun: true,
      writesAttempted: 0,
      summary: {
        activeRequests: 3,
        items: 3,
        ready: 1,
        needsReview: 2,
        legacyAggregate: 1,
        unmatched: 1,
      },
    });
    expect(review.needsReview).toEqual([
      expect.objectContaining({requestId: 21, reason: 'legacy_aggregate_split'}),
      expect.objectContaining({requestId: 23, reason: 'material_not_in_projection'}),
    ]);
    expect(JSON.stringify(requests)).toBe(snapshot);
  });

  test('keeps a malformed request without id visible as a separate review problem', () => {
    const review = buildSupplyRequestProjectionReview({
      projectName: 'Лицей',
      requests: [{project: 'Лицей', status: 'Новая', materialName: 'Материал без ID', quantity: 1, unit: 'шт'}],
      correctedRows: [row('Точный материал', 2)],
    });

    expect(review.summary).toMatchObject({activeRequests: 1, needsReview: 1, missingId: 1});
    expect(review.needsReview).toEqual([
      expect.objectContaining({
        requestId: null,
        requestKey: 'missing:0',
        reason: 'missing_request_id',
      }),
    ]);
  });

  test('treats blank request ids as separate missing identities', () => {
    const report = buildAllProjectsMaterialProjectionReview([{
      projectId: 6,
      projectName: 'Лицей',
      correctedRows: [row('Точный материал', 2)],
      requests: [
        projectionRequest({id: '', project: 'Лицей', status: 'Новая', materialName: 'Материал А', quantity: 1, unit: 'шт'}),
        projectionRequest({id: '  ', project: 'Лицей', status: 'Новая', materialName: 'Материал Б', quantity: 1, unit: 'шт'}),
      ],
    }]);

    expect(report.summary).toMatchObject({activeRequests: 2, requestsNeedingReview: 2, requestItemsNeedingReview: 2});
    expect(report.reviewItems.map(item => item.requestKey)).toEqual(['missing:0', 'missing:1']);
    expect(report.reviewItems.every(item => item.reason === 'missing_request_id')).toBe(true);
  });

  test('treats non-positive and malformed request ids as separate missing identities', () => {
    const requests = [0, -1, Number.NaN, 'bad-id'].map((id, index) => projectionRequest({
      id,
      project: 'Лицей',
      status: 'Новая',
      materialName: `Материал ${index + 1}`,
      quantity: 1,
      unit: 'шт',
    }));
    const repeatedMalformed = projectionRequest({id: [82], project: 'Лицей', status: 'Новая', materialName: 'Повтор', quantity: 1, unit: 'шт'});
    requests.push(repeatedMalformed, repeatedMalformed);
    const report = buildAllProjectsMaterialProjectionReview([{
      projectId: 6,
      projectName: 'Лицей',
      correctedRows: [row('Точный материал', 2)],
      requests,
    }]);

    expect(report.summary).toMatchObject({activeRequests: 6, requestsNeedingReview: 6, requestItemsNeedingReview: 6});
    expect(report.reviewItems.map(item => item.requestKey)).toEqual(['missing:0', 'missing:1', 'missing:2', 'missing:3', 'missing:4', 'missing:5']);
  });

  test('summarizes every active project and sorts projects needing review first', () => {
    const sourceA = {estimateId: 10, packageName: 'Электрика', sectionName: 'Крепёж', materialName: 'Дюбель распорный 8х60', qty: 100, unit: 'шт'};
    const sourceB = {estimateId: 10, packageName: 'Электрика', sectionName: 'Крепёж', materialName: 'Шуруп самонарезающий 3,5х35', qty: 200, unit: 'шт'};
    const inputs = [
      {
        projectId: 2,
        projectName: 'Школа',
        correctedRows: [
          row('Дюбель распорный 8х60', 100, {planDetails: [sourceA]}),
          row('Шуруп самонарезающий 3,5х35', 200, {planDetails: [sourceB]}),
        ],
        requests: [{id: 31, project: 'Школа', status: 'Новая', materialName: 'Дюбель распорный 8х60', quantity: 300, unit: 'шт', workPackage: 'Электрика', notes: 'Создано из контроля материалов'}],
      },
      {
        projectId: 1,
        projectName: 'Лицей',
        correctedRows: [row('Кабель ВВГ 3х1,5', 80, {unit: 'м'})],
        requests: [projectionRequest({id: 32, project: 'Лицей', status: 'Утверждена', materialName: 'Кабель ВВГ 3х1,5', quantity: 20, unit: 'м', workPackage: 'Электрика'})],
      },
      {projectId: 3, projectName: 'Пустой объект', correctedRows: [], requests: []},
    ];
    const snapshot = JSON.stringify(inputs);

    const report = buildAllProjectsMaterialProjectionReview(inputs, request => [{
      materialName: request.materialName,
      quantity: request.quantity,
      unit: request.unit,
      workPackage: request.workPackage,
    }]);

    expect(report).toMatchObject({
      ok: true,
      dryRun: true,
      writesAttempted: 0,
      summary: {
        projects: 3,
        projectsNeedingReview: 1,
        activeRequests: 2,
        requestItems: 2,
        requestItemsReady: 1,
        requestsNeedingReview: 1,
        requestItemsNeedingReview: 1,
        splitRows: 1,
      },
    });
    expect(report.projects.map(project => project.projectName)).toEqual(['Школа', 'Лицей', 'Пустой объект']);
    expect(report.projects[0]).toMatchObject({
      projectId: 2,
      projectionChanges: 1,
      requestItemsNeedingReview: 1,
      needsReview: true,
    });
    expect(report.reviewItems).toEqual([
      expect.objectContaining({
        projectId: 2,
        projectName: 'Школа',
        requestId: 31,
        requestStatus: 'Новая',
        materialName: 'Дюбель распорный 8х60',
        reason: 'legacy_aggregate_split',
        candidateNames: ['Дюбель распорный 8х60', 'Шуруп самонарезающий 3,5х35'],
      }),
    ]);
    expect(report.projects[2]).toMatchObject({projectionChanges: 0, requestItemsNeedingReview: 0, needsReview: false});
    expect(JSON.stringify(inputs)).toBe(snapshot);
  });

  test('keeps one request count when several items from the same request need review', () => {
    const report = buildAllProjectsMaterialProjectionReview([{
      projectId: 7,
      projectName: 'Больница',
      correctedRows: [row('Кабель ВВГ 3х1,5', 80, {unit: 'м'})],
      requests: [projectionRequest({id: 41, project: 'Больница', status: 'Новая'})],
    }], () => [
      {materialName: 'Старый кабель А', quantity: 10, unit: 'м', workPackage: 'Электрика'},
      {materialName: 'Старый кабель Б', quantity: 20, unit: 'м', workPackage: 'Электрика'},
    ]);

    expect(report.summary).toMatchObject({
      requestsNeedingReview: 1,
      requestItemsNeedingReview: 2,
    });
    expect(report.reviewItems).toEqual([
      expect.objectContaining({projectId: 7, projectName: 'Больница', requestId: 41, itemIndex: 0}),
      expect.objectContaining({projectId: 7, projectName: 'Больница', requestId: 41, itemIndex: 1}),
    ]);
  });

  test('does not attribute one request to either project when project names are duplicated', () => {
    const sharedRequest = projectionRequest({id: 51, project: 'Одинаковый объект', status: 'Новая', materialName: 'Старый материал', quantity: 4, unit: 'шт'});
    const report = buildAllProjectsMaterialProjectionReview([
      {projectId: 8, projectName: 'Одинаковый объект', correctedRows: [row('Материал А', 2)], requests: [sharedRequest]},
      {projectId: 9, projectName: 'Одинаковый объект', correctedRows: [row('Материал Б', 3)], requests: [sharedRequest]},
    ]);

    expect(report.summary).toMatchObject({
      activeRequests: 1,
      requestItems: 1,
      requestsNeedingReview: 1,
      requestItemsNeedingReview: 1,
    });
    expect(report.reviewItems).toEqual([
      expect.objectContaining({
        projectId: null,
        projectName: 'Одинаковый объект',
        requestId: 51,
        requestKey: 'id:51',
        reason: 'ambiguous_project_identity',
        candidateProjectIds: [8, 9],
      }),
    ]);
    expect(report.projects).toEqual([
      expect.objectContaining({projectId: 8, activeRequests: 0, requestItemsNeedingReview: 0}),
      expect.objectContaining({projectId: 9, activeRequests: 0, requestItemsNeedingReview: 0}),
    ]);
  });

  test('keeps unknown and hidden duplicate project references in review', () => {
    const activeInput = {
      projectId: 10,
      projectName: 'Объект',
      correctedRows: [row('Материал', 2)],
      requests: [
        projectionRequest({id: 61, project: 'Объект', status: 'Новая', materialName: 'Материал', quantity: 1, unit: 'шт'}),
        projectionRequest({id: 62, project: 'Удалённый объект', status: 'Новая', materialName: 'Старый материал', quantity: 1, unit: 'шт'}),
      ],
    };
    const report = buildAllProjectsMaterialProjectionReview(
      [activeInput],
      undefined,
      [{projectId: 10, projectName: 'Объект'}, {projectId: 11, projectName: 'Объект'}],
    );

    expect(report.summary).toMatchObject({activeRequests: 2, requestsNeedingReview: 2, requestItemsNeedingReview: 2});
    expect(report.reviewItems).toEqual(expect.arrayContaining([
      expect.objectContaining({requestId: 61, reason: 'ambiguous_project_identity', candidateProjectIds: [10, 11]}),
      expect.objectContaining({requestId: 62, reason: 'project_not_found', candidateProjectIds: []}),
    ]));
  });

  test('keeps requests visible when there are no active project inputs', () => {
    const report = buildAllProjectsMaterialProjectionReview(
      [],
      undefined,
      [],
      [projectionRequest({id: 71, project: 'Архивный объект', status: 'Новая', materialName: 'Материал', quantity: 1, unit: 'шт'})],
    );

    expect(report.summary).toMatchObject({projects: 0, activeRequests: 1, requestsNeedingReview: 1});
    expect(report.reviewItems).toEqual([
      expect.objectContaining({requestId: 71, reason: 'project_not_found'}),
    ]);
  });

  test('marks a uniquely identified inactive project as unresolved', () => {
    const report = buildAllProjectsMaterialProjectionReview(
      [],
      undefined,
      [{projectId: 12, projectName: 'Архивный объект'}],
      [projectionRequest({id: 73, project: 'Архивный объект', status: 'Новая', materialName: 'Материал', quantity: 1, unit: 'шт'})],
    );

    expect(report.summary).toMatchObject({projects: 0, activeRequests: 1, requestItemsReady: 0, requestsNeedingReview: 1});
    expect(report.reviewItems).toEqual([
      expect.objectContaining({requestId: 73, reason: 'project_inactive', candidateProjectIds: [12]}),
    ]);
  });

  test('does not collapse same-name project candidates that both lack ids', () => {
    const request = projectionRequest({id: 72, project: 'Без ID', status: 'Новая', materialName: 'Материал', quantity: 1, unit: 'шт'});
    const report = buildAllProjectsMaterialProjectionReview(
      [{projectId: null, projectName: 'Без ID', correctedRows: [], requests: [request]}],
      undefined,
      [{projectId: null, projectName: 'Без ID'}, {projectId: null, projectName: 'Без ID'}],
    );

    expect(report.reviewItems).toEqual([
      expect.objectContaining({requestId: 72, reason: 'ambiguous_project_identity'}),
    ]);
  });

  test('does not resolve malformed project ids as one owner', () => {
    const request = projectionRequest({id: 74, project: 'Кривой ID', status: 'Новая', materialName: 'Материал', quantity: 1, unit: 'шт'});
    const report = buildAllProjectsMaterialProjectionReview(
      [{projectId: 0, projectName: 'Кривой ID', correctedRows: [], requests: [request]}],
      undefined,
      [{projectId: 0, projectName: 'Кривой ID'}, {projectId: [82], projectName: 'Кривой ID'}],
    );

    expect(report.reviewItems).toEqual([
      expect.objectContaining({requestId: 74, reason: 'ambiguous_project_identity', candidateProjectIds: []}),
    ]);
  });

  test('prefers an active duplicate request over an earlier closed occurrence', () => {
    const report = buildAllProjectsMaterialProjectionReview([{
      projectId: 13,
      projectName: 'Школа',
      correctedRows: [row('Точный материал', 2)],
      requests: [
        projectionRequest({id: 75, project: 'Школа', status: 'Закрыта', materialName: 'Старая копия', quantity: 1, unit: 'шт'}),
        projectionRequest({id: 75, project: 'Школа', status: 'Новая', materialName: 'Действующая копия', quantity: 1, unit: 'шт'}),
      ],
    }]);

    expect(report.summary).toMatchObject({activeRequests: 1, requestsNeedingReview: 1});
    expect(report.reviewItems).toEqual([
      expect.objectContaining({requestId: 75, requestStatus: 'Новая', materialName: 'Действующая копия'}),
    ]);
  });

  test('ignores manual requests that have no estimate or material-projection lineage', () => {
    const report = buildAllProjectsMaterialProjectionReview([{
      projectId: 14,
      projectName: 'Школа',
      correctedRows: [row('Точный материал', 2)],
      requests: [
        {id: 76, project: 'Школа', status: 'Новая', materialName: 'Ручной материал', quantity: 1, unit: 'шт'},
        projectionRequest({id: 77, project: 'Школа', status: 'Новая', materialName: 'Сметный материал', quantity: 1, unit: 'шт'}),
      ],
    }]);

    expect(report.summary).toMatchObject({activeRequests: 1, requestsNeedingReview: 1});
    expect(report.reviewItems).toEqual([
      expect.objectContaining({requestId: 77, materialName: 'Сметный материал'}),
    ]);
  });

  test('fails closed for null candidates and malformed request project values', () => {
    const report = buildAllProjectsMaterialProjectionReview(
      [{projectId: 15, projectName: 'Школа', correctedRows: [row('Материал', 2)], requests: []}],
      undefined,
      [null, {projectId: 15, projectName: 'Школа'}],
      [projectionRequest({id: 78, project: {name: 'Школа'}, status: 'Новая', materialName: 'Материал', quantity: 1, unit: 'шт'})],
    );

    expect(report.reviewItems).toEqual([
      expect.objectContaining({requestId: 78, projectId: null, reason: 'project_identity_invalid'}),
    ]);
  });

  test('treats duplicate candidate occurrences with the same valid id as ambiguous', () => {
    const request = projectionRequest({id: 79, project: 'Школа', status: 'Новая', materialName: 'Материал', quantity: 1, unit: 'шт'});
    const report = buildAllProjectsMaterialProjectionReview(
      [{projectId: 15, projectName: 'Школа', correctedRows: [row('Материал', 2)], requests: [request]}],
      undefined,
      [{projectId: 15, projectName: 'Школа'}, {projectId: 15, projectName: 'Школа'}],
    );

    expect(report.reviewItems).toEqual([
      expect.objectContaining({requestId: 79, projectId: null, reason: 'ambiguous_project_identity', candidateProjectIds: [15, 15]}),
    ]);
  });

  test('collapses conflicting active duplicates into one fail-closed request occurrence', () => {
    const report = buildAllProjectsMaterialProjectionReview([{
      projectId: 16,
      projectName: 'Школа',
      correctedRows: [row('Материал', 2)],
      requests: [
        projectionRequest({id: 80, project: 'Школа', status: 'Новая', materialName: 'Материал А', quantity: 1, unit: 'шт'}),
        projectionRequest({id: 80, project: 'Другой объект', status: 'Новая', materialName: 'Материал Б', quantity: 3, unit: 'м'}),
      ],
    }]);

    expect(report.summary).toMatchObject({activeRequests: 1, requestItems: 1, requestsNeedingReview: 1, requestItemsNeedingReview: 1});
    expect(report.reviewItems).toEqual([
      expect.objectContaining({
        requestId: 80,
        requestKey: 'id:80',
        projectId: null,
        reason: 'conflicting_request_duplicates',
        candidateNames: ['Материал А', 'Материал Б'],
      }),
    ]);
  });
});
