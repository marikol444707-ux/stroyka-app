import { createMobileInitialDataLoader } from './mobileInitialDataLoader';

const setterNames = [
  'setAiTasks', 'setAllBrigadeItems', 'setBrigadeContracts', 'setCableJournal',
  'setContracts', 'setEstimateReconciliations', 'setHiddenActs',
  'setInitialDataLoaded', 'setInterimActs', 'setMasterProfiles',
  'setMaterialInspections', 'setOwnExpenses', 'setPiecework',
  'setProjectDocuments', 'setProjectMeasurements', 'setProjectPayments',
  'setProjects', 'setStaff', 'setSupervisorActs', 'setSupplyRequests',
  'setUsers', 'setWarehouseMain', 'setWorkJournal',
];

const leadershipPolicy = {
  role: 'директор',
  isFinanceRole: true,
  isSupplyRole: true,
  isInternalRole: true,
  canSeeProjectDocs: true,
  canLoadEstimates: true,
  estimatesLoadPath: '/estimates?summary=true',
  canLoadPeopleData: true,
  canLoadUserDirectory: true,
  canLoadAccountingData: true,
  canLoadBrigadeData: true,
  assignmentsPath: '/ai-tasks',
};

const createDeps = (overrides = {}) => {
  const responses = overrides.responses || {};
  const deps = {
    WORK_JOURNAL_PAGE_LIMIT: 100,
    dataLoadPolicyForUser: jest.fn(() => leadershipPolicy),
    getApi: jest.fn(async path => (
      Object.prototype.hasOwnProperty.call(responses, path) ? responses[path] : []
    )),
    pagedPath: jest.fn((path, params = {}) => `${path}?${new URLSearchParams(params)}`),
    loadMobileScopeOnce: jest.fn(async (scope, loader) => loader()),
    resetWorkJournalPage: jest.fn(),
    applyLoadedEstimates: jest.fn(),
  };
  setterNames.forEach(name => { deps[name] = jest.fn(); });
  return { ...deps, ...overrides, responses };
};

describe('createMobileInitialDataLoader', () => {
  it('loads the complete leadership scope and applies normalized state', async () => {
    const deps = createDeps({
      responses: {
        '/projects': [{ id: 1 }],
        '/work-journal?limit=100': [{ id: 2 }],
        '/estimates?summary=true': [{ id: 3 }],
        '/ai-tasks': [{ id: 4 }],
      },
    });

    await createMobileInitialDataLoader(deps)();

    const paths = deps.getApi.mock.calls.map(([path]) => path);
    expect(deps.loadMobileScopeOnce).toHaveBeenCalledWith('mobile:init', expect.any(Function));
    expect(paths).toEqual([
      '/projects', '/users', '/supply-requests', '/ai-tasks', '/own-expenses',
      '/project-payments', '/work-journal?limit=100', '/staff', '/piecework',
      '/contracts', '/interim-acts', '/master-profiles', '/brigade-contracts',
      '/brigade-contract-items-all', '/estimates?summary=true',
      '/estimate-reconciliations', '/hidden-works-acts', '/material-inspection',
      '/cable-journal', '/supervisor-acts', '/project-documents',
      '/project-measurements',
    ]);
    expect(deps.setProjects).toHaveBeenCalledWith([{ id: 1 }]);
    expect(deps.setWorkJournal).toHaveBeenCalledWith([{ id: 2 }]);
    expect(deps.resetWorkJournalPage).toHaveBeenCalledWith([{ id: 2 }]);
    expect(deps.applyLoadedEstimates).toHaveBeenCalledWith([{ id: 3 }], true);
    expect(deps.setInitialDataLoaded).toHaveBeenLastCalledWith(true);
  });

  it('skips protected project data for a supplier role', async () => {
    const supplierPolicy = {
      ...leadershipPolicy,
      role: 'поставщик',
      isFinanceRole: false,
      isSupplyRole: true,
      isInternalRole: false,
      canSeeProjectDocs: false,
      canLoadEstimates: false,
      canLoadPeopleData: false,
      canLoadUserDirectory: false,
      canLoadAccountingData: false,
      canLoadBrigadeData: false,
    };
    const deps = createDeps({ dataLoadPolicyForUser: jest.fn(() => supplierPolicy) });

    await createMobileInitialDataLoader(deps)();

    expect(deps.getApi.mock.calls.map(([path]) => path)).toEqual(['/supply-requests']);
    expect(deps.setProjects).toHaveBeenCalledWith([]);
    expect(deps.setWorkJournal).toHaveBeenCalledWith([]);
    expect(deps.applyLoadedEstimates).toHaveBeenCalledWith(null, false);
  });

  it('loads warehouse stock only for a warehouse keeper', async () => {
    const warehousePolicy = {
      ...leadershipPolicy,
      role: 'кладовщик',
      isFinanceRole: false,
      isSupplyRole: false,
      isInternalRole: true,
      canSeeProjectDocs: false,
      canLoadEstimates: false,
      canLoadPeopleData: false,
      canLoadUserDirectory: false,
      canLoadAccountingData: false,
      canLoadBrigadeData: false,
    };
    const deps = createDeps({
      dataLoadPolicyForUser: jest.fn(() => warehousePolicy),
      responses: { '/warehouse-main': [{ id: 9 }] },
    });

    await createMobileInitialDataLoader(deps)();

    expect(deps.getApi).toHaveBeenCalledWith('/warehouse-main');
    expect(deps.setWarehouseMain).toHaveBeenCalledWith([{ id: 9 }]);
  });

  it('marks initial data ready even when the scoped loader rejects', async () => {
    const deps = createDeps({
      loadMobileScopeOnce: jest.fn(async () => { throw new Error('network'); }),
    });

    await expect(createMobileInitialDataLoader(deps)()).rejects.toThrow('network');

    expect(deps.setInitialDataLoaded).toHaveBeenLastCalledWith(true);
  });
});
