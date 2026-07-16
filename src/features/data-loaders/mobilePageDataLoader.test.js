import { createMobilePageDataLoader } from './mobilePageDataLoader';

const setterNames = [
  'setAiFindings', 'setAiTasks', 'setSupplyHistory', 'setSupplyDeliveries', 'setSupplierCatalog',
  'setEstimateReconciliations', 'setPricelists', 'setMaterialNorms', 'setMaterialAliases',
  'setMaterialNormOverrides', 'setMaterialNormSuggestions', 'setBrigadeContracts',
  'setAllBrigadeItems', 'setAllBrigadePayments', 'setStaff', 'setPiecework', 'setUsers',
  'setMasterProfiles', 'setTimesheet', 'setPdConsents', 'setInviteCodes',
];

const createDeps = (overrides = {}) => {
  const responses = overrides.responses || {};
  const scopes = [];
  const deps = {
    activePage: 'dashboard',
    user: { id: 1 },
    AUDIT_LOG_PAGE_LIMIT: 50,
    MATERIAL_NORMS_PAGE_LIMIT: 100,
    MATERIALS_PAGE_LIMIT: 100,
    WORK_JOURNAL_PAGE_LIMIT: 100,
    mobileLoadedScopesRef: { current: new Set() },
    dataLoadPolicyForUser: jest.fn(() => ({
      role: 'директор',
      isLeadershipRole: true,
      isFinanceRole: true,
      isWarehouseRole: false,
      isSupplyRole: false,
      canSeeSupplierInvoices: true,
      isInternalRole: true,
      canSeeProjectDocs: true,
      isWorkerRole: false,
      canLoadPeopleData: true,
      canLoadUserDirectory: true,
      canLoadAccountingData: true,
      canLoadBrigadeData: true,
      canLoadBrigadePayments: true,
      canLoadEstimates: true,
      estimatesLoadPath: '/estimates?summary=true',
      assignmentsPath: '/ai-tasks',
    })),
    getApi: jest.fn(async (path) => Object.prototype.hasOwnProperty.call(responses, path) ? responses[path] : []),
    pagedPath: jest.fn((path, params = {}) => `${path}?${new URLSearchParams(params)}`),
    loadMobileScopeOnce: jest.fn(async (scope, loader) => {
      scopes.push(scope);
      await loader();
    }),
    markEstimatesLoading: jest.fn(),
    applyLoadedEstimates: jest.fn(),
    resetWorkJournalPage: jest.fn(),
    resetMaterialsPage: jest.fn(),
    resetMaterialNormsPage: jest.fn(),
    scopes,
  };
  setterNames.forEach(name => { deps[name] = jest.fn(); });
  return { ...deps, ...overrides, responses };
};

describe('createMobilePageDataLoader', () => {
  it('does not load a scope without an authenticated user', async () => {
    const deps = createDeps({ user: null });

    await createMobilePageDataLoader(deps)('dashboard');

    expect(deps.loadMobileScopeOnce).not.toHaveBeenCalled();
    expect(deps.getApi).not.toHaveBeenCalled();
  });

  it('loads dashboard data using the role policy', async () => {
    const deps = createDeps({
      responses: {
        '/ai-findings': [{ id: 1 }],
        '/ai-tasks': [{ id: 2 }],
        '/supply-history': [{ id: 3 }],
      },
    });

    await createMobilePageDataLoader(deps)('dashboard');

    expect(deps.scopes).toEqual(['mobile:dashboard']);
    expect(deps.getApi.mock.calls.map(([path]) => path)).toEqual([
      '/ai-findings', '/ai-tasks', '/supply-history', '/supplier-catalog',
    ]);
    expect(deps.setAiFindings).toHaveBeenCalledWith([{ id: 1 }]);
    expect(deps.setAiTasks).toHaveBeenCalledWith([{ id: 2 }]);
    expect(deps.setSupplyHistory).toHaveBeenCalledWith([{ id: 3 }]);
    expect(deps.setSupplyDeliveries).toHaveBeenCalledWith([]);
    expect(deps.setSupplierCatalog).toHaveBeenCalledWith([]);
  });

  it('loads estimate dependencies and reopens the scope after a failed estimate response', async () => {
    const deps = createDeps({
      responses: {
        '/estimates?summary=true': null,
        '/estimate-reconciliations': [{ id: 4 }],
        '/pricelists': [{ id: 5 }],
        '/material-norms?limit=100': [{ id: 6 }],
        '/material-aliases': [{ id: 7 }],
        '/material-norms/overrides': [{ id: 8 }],
        '/material-norm-suggestions': [{ id: 9 }],
        '/brigade-contracts': [{ id: 10 }],
        '/brigade-contract-items-all': [{ id: 11 }],
        '/brigade-payments': [{ id: 12 }],
      },
    });
    deps.mobileLoadedScopesRef.current.add('mobile:estimates');

    await createMobilePageDataLoader(deps)('estimates');

    expect(deps.scopes).toEqual(['mobile:estimates']);
    expect(deps.markEstimatesLoading).toHaveBeenCalledWith(true);
    expect(deps.applyLoadedEstimates).toHaveBeenCalledWith(null, true);
    expect(deps.mobileLoadedScopesRef.current.has('mobile:estimates')).toBe(false);
    expect(deps.resetMaterialNormsPage).toHaveBeenCalledWith([{ id: 6 }]);
    expect(deps.setAllBrigadePayments).toHaveBeenCalledWith([{ id: 12 }]);
  });

  it('loads personnel data and converts timesheet rows to the existing lookup map', async () => {
    const deps = createDeps({
      responses: {
        '/staff': [{ id: 20 }],
        '/piecework': [{ id: 21 }],
        '/users': [{ id: 22 }],
        '/master-profiles': [{ id: 23 }],
        '/timesheet': [{ staffId: 20, day: '2026-07-17' }],
        '/pd-consents': [{ id: 24 }],
        '/invite-codes': [{ id: 25 }],
      },
    });

    await createMobilePageDataLoader(deps)('personnel');

    expect(deps.scopes).toEqual(['mobile:people']);
    expect(deps.getApi.mock.calls.map(([path]) => path)).toEqual([
      '/staff', '/piecework', '/users', '/master-profiles', '/timesheet', '/pd-consents', '/invite-codes',
    ]);
    expect(deps.setStaff).toHaveBeenCalledWith([{ id: 20 }]);
    expect(deps.setTimesheet).toHaveBeenCalledWith({ '20-2026-07-17': true });
    expect(deps.setInviteCodes).toHaveBeenCalledWith([{ id: 25 }]);
  });
});
