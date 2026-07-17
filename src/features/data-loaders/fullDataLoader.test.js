import { createFullDataLoader } from './fullDataLoader';

const setterNames = [
  'setAccountablePayments', 'setAiFindings', 'setAiTasks', 'setAllBrigadeItems',
  'setAllBrigadePayments', 'setAuditLog', 'setBrigadeContracts', 'setCableJournal',
  'setChecklists', 'setClients', 'setCompanyDocuments', 'setCompanyRequisites',
  'setContracts', 'setEstimateReconciliations', 'setEstimatesPage', 'setExpenseReports',
  'setHiddenActs', 'setHistory', 'setInspectionOrders', 'setInterimActs', 'setInventory',
  'setInviteCodes', 'setInvoices', 'setLeads', 'setManualExpenses', 'setMasterProfiles',
  'setMaterialAliases', 'setMaterialInspections', 'setMaterialNormOverrides',
  'setMaterialNorms', 'setMaterialNormSuggestions', 'setMaterials', 'setMaterialTransfers',
  'setMeasurementRoomDrafts', 'setOwnExpenses', 'setPdConsents', 'setPiecework',
  'setPrescriptionsList', 'setPricelists', 'setProjectDocuments', 'setProjectLetters',
  'setProjectMeasurements', 'setProjectPayments', 'setProjects', 'setProjectStages',
  'setRoomDoors', 'setRooms', 'setRoomWindows', 'setRoomWorks', 'setSalaryPayments',
  'setStaff', 'setSupervisorActs', 'setSupplierCatalog', 'setSupplierInvoices',
  'setSupplierOffers', 'setSuppliers', 'setSupplyClaims', 'setSupplyDeliveries',
  'setSupplyHistory', 'setSupplyRequests', 'setSupplyTemplates', 'setTbJournal',
  'setTimesheet', 'setToolHistory', 'setTools', 'setUnexpectedWorksList', 'setUsers',
  'setWarehouseMain', 'setWarehouseMovements', 'setWarehouses', 'setWarrantyDefects',
  'setWorkJournal',
];

const leadershipPolicy = {
  role: 'директор',
  isLeadershipRole: true,
  isFinanceRole: true,
  isWarehouseRole: true,
  isSupplyRole: true,
  canSeeSupplierInvoices: true,
  isInternalRole: true,
  canSeeProjectDocs: true,
  canLoadPeopleData: true,
  canLoadUserDirectory: true,
  canLoadAccountingData: true,
  canLoadBrigadeData: true,
  canLoadBrigadePayments: true,
  canLoadEstimates: true,
  estimatesLoadPath: '/estimates?summary=true',
  assignmentsPath: '/ai-tasks',
};

const createDeps = (overrides = {}) => {
  const responses = overrides.responses || {};
  const failedPaths = new Set(overrides.failedPaths || []);
  const unauthorizedPaths = new Set(overrides.unauthorizedPaths || []);
  const fetchMock = jest.fn(async (url) => {
    const path = String(url).replace('https://example.test', '');
    if (unauthorizedPaths.has(path)) return { ok: false, status: 401 };
    if (failedPaths.has(path)) return { ok: false, status: 500 };
    return {
      ok: true,
      status: 200,
      json: async () => Object.prototype.hasOwnProperty.call(responses, path) ? responses[path] : [],
    };
  });
  const deps = {
    API: 'https://example.test',
    AUDIT_LOG_PAGE_LIMIT: 50,
    MATERIAL_NORMS_PAGE_LIMIT: 100,
    MATERIALS_PAGE_LIMIT: 100,
    WORK_JOURNAL_PAGE_LIMIT: 100,
    user: { id: 1, name: 'Директор' },
    mobileLoadedScopesRef: { current: new Set() },
    dataLoadPolicyForUser: jest.fn(() => leadershipPolicy),
    pagedPath: jest.fn((path, params = {}) => `${path}?${new URLSearchParams(params)}`),
    markEstimatesLoading: jest.fn(),
    applyLoadedEstimates: jest.fn(),
    resetWorkJournalPage: jest.fn(),
    resetMaterialsPage: jest.fn(),
    resetMaterialNormsPage: jest.fn(),
    handleApiUnauthorized: jest.fn(),
    setInitialDataLoaded: jest.fn(),
    fetchImpl: fetchMock,
  };
  setterNames.forEach(name => { deps[name] = jest.fn(); });
  return { ...deps, ...overrides, responses, fetchImpl: fetchMock };
};

describe('createFullDataLoader', () => {
  beforeEach(() => {
    localStorage.clear();
    localStorage.setItem('authToken', 'token');
  });

  it('loads the complete leadership data scope and marks it as ready', async () => {
    const deps = createDeps({
      responses: {
        '/projects': [{ id: 1 }],
        '/estimates?summary=true': [{ id: 2 }],
        '/timesheet': [{ staffId: 7, day: '2026-07-17' }],
      },
    });

    await createFullDataLoader(deps)();

    const paths = deps.fetchImpl.mock.calls.map(([url]) => String(url).replace(deps.API, ''));
    expect(paths).toEqual(expect.arrayContaining([
      '/projects', '/materials?limit=100', '/estimates?summary=true', '/warehouse-main',
      '/staff', '/users', '/supplier-invoices', '/ai-findings', '/ai-tasks', '/timesheet',
    ]));
    expect(deps.setProjects).toHaveBeenCalledWith([{ id: 1 }]);
    expect(deps.applyLoadedEstimates).toHaveBeenCalledWith([{ id: 2 }], true);
    expect(deps.setTimesheet).toHaveBeenCalledWith({ '7-2026-07-17': true });
    expect(deps.mobileLoadedScopesRef.current.has('full')).toBe(true);
    expect(deps.setInitialDataLoaded).toHaveBeenLastCalledWith(true);
  });

  it('does not request protected data for a supplier role', async () => {
    const supplierPolicy = Object.fromEntries(Object.keys(leadershipPolicy).map(key => [key, false]));
    Object.assign(supplierPolicy, {
      role: 'поставщик',
      estimatesLoadPath: '/estimates?summary=true',
      assignmentsPath: '/ai-tasks',
    });
    const deps = createDeps({ dataLoadPolicyForUser: jest.fn(() => supplierPolicy) });

    await createFullDataLoader(deps)();

    const paths = deps.fetchImpl.mock.calls.map(([url]) => String(url).replace(deps.API, ''));
    expect(paths).not.toEqual(expect.arrayContaining([
      '/projects', '/materials?limit=100', '/users', '/estimates?summary=true', '/project-documents',
    ]));
    expect(paths).toContain('/crm/lead-summaries');
    expect(deps.setProjects).toHaveBeenCalledWith([]);
  });

  it('keeps existing state when an endpoint fails', async () => {
    const deps = createDeps({ failedPaths: ['/projects'] });

    await createFullDataLoader(deps)();

    expect(deps.setProjects).not.toHaveBeenCalled();
    expect(deps.mobileLoadedScopesRef.current.has('full')).toBe(true);
    expect(deps.setInitialDataLoaded).toHaveBeenLastCalledWith(true);
  });

  it('delegates unauthorized responses to the session handler', async () => {
    const deps = createDeps({ unauthorizedPaths: ['/projects'] });

    await createFullDataLoader(deps)();

    expect(deps.handleApiUnauthorized).toHaveBeenCalled();
    expect(deps.setProjects).not.toHaveBeenCalled();
    expect(deps.setInitialDataLoaded).toHaveBeenLastCalledWith(true);
  });
});
