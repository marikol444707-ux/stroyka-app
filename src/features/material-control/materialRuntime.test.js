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

const createRuntime = (cache, overrides = {}) => createMaterialRuntime({
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
  ...overrides,
});

test.each(['1', '0'])('director availability exposes warehouse sources only under accounting flag=%s', flag => {
  const previous = process.env.REACT_APP_WORK_MATERIAL_ACCOUNTING_ENABLED;
  process.env.REACT_APP_WORK_MATERIAL_ACCOUNTING_ENABLED = flag;
  try {
    const runtime = createRuntime(createMaterialRuntimeCache(), {
      companyContext: { mode: 'company', selectedCompanyId: 1 }, materialAliasesError: '',
      projects: [firstProject], user: { id: 7, name: 'Директор', role: 'директор' },
      materials: [{ id: 41, name: 'Цемент', unit: 'кг', quantity: 3, project: 'Школа', workPackage: 'Основная' }],
      materialTransfers: [
        { id: 71, toUserId: 7, toPerson: 'Директор', signed: true, projectName: 'Школа',
          materialName: 'Цемент', unit: 'кг', quantity: 6, workPackage: 'Основная' },
        { id: 72, toUserId: 8, toPerson: 'Мастер', signed: true, projectName: 'Школа',
          materialName: 'Цемент', unit: 'кг', quantity: 8, workPackage: 'Основная' },
      ],
    });
    // Prove the personal fixture is valid, then verify it is not a source for
    // a director's work submission, even when its recipient is the same user.
    expect(runtime.personalMaterialRowsForProject('Школа', 'Директор', 7, 'Основная'))
      .toEqual([expect.objectContaining({ name: 'Цемент', quantity: 6 })]);
    const available = Object.values(runtime.materialAvailabilityMapForWork('Школа', 'Основная'));
    expect(available).toHaveLength(1);
    expect(available[0]).toMatchObject({ name: 'Цемент', unit: 'кг', quantity: 3 });
    if (flag === '1') {
      expect(available[0]).toMatchObject({ materialAccountingVersion: 2, personalAvailable: 0,
        warehouseAvailable: 3, warehouseMaterialId: 41, sourceConflict: false });
    } else {
      expect(available[0].materialAccountingVersion).toBeUndefined();
      expect(available[0].warehouseAvailable).toBeUndefined();
      expect(available[0].warehouseMaterialId).toBeUndefined();
    }
  } finally {
    if (previous === undefined) delete process.env.REACT_APP_WORK_MATERIAL_ACCOUNTING_ENABLED;
    else process.env.REACT_APP_WORK_MATERIAL_ACCOUNTING_ENABLED = previous;
  }
});

test('owned snapshot failure blocks cached reconciliation and marks invoice control unavailable', () => {
  const previous = process.env.REACT_APP_COMPANY_MATERIAL_ALIASES_ENABLED;
  process.env.REACT_APP_COMPANY_MATERIAL_ALIASES_ENABLED = '1';
  try {
    const cache = createMaterialRuntimeCache();
    const companyContext = {mode: 'company', selectedCompanyId: 1};
    const ready = createRuntime(cache, {companyContext, materialAliasesError: ''});
    ready.materialReconciliationRows(firstProject);
    const failed = createRuntime(cache, {companyContext, materialAliasesError: 'Нет соединения'});
    expect(failed.materialReconciliationRows(firstProject)).toEqual([]);
    expect(failed.materialControlSummaryForProject(firstProject)).toMatchObject({unavailable: true, error: 'Нет соединения'});
    expect(ready.materialReconciliationRows(secondProject)).toEqual([]);
  } finally {
    if (previous === undefined) delete process.env.REACT_APP_COMPANY_MATERIAL_ALIASES_ENABLED;
    else process.env.REACT_APP_COMPANY_MATERIAL_ALIASES_ENABLED = previous;
  }
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
