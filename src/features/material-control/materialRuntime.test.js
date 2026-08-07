import { createMaterialRuntime, createMaterialRuntimeCache } from './materialRuntime';
import {
  buildEstimateMaterialPlanRows,
  buildMaterialControlSummary,
  buildMaterialReconciliationRows,
} from '../../utils/materialReconciliationUtils';

jest.mock('../../utils/materialReconciliationUtils', () => ({
  buildEstimateMaterialPlanRows: jest.fn(() => []),
  buildMaterialAliasCandidates: jest.fn(() => []),
  buildMaterialControlSummary: jest.fn(() => ({ rows: [] })),
  buildMaterialReconciliationRows: jest.fn(() => [{ key: 'cement' }]),
}));

const firstProject = { id: 11, companyId: 1, name: 'Школа' };
const secondProject = { id: 22, companyId: 2, name: 'Школа' };

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
  projects: [firstProject, secondProject],
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

  test('builds reconciliation rows once per exact owner and package', () => {
    const cache = createMaterialRuntimeCache();
    const runtime = createRuntime(cache);

    expect(runtime.materialReconciliationRows(firstProject)).toEqual([{ key: 'cement' }]);
    expect(runtime.materialReconciliationRows(firstProject)).toEqual([{ key: 'cement' }]);
    expect(runtime.materialReconciliationRows(secondProject)).toEqual([{ key: 'cement' }]);
    expect(runtime.materialReconciliationRows(firstProject, 'Электрика')).toEqual([{ key: 'cement' }]);

    expect(buildMaterialReconciliationRows).toHaveBeenCalledTimes(3);
    expect(buildMaterialReconciliationRows.mock.calls.map(([args]) => args.project)).toEqual([
      { companyId: 1, projectId: 11, projectName: 'Школа' },
      { companyId: 2, projectId: 22, projectName: 'Школа' },
      { companyId: 1, projectId: 11, projectName: 'Школа' },
    ]);
    expect([...cache.reconciliationRows.keys()]).toEqual([
      '1\u000011\u0000',
      '2\u000022\u0000',
      '1\u000011\u0000Электрика',
    ]);
  });

  test('passes the exact immutable owner into the material plan builder', () => {
    const runtime = createRuntime(createMaterialRuntimeCache());

    runtime.estimateMaterialPlanRows(firstProject);
    runtime.estimateMaterialPlanRows(secondProject);

    expect(buildEstimateMaterialPlanRows.mock.calls.map(([args]) => args.project)).toEqual([
      { companyId: 1, projectId: 11, projectName: 'Школа' },
      { companyId: 2, projectId: 22, projectName: 'Школа' },
    ]);
    buildEstimateMaterialPlanRows.mock.calls.forEach(([args]) => {
      expect(Object.isFrozen(args.project)).toBe(true);
    });
  });

  test('keeps summaries for same-name owners isolated', () => {
    const runtime = createRuntime(createMaterialRuntimeCache());

    runtime.materialControlSummaryForProject(firstProject);
    runtime.materialControlSummaryForProject(firstProject);
    runtime.materialControlSummaryForProject(secondProject);

    expect(buildMaterialReconciliationRows).toHaveBeenCalledTimes(2);
    expect(buildMaterialControlSummary).toHaveBeenCalledTimes(2);
  });

  test('fails closed for a name-only scope', () => {
    const runtime = createRuntime(createMaterialRuntimeCache());

    expect(runtime.materialReconciliationRows('Школа')).toEqual([]);
    expect(buildMaterialReconciliationRows).not.toHaveBeenCalled();
  });
});
