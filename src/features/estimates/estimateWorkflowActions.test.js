import { createEstimateWorkflowActions } from './estimateWorkflowActions';

describe('estimate workflow detail loading', () => {
  it('loads full estimate sections on demand and merges them into the list', async () => {
    const setEstimatesList = jest.fn();
    const fetchFn = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        id: 7,
        projectName: 'Лицей',
        status: 'Активная',
        sectionsLoaded: true,
        sections: [{
          name: 'Общестрой',
          items: [{ id: 1, name: 'Цемент', itemType: 'material', unit: 'кг', quantity: 100 }],
        }],
      }),
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

    expect(fetchFn).toHaveBeenCalledWith('https://example.test/estimates/7', undefined);
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
});
