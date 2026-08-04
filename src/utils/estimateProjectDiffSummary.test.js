import {
  buildProjectEstimateDiffSummaryPayload,
  projectEstimateRevisionPairs,
} from './estimateDiffDocumentUtils';

const estimate = ({ id, workPackage, quantity, total }) => ({
  id,
  projectName: 'Лицей',
  smetaType: 'Заказчик',
  workPackage,
  sectionsLoaded: true,
  sections: [{
    name: 'Работы',
    items: [{
      isImported: true,
      type: 'work',
      name: 'Штукатурка стен',
      unit: 'м2',
      quantity,
      totalWork: total,
      lineTotal: total,
    }],
  }],
});

describe('project estimate difference summary', () => {
  test('uses the saved reconciliation base for the current active estimate', () => {
    const base = estimate({ id: 1, workPackage: 'Отделка', quantity: 80, total: 80000 });
    const unrelatedDraft = estimate({ id: 3, workPackage: 'Отделка', quantity: 85, total: 85000 });
    const active = { ...estimate({ id: 2, workPackage: 'Отделка', quantity: 90, total: 90000 }), status: 'Активная' };
    const pairs = projectEstimateRevisionPairs({
      project: { id: 44, name: 'Лицей' },
      estimates: [
        { ...base, projectId: 44, status: 'Черновик' },
        { ...active, projectId: 44 },
        { ...unrelatedDraft, projectId: 44, status: 'Черновик' },
      ],
      reconciliations: [{ id: 10, baseEstimateId: 1, nextEstimateId: 2 }],
    });

    expect(pairs).toHaveLength(1);
    expect(pairs[0].base.id).toBe(1);
    expect(pairs[0].next.id).toBe(2);
  });

  test('falls back to the revision before the active estimate, not a later unrelated draft', () => {
    const pairs = projectEstimateRevisionPairs({
      project: { id: 44, name: 'Лицей' },
      estimates: [
        { ...estimate({ id: 1, workPackage: 'Отделка', quantity: 80, total: 80000 }), projectId: 44, status: 'Черновик' },
        { ...estimate({ id: 2, workPackage: 'Отделка', quantity: 90, total: 90000 }), projectId: 44, status: 'Активная' },
        { ...estimate({ id: 3, workPackage: 'Отделка', quantity: 95, total: 95000 }), projectId: 44, status: 'Черновик' },
      ],
      reconciliations: [],
    });

    expect(pairs[0].base.id).toBe(1);
    expect(pairs[0].next.id).toBe(2);
  });

  test('collects only changed rows from every estimate package', () => {
    const payload = buildProjectEstimateDiffSummaryPayload({
      projectName: 'Лицей',
      pairs: [
        { base: estimate({ id: 1, workPackage: 'Отделка', quantity: 80, total: 80000 }), next: estimate({ id: 2, workPackage: 'Отделка', quantity: 90, total: 90000 }) },
        { base: estimate({ id: 3, workPackage: 'Электрика', quantity: 10, total: 20000 }), next: estimate({ id: 4, workPackage: 'Электрика', quantity: 10, total: 20000 }) },
      ],
    });

    expect(payload.packageCount).toBe(2);
    expect(payload.changedPackageCount).toBe(1);
    expect(payload.rows).toEqual([expect.objectContaining({
      workPackage: 'Отделка',
      name: 'Штукатурка стен',
      baseQty: 80,
      nextQty: 90,
      baseSum: 80000,
      nextSum: 90000,
      impact: 10000,
    })]);
    expect(payload.impact).toBe(10000);
  });
});
