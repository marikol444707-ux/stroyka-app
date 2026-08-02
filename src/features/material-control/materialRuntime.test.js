import { createMaterialRuntime, createMaterialRuntimeCache } from './materialRuntime';
import { buildMaterialControlSummary, buildMaterialReconciliationRows } from '../../utils/materialReconciliationUtils';

jest.mock('../../utils/materialReconciliationUtils', () => ({
  buildEstimateMaterialPlanRows: jest.fn(() => []),
  buildMaterialAliasCandidates: jest.fn(() => []),
  buildMaterialControlSummary: jest.fn(() => ({ rows: [] })),
  buildMaterialReconciliationRows: jest.fn(() => [{ key: 'cement' }]),
}));

const createRuntime = (cache) => createMaterialRuntime({
  activeEstimatesForProject: () => [],
  canonicalCompanyName: '',
  companyRequisites: {},
  history: [],
  invoices: [],
  materialAliases: [],
  materialInspections: [],
  materialNormOverrides: [],
  materialNorms: [],
  materials: [],
  materialTransfers: [],
  parseSupplyItems: () => [],
  projects: [],
  supplyDeliveries: [],
  supplyHistory: [],
  supplyRequests: [],
  user: {},
  warehouseMain: [],
  warehouseMovements: [],
  workJournal: [],
  cache,
});

describe('material runtime cache', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    buildMaterialReconciliationRows.mockReturnValue([{ key: 'cement' }]);
    buildMaterialControlSummary.mockReturnValue({ rows: [] });
  });

  test('builds reconciliation rows once per project and package', () => {
    const runtime = createRuntime(createMaterialRuntimeCache());

    expect(runtime.materialReconciliationRows('Лицей 4')).toEqual([{ key: 'cement' }]);
    expect(runtime.materialReconciliationRows('Лицей 4')).toEqual([{ key: 'cement' }]);
    expect(runtime.materialReconciliationRows('Лицей 4', 'Электрика')).toEqual([{ key: 'cement' }]);

    expect(buildMaterialReconciliationRows).toHaveBeenCalledTimes(2);
  });

  test('reuses the project summary after rows are cached', () => {
    const runtime = createRuntime(createMaterialRuntimeCache());

    runtime.materialControlSummaryForProject('Лицей 4');
    runtime.materialControlSummaryForProject('Лицей 4');

    expect(buildMaterialReconciliationRows).toHaveBeenCalledTimes(1);
    expect(buildMaterialControlSummary).toHaveBeenCalledTimes(1);
  });
});
