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
