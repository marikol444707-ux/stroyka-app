import { act, renderHook } from '@testing-library/react';
import { useAppDataLoaders } from './useAppDataLoaders';

const setter = () => jest.fn();

test('refreshing the warehouse reloads tools, tool history and inventory', async () => {
  const setTools = setter();
  const setToolHistory = setter();
  const setInventory = setter();
  global.fetch = jest.fn(async url => ({ok: true, json: async () => [{id: url}]}));

  const {result} = renderHook(() => useAppDataLoaders({
    activePage: 'warehouse',
    API: '/api',
    AUDIT_LOG_PAGE_LIMIT: 50,
    buildPagedPath: path => path,
    canAccessRole: () => false,
    createMaterialNormsPageState: value => value,
    createMaterialsPageState: value => value,
    createWorkJournalPageState: value => value,
    estimatesTab: 'list',
    initialDataLoaded: false,
    MATERIAL_NORMS_PAGE_LIMIT: 100,
    materialNormSearch: '',
    MATERIALS_PAGE_LIMIT: 100,
    mergeRowsByIdValue: (_current, incoming) => incoming,
    mobileApiRequestsRef: {current: new Map()},
    mobileLoadedScopesRef: {current: new Set()},
    mobileScopeForPage: page => `mobile:${page}`,
    normalizeEstimateList: rows => rows,
    roleFlagsForUser: () => ({
      role: 'директор', isLeadershipRole: true, isFinanceRole: false,
      isWarehouseRole: true, isSupplyRole: true, canSeeSupplierInvoices: true,
      isInternalRole: true, canSeeProjectDocs: true,
    }),
    ROLES: {},
    setMaterials: setter(), setMaterialsPage: setter(), setInvoices: setter(),
    setWarehouseMain: setter(), setWarehouseMovements: setter(), setHistory: setter(),
    setWarehouses: setter(), setMaterialTransfers: setter(), setMaterialInspections: setter(),
    setCableJournal: setter(), setSupplyRequests: setter(), setSupplyHistory: setter(),
    setSupplyDeliveries: setter(), setTools, setToolHistory, setInventory,
    setEstimatesPage: setter(), setInitialDataLoaded: setter(), setUser: setter(),
    user: {id: 1, role: 'директор'},
    WORK_JOURNAL_PAGE_LIMIT: 100,
  }));

  await act(async () => {
    await result.current.refreshData('warehouse');
  });

  const paths = global.fetch.mock.calls.map(([url]) => url);
  expect(paths).toEqual(expect.arrayContaining(['/api/tools', '/api/tool-history', '/api/inventory']));
  expect(setTools).toHaveBeenCalledWith([{id: '/api/tools'}]);
  expect(setToolHistory).toHaveBeenCalledWith([{id: '/api/tool-history'}]);
  expect(setInventory).toHaveBeenCalledWith([{id: '/api/inventory'}]);
});
