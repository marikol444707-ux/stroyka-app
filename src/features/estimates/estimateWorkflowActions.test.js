import { createEstimateWorkflowActions } from './estimateWorkflowActions';

describe('estimate workflow detail loading', () => {
  it('loads full estimate sections on demand and merges them into the list', async () => {
    const setEstimatesList = jest.fn();
    const fetchFn = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ([{
        id: 7,
        projectName: 'Лицей',
        status: 'Активная',
        sectionsLoaded: true,
        sections: [{
          name: 'Общестрой',
          items: [{ id: 1, name: 'Цемент', itemType: 'material', unit: 'кг', quantity: 100 }],
        }],
      }]),
    });
    const actions = createEstimateWorkflowActions({
      API: 'https://example.test',
      estimatesList: [],
      setEstimatesList,
      setSelectedEstimate: jest.fn(),
      setEstimateReconciliations: jest.fn(),
      fetchFn,
      localStorageRef: { getItem: () => '' },
    });

    const result = await actions.loadEstimateDetail({
      id: 7,
      projectName: 'Лицей',
      sectionsLoaded: false,
      sections: [],
    });

    expect(fetchFn).toHaveBeenCalledWith('https://example.test/estimates?ids=7', undefined);
    expect(result.sectionsLoaded).toBe(true);
    expect(result.sections[0].items[0]).toMatchObject({
      name: 'Цемент',
      itemType: 'material',
      quantity: 100,
    });
    expect(setEstimatesList).toHaveBeenCalledTimes(1);
  });

  it('does not request details that are already loaded', async () => {
    const fetchFn = jest.fn();
    const loaded = { id: 7, sectionsLoaded: true, sections: [] };
    const actions = createEstimateWorkflowActions({
      API: 'https://example.test',
      estimatesList: [loaded],
      setEstimatesList: jest.fn(),
      setSelectedEstimate: jest.fn(),
      setEstimateReconciliations: jest.fn(),
      fetchFn,
    });

    await expect(actions.loadEstimateDetail(loaded)).resolves.toBe(loaded);
    expect(fetchFn).not.toHaveBeenCalled();
  });

  it('loads several estimate details through one company-scoped request', async () => {
    const setEstimatesList = jest.fn();
    const fetchFn = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ([
        { id: 8, sectionsLoaded: true, sections: [{ name: 'Электрика', items: [] }] },
        { id: 7, sectionsLoaded: true, sections: [{ name: 'Общестрой', items: [] }] },
      ]),
    });
    const actions = createEstimateWorkflowActions({
      API: 'https://example.test',
      estimatesList: [],
      setEstimatesList,
      setSelectedEstimate: jest.fn(),
      setEstimateReconciliations: jest.fn(),
      fetchFn,
      localStorageRef: { getItem: () => '' },
    });

    const loaded = await actions.loadEstimateDetails([
      { id: 7, sectionsLoaded: false, sections: [] },
      { id: 8, sectionsLoaded: false, sections: [] },
    ]);

    expect(fetchFn).toHaveBeenCalledWith('https://example.test/estimates?ids=7%2C8', undefined);
    expect(loaded.map(estimate => estimate.sectionsLoaded)).toEqual([true, true]);
    expect(setEstimatesList).toHaveBeenCalledTimes(1);
  });

  it('loads both full estimates before building the comparison statement', async () => {
    const showPreview = jest.fn();
    const buildEstimateDiffDocContent = jest.fn(() => '<div>comparison</div>');
    const fetchFn = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ([
        {
          id: 7,
          sectionsLoaded: true,
          summaryTotal: 1000,
          sections: [{ name: 'Отделка', items: [{ name: 'Штукатурка', type: 'work', isImported: true, unit: 'м2', quantity: 10, lineTotal: 1000, totalWork: 1000 }] }],
        },
        {
          id: 8,
          sectionsLoaded: true,
          summaryTotal: 1200,
          sections: [{ name: 'Отделка', items: [{ name: 'Штукатурка', type: 'work', isImported: true, unit: 'м2', quantity: 12, lineTotal: 1200, totalWork: 1200 }] }],
        },
      ]),
    });
    const actions = createEstimateWorkflowActions({
      API: 'https://example.test',
      estimatesList: [],
      setEstimatesList: jest.fn(),
      setSelectedEstimate: jest.fn(),
      setEstimateReconciliations: jest.fn(),
      fetchFn,
      localStorageRef: { getItem: () => '' },
      showPreview,
      buildEstimateDiffDocContent,
    });

    await expect(actions.openEstimateDiffPreview(
      { id: 7, sectionsLoaded: false, sections: [], summaryTotal: 1000 },
      { id: 8, sectionsLoaded: false, sections: [], summaryTotal: 1200 },
    )).resolves.toBe(true);

    expect(fetchFn).toHaveBeenCalledWith('https://example.test/estimates?ids=7%2C8', undefined);
    expect(buildEstimateDiffDocContent).toHaveBeenCalledWith(expect.objectContaining({
      diff: expect.objectContaining({
        impact: 200,
        changed: [expect.objectContaining({ impact: 200 })],
      }),
    }));
    expect(showPreview).toHaveBeenCalledWith('<div>comparison</div>', 'Сопоставительная ведомость');
  });

  it('loads all estimate pairs once before building the project change summary', async () => {
    const showPreview = jest.fn();
    const buildProjectEstimateDiffSummaryDocContent = jest.fn(() => '<div>project summary</div>');
    const fetchFn = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ([7, 8, 9, 10].map(id => ({
        id,
        sectionsLoaded: true,
        projectName: 'Лицей',
        workPackage: id < 9 ? 'Отделка' : 'Электрика',
        sections: [{ name: 'Работы', items: [] }],
      }))),
    });
    const actions = createEstimateWorkflowActions({
      API: 'https://example.test',
      estimatesList: [],
      setEstimatesList: jest.fn(),
      setSelectedEstimate: jest.fn(),
      setEstimateReconciliations: jest.fn(),
      fetchFn,
      localStorageRef: { getItem: () => '' },
      showPreview,
      buildProjectEstimateDiffSummaryDocContent,
    });

    await expect(actions.openProjectEstimateDiffSummary('Лицей', [
      { base: { id: 7, sectionsLoaded: false }, next: { id: 8, sectionsLoaded: false } },
      { base: { id: 9, sectionsLoaded: false }, next: { id: 10, sectionsLoaded: false } },
    ])).resolves.toBe(true);

    expect(fetchFn).toHaveBeenCalledWith('https://example.test/estimates?ids=7%2C8%2C9%2C10', undefined);
    expect(buildProjectEstimateDiffSummaryDocContent).toHaveBeenCalledWith(expect.objectContaining({
      projectName: 'Лицей',
      packageCount: 2,
    }));
    expect(showPreview).toHaveBeenCalledWith('<div>project summary</div>', 'Свод изменений смет по объекту');
  });

  it('deletes a confirmed unused draft through the explicit hard-delete endpoint', async () => {
    const setEstimatesList = jest.fn();
    const setSelectedEstimate = jest.fn();
    const setEstimateReconciliations = jest.fn();
    const fetchFn = jest.fn().mockResolvedValue({ ok: true, json: async () => ({ ok: true, id: 7 }) });
    const actions = createEstimateWorkflowActions({
      API: 'https://example.test',
      estimatesList: [{ id: 7, name: 'Лишний черновик', status: 'Черновик' }],
      setEstimatesList,
      setSelectedEstimate,
      setEstimateReconciliations,
      fetchFn,
      confirmFn: () => true,
    });

    await actions.deleteEstimateRemote({ id: 7, name: 'Лишний черновик', status: 'Черновик' });

    expect(fetchFn).toHaveBeenCalledWith('https://example.test/estimates/7?hard=true', { method: 'DELETE' });
    expect(setEstimatesList).toHaveBeenCalled();
    expect(setSelectedEstimate).toHaveBeenCalled();
    expect(setEstimateReconciliations).toHaveBeenCalled();
  });

  it('finishes estimate deactivation after the server accepts the status change', async () => {
    const setEstimatesList = jest.fn();
    const setSelectedEstimate = jest.fn();
    const notify = jest.fn();
    const fetchFn = jest.fn().mockResolvedValue({ ok: true, json: async () => ({ ok: true, status: 'Черновик' }) });
    const estimate = { id: 7, name: 'Ошибочная смета', status: 'Активная' };
    const actions = createEstimateWorkflowActions({
      API: 'https://example.test',
      estimatesList: [estimate],
      setEstimatesList,
      setSelectedEstimate,
      setEstimateReconciliations: jest.fn(),
      fetchFn,
      notify,
    });

    await expect(actions.setEstimateStatusRemote(estimate, 'Черновик')).resolves.toBe(true);

    expect(setEstimatesList).toHaveBeenCalledWith([{ ...estimate, status: 'Черновик' }]);
    expect(setSelectedEstimate).toHaveBeenCalled();
    expect(notify).toHaveBeenCalledWith(expect.stringContaining('Черновик'), 'estimate');
  });

  it('loads full revisions and saves their reconciliation when a draft becomes active', async () => {
    const setEstimateReconciliations = jest.fn();
    const queueEstimateDiffReviewTask = jest.fn();
    const autoReconcileEstimateChanges = jest.fn();
    const fullBase = {
      id: 7,
      projectName: 'Лицей',
      smetaType: 'Заказчик',
      workPackage: 'Отделка',
      status: 'Активная',
      sectionsLoaded: true,
      sections: [{ name: 'Стены', items: [{ name: 'Штукатурка', quantity: 80 }] }],
    };
    const fullNext = {
      id: 8,
      projectName: 'Лицей',
      smetaType: 'Заказчик',
      workPackage: 'Отделка',
      status: 'Черновик',
      sectionsLoaded: true,
      sections: [{ name: 'Стены', items: [{ name: 'Штукатурка', quantity: 90 }] }],
    };
    const fetchFn = jest.fn(async (url, options = {}) => {
      if (url.endsWith('/estimates?ids=7%2C8')) {
        return { ok: true, json: async () => [fullBase, fullNext] };
      }
      if (url.endsWith('/estimates/8/status') && options.method === 'PUT') {
        return { ok: true, json: async () => ({ ok: true, status: 'Активная' }) };
      }
      if (url.endsWith('/estimate-reconciliations') && options.method === 'POST') {
        return { ok: true, json: async () => ({ ok: true, id: 44 }) };
      }
      if (url.endsWith('/estimate-reconciliations/44')) {
        return {
          ok: true,
          json: async () => ({ id: 44, baseEstimateId: 7, nextEstimateId: 8, items: [] }),
        };
      }
      throw new Error('Unexpected request: ' + url);
    });
    const baseSummary = { ...fullBase, sectionsLoaded: false, sections: [] };
    const nextSummary = { ...fullNext, sectionsLoaded: false, sections: [] };
    const actions = createEstimateWorkflowActions({
      API: 'https://example.test',
      estimatesList: [baseSummary, nextSummary],
      estimateReconciliations: [],
      setEstimatesList: jest.fn(),
      setSelectedEstimate: jest.fn(),
      setEstimateReconciliations,
      fetchFn,
      localStorageRef: { getItem: () => '' },
      apiAuthHeaders: (headers = {}) => headers,
      queueEstimateDiffReviewTask,
      autoReconcileEstimateChanges,
    });

    await expect(actions.setEstimateStatusRemote(nextSummary, 'Активная')).resolves.toBe(true);

    expect(fetchFn.mock.calls.map(([url]) => url)).toEqual([
      'https://example.test/estimates?ids=7%2C8',
      'https://example.test/estimates/8/status',
      'https://example.test/estimate-reconciliations',
      'https://example.test/estimate-reconciliations/44',
    ]);
    expect(queueEstimateDiffReviewTask).toHaveBeenCalledWith(
      expect.objectContaining({ id: 7, sectionsLoaded: true }),
      expect.objectContaining({ id: 8, sectionsLoaded: true, status: 'Активная' }),
      'Смета активирована',
    );
    expect(autoReconcileEstimateChanges).toHaveBeenCalledWith(
      expect.objectContaining({ id: 7, sectionsLoaded: true }),
      expect.objectContaining({ id: 8, sectionsLoaded: true, status: 'Активная' }),
      'Смета активирована',
    );
    expect(setEstimateReconciliations).toHaveBeenCalled();
  });

  it('shows a useful message when the status request cannot reach the server', async () => {
    const alertFn = jest.fn();
    const estimate = { id: 7, name: 'Ошибочная смета', status: 'Активная' };
    const actions = createEstimateWorkflowActions({
      API: 'https://example.test',
      estimatesList: [estimate],
      setEstimatesList: jest.fn(),
      setSelectedEstimate: jest.fn(),
      setEstimateReconciliations: jest.fn(),
      fetchFn: jest.fn().mockRejectedValue(new Error('network timeout')),
      alertFn,
    });

    await expect(actions.setEstimateStatusRemote(estimate, 'Черновик')).resolves.toBe(false);
    expect(alertFn).toHaveBeenCalledWith(expect.stringContaining('network timeout'));
  });

  it('shows a useful message when the delete request cannot reach the server', async () => {
    const alertFn = jest.fn();
    const actions = createEstimateWorkflowActions({
      API: 'https://example.test',
      estimatesList: [{ id: 7, name: 'Лишний черновик', status: 'Черновик' }],
      setEstimatesList: jest.fn(),
      setSelectedEstimate: jest.fn(),
      setEstimateReconciliations: jest.fn(),
      fetchFn: jest.fn().mockRejectedValue(new Error('network timeout')),
      alertFn,
      confirmFn: () => true,
    });

    await expect(actions.deleteEstimateRemote({ id: 7, name: 'Лишний черновик', status: 'Черновик' })).resolves.toBe(false);
    expect(alertFn).toHaveBeenCalledWith(expect.stringContaining('network timeout'));
  });
});
