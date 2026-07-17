import { createPagedDataLoaders } from './pagedDataLoaders';

const createDeps = (overrides = {}) => ({
  MATERIAL_NORMS_PAGE_LIMIT: 20,
  MATERIALS_PAGE_LIMIT: 30,
  WORK_JOURNAL_PAGE_LIMIT: 40,
  createMaterialNormsPageState: jest.fn((params, limit) => ({...params, limit})),
  createMaterialsPageState: jest.fn((params, limit) => ({...params, limit})),
  createWorkJournalPageState: jest.fn((params, limit) => ({...params, limit})),
  getApi: jest.fn(async () => []),
  mergeRowsById: jest.fn((current, incoming) => [...current, ...incoming]),
  pagedPath: jest.fn((path, params) => `${path}?${JSON.stringify(params)}`),
  setMaterialNorms: jest.fn(),
  setMaterialNormsPage: jest.fn(),
  setMaterials: jest.fn(),
  setMaterialsPage: jest.fn(),
  setWorkJournal: jest.fn(),
  setWorkJournalPage: jest.fn(),
  ...overrides,
});

describe('createPagedDataLoaders', () => {
  it('loads and merges a page of project materials', async () => {
    const rows = [{id: 2}, {id: 3}];
    const deps = createDeps({getApi: jest.fn(async () => rows)});
    const loaders = createPagedDataLoaders(deps);

    await expect(loaders.loadMaterialsPage({
      projectName: 'Лицей',
      search: 'кабель',
      offset: 30,
    })).resolves.toEqual(rows);

    expect(deps.pagedPath).toHaveBeenCalledWith('/materials', {
      project_name: 'Лицей',
      search: 'кабель',
      limit: 30,
      offset: 30,
    });
    expect(deps.getApi).toHaveBeenCalledWith(expect.stringContaining('/materials?'), []);
    const mergeUpdater = deps.setMaterials.mock.calls[0][0];
    expect(mergeUpdater([{id: 1}])).toEqual([{id: 1}, {id: 2}, {id: 3}]);
    expect(deps.setMaterialsPage).toHaveBeenLastCalledWith({
      projectName: 'Лицей',
      search: 'кабель',
      hasMore: false,
      loading: false,
      error: '',
    });
  });

  it('loads material norms with their own page limit', async () => {
    const rows = Array.from({length: 20}, (_, id) => ({id}));
    const deps = createDeps({getApi: jest.fn(async () => rows)});
    const loaders = createPagedDataLoaders(deps);

    await loaders.loadMaterialNormsPage({search: 'штукатурка', offset: 20});

    expect(deps.pagedPath).toHaveBeenCalledWith('/material-norms', {
      search: 'штукатурка',
      limit: 20,
      offset: 20,
    });
    expect(deps.setMaterialNormsPage).toHaveBeenLastCalledWith({
      search: 'штукатурка',
      hasMore: true,
      loading: false,
      error: '',
    });
  });

  it('loads a filtered work journal page and builds its page state', async () => {
    const rows = [{id: 7}];
    const deps = createDeps({getApi: jest.fn(async () => rows)});
    const loaders = createPagedDataLoaders(deps);

    await loaders.loadWorkJournalPage({
      projectName: 'Лицей',
      search: 'монтаж',
      dateFrom: '2026-07-01',
      dateTo: '2026-07-17',
      offset: 40,
    });

    expect(deps.pagedPath).toHaveBeenCalledWith('/work-journal', {
      project_name: 'Лицей',
      search: 'монтаж',
      date_from: '2026-07-01',
      date_to: '2026-07-17',
      limit: 40,
      offset: 40,
    });
    expect(deps.createWorkJournalPageState).toHaveBeenCalledWith({
      projectName: 'Лицей',
      search: 'монтаж',
      dateFrom: '2026-07-01',
      dateTo: '2026-07-17',
      rows,
      loading: false,
      error: '',
    }, 40);
  });

  it('turns malformed payloads into empty row lists', async () => {
    const deps = createDeps({getApi: jest.fn(async () => ({detail: 'bad payload'}))});
    const loaders = createPagedDataLoaders(deps);

    await expect(loaders.loadMaterialsPage()).resolves.toEqual([]);
    const mergeUpdater = deps.setMaterials.mock.calls[0][0];
    expect(mergeUpdater([{id: 1}])).toEqual([{id: 1}]);
  });

  it('reports a page error and keeps the loader retryable', async () => {
    const failure = new Error('network');
    const deps = createDeps({getApi: jest.fn(async () => { throw failure; })});
    const loaders = createPagedDataLoaders(deps);

    await expect(loaders.loadWorkJournalPage({projectName: 'Лицей'})).resolves.toEqual([]);

    const errorUpdater = deps.setWorkJournalPage.mock.calls.at(-1)[0];
    expect(errorUpdater({loading: true, error: ''})).toEqual({
      loading: false,
      error: 'Не удалось загрузить ЖПР',
    });
  });

  it('resets all paged states through the shared state builders', () => {
    const deps = createDeps();
    const loaders = createPagedDataLoaders(deps);
    const rows = [{id: 11}];

    loaders.resetWorkJournalPage(rows);
    loaders.resetMaterialNormsPage(rows);
    loaders.resetMaterialsPage(rows);

    expect(deps.createWorkJournalPageState).toHaveBeenCalledWith({
      rows,
      loading: false,
      error: '',
    }, 40);
    expect(deps.createMaterialNormsPageState).toHaveBeenCalledWith({
      rows,
      loading: false,
      error: '',
    }, 20);
    expect(deps.createMaterialsPageState).toHaveBeenCalledWith({
      rows,
      loading: false,
      error: '',
    }, 30);
  });
});
