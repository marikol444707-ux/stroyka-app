import {
  buildEstimateMaterialPlanRows,
  buildMaterialAliasCandidates,
  buildMaterialControlSummary,
  buildMaterialReconciliationRows,
} from '../../utils/materialReconciliationUtils';
import { buildWarehouseInvoiceEstimateControl } from '../../utils/warehouseInvoiceControlUtils';
import {
  buildEstimateNormCoverageRows,
  buildEstimateWorkNormRequirementRows,
  buildMaterialAvailabilityMap,
  buildMaterialNormControlSummary,
  buildMaterialNormDeviationRows,
  buildMaterialSuggestionsForWork,
  buildPersonalMaterialRowsForProject,
} from '../../utils/materialNormSelectors';
import { materialLookupText } from '../../utils/materialMatchUtils';
import {
  WORK_MATERIAL_NORM_RULES,
  calculateMaterialNormForWork,
  calculateNormRequirementsForWork,
  materialNormCoverageComment,
  materialTitleForNormRule,
  workNormRulesForCalculation,
} from '../../utils/materialNormUtils';
import {
  buildWarehouseInvoiceItems,
  packageMatches,
  parseJournalMaterialsValue,
} from '../../utils/materialDocumentUtils';
import { buildMaterialNormCoverageDocContent } from '../../utils/printDocumentBuilders';
import { toNum } from '../../utils/measureUtils';
import {
  immutableStoredProjectOwner,
  uniqueStoredProjectForName,
} from '../estimates/projectEstimateOwnership';

const ownerCacheKey = (owner, workPackage = '') => (
  `${owner.companyId}\u0000${owner.projectId}\u0000${String(workPackage || '').trim()}`
);

export function createMaterialRuntimeCache(sourceSnapshot = []) {
  return {
    sourceSnapshot,
    reconciliationRows: new Map(),
    controlSummaries: new Map(),
  };
}

export function createMaterialRuntime({
  activeEstimatesForProject,
  canonicalCompanyName,
  companyRequisites,
  estimateWorkNormRequirementRows: externalEstimateWorkNormRequirementRows,
  history,
  invoices,
  materialAliases,
  materialInspections,
  materialNormOverrides,
  materialNorms,
  materials,
  materialTransfers,
  parseSupplyItems,
  projects,
  supplyDeliveries,
  supplyHistory,
  supplyRequests,
  user,
  warehouseMain,
  warehouseMovements,
  workJournal,
  cache = null,
}) {
  const materialControlOwner = (projectOrOwner) => immutableStoredProjectOwner(projectOrOwner);
  const materialControlProjectForName = (projectName) => {
    const project = uniqueStoredProjectForName(projects, projectName);
    return immutableStoredProjectOwner(project);
  };

  const warehouseInvoiceItems = (inv) => buildWarehouseInvoiceItems(inv, {
    materials,
    warehouseMain,
    materialInspections,
    history,
  });

  const isSupplyDeliveryInvoice = (inv) => !!(inv?.supplyDeliveryId || inv?.sourceType === 'supply_delivery');
  const materialNameLookupKey = materialLookupText;

  const materialAliasFor = (projectName, aliasName) => {
    const key = materialNameLookupKey(aliasName);
    if (!key) return null;
    const active = (materialAliases || []).filter(a => a && a.active !== false && materialNameLookupKey(a.aliasName) === key);
    return active.find(a => (a.projectName || '') === projectName) || active.find(a => !(a.projectName || '')) || null;
  };

  const canonicalMaterialMeta = (projectName, name, unit = '') => {
    const alias = materialAliasFor(projectName, name);
    return {
      name: alias?.canonicalName || name || '',
      unit: alias?.canonicalUnit || unit || '',
      alias,
    };
  };

  const estimateMaterialPlanRows = (projectOrOwner) => {
    const project = materialControlOwner(projectOrOwner);
    if (!project) return [];
    return buildEstimateMaterialPlanRows({
      project,
      activeEstimatesForProject,
      materialNameLookupKey,
    });
  };

  const materialAliasCandidates = (projectOrOwner, row) => buildMaterialAliasCandidates({
    project: materialControlOwner(projectOrOwner),
    row,
    estimateMaterialPlanRows,
    materialNameLookupKey,
  });

  const estimateWorkNormRequirementRows = externalEstimateWorkNormRequirementRows || ((projectOrOwner, workPackage = '') => {
    const project = materialControlOwner(projectOrOwner);
    if (!project) return [];
    return buildEstimateWorkNormRequirementRows({
      project,
      workPackage,
      activeEstimatesForProject,
      normRequirementsForWork,
      materialNameKey,
    });
  });

  const materialReconciliationRows = (projectOrOwner, workPackage = '') => {
    const project = materialControlOwner(projectOrOwner);
    if (!project) return [];
    const key = ownerCacheKey(project, workPackage);
    if (cache?.reconciliationRows?.has(key)) return cache.reconciliationRows.get(key);
    const rows = buildMaterialReconciliationRows({
      project,
      workPackage,
      invoices,
      supplyDeliveries,
      supplyHistory,
      warehouseMovements,
      materialTransfers,
      workJournal,
      history,
      materials,
      supplyRequests,
      activeEstimatesForProject,
      canonicalMaterialMeta,
      warehouseInvoiceItems,
      isSupplyDeliveryInvoice,
      estimateWorkNormRequirementRows,
      parseSupplyItems,
      materialNameLookupKey,
    });
    cache?.reconciliationRows?.set(key, rows);
    return rows;
  };

  const materialControlSummaryForProject = (projectOrOwner) => {
    const project = materialControlOwner(projectOrOwner);
    if (!project) return buildMaterialControlSummary([]);
    const key = ownerCacheKey(project);
    if (cache?.controlSummaries?.has(key)) return cache.controlSummaries.get(key);
    const summary = buildMaterialControlSummary(materialReconciliationRows(project));
    cache?.controlSummaries?.set(key, summary);
    return summary;
  };

  const warehouseInvoiceEstimateControl = (inv) => buildWarehouseInvoiceEstimateControl({
    inv,
    warehouseInvoiceItems,
    materialControlProjectForName,
    materialControlSummaryForProject,
    canonicalMaterialMeta,
    materialNameLookupKey,
  });

  const materialNameKey = materialNameLookupKey;
  const isPersonalMaterialRole = () => ['мастер', 'субподрядчик', 'бригадир'].includes(user?.role);
  const parseJournalMaterials = (value) => parseJournalMaterialsValue(value);

  const materialNormDeviationRows = (projectName, workPackage = '') => buildMaterialNormDeviationRows({
    projectName,
    workPackage,
    workJournal,
    parseJournalMaterials,
    materialNameKey,
  });

  const materialNormControlSummaryForProject = (projectName, workPackage = '') =>
    buildMaterialNormControlSummary(materialNormDeviationRows(projectName, workPackage));

  const personalMaterialRowsForProject = (projectName, personName = user?.name, personId = user?.id, workPackage = '') =>
    buildPersonalMaterialRowsForProject({
      projectName,
      personName,
      personId,
      workPackage,
      materialTransfers,
      workJournal,
      history,
      canonicalMaterialMeta,
      parseJournalMaterials,
      materialNameKey,
    });

  const materialRowsAvailableForWork = (projectName, workPackage = '') => {
    if (isPersonalMaterialRole()) return personalMaterialRowsForProject(projectName, user?.name, user?.id, workPackage).filter(r => toNum(r.quantity) > 0);
    return (materials || []).filter(m => m.project === projectName && toNum(m.quantity) > 0 && packageMatches(m.workPackage || m.work_package, workPackage));
  };

  const materialAvailabilityMapForWork = (projectName, workPackage = '') => buildMaterialAvailabilityMap({
    rows: materialRowsAvailableForWork(projectName, workPackage),
    projectName,
    canonicalMaterialMeta,
    materialNameKey,
  });

  const materialHintForProject = (projectOrOwner, materialName, workPackage = '') => {
    const project = materialControlOwner(projectOrOwner);
    if (!project) return null;
    const projectName = project.projectName;
    const meta = canonicalMaterialMeta(projectName, materialName);
    const key = materialNameKey(meta.name);
    if (!key) return null;
    return materialReconciliationRows(project, workPackage).find(r => materialNameKey(r.name) === key) || null;
  };

  const materialSuggestionsForWork = (projectOrOwner, workName, sectionName = '', workPackage = '') => {
    const project = materialControlOwner(projectOrOwner);
    if (!project) return [];
    return buildMaterialSuggestionsForWork({
      project,
      workName,
      sectionName,
      workPackage,
      materialReconciliationRows,
      materialNameKey,
    });
  };

  const workNormRulesFor = (workName, sectionName = '', projectName = '', estimateId = null) => {
    return workNormRulesForCalculation({
      workName,
      sectionName,
      projectName,
      estimateId,
      materialNorms,
      materialNormOverrides,
      baseRules: WORK_MATERIAL_NORM_RULES,
    });
  };

  const workNeedsThicknessParam = (workName, sectionName = '') =>
    workNormRulesFor(workName, sectionName).some(r => r.thicknessBaseMm);

  const materialNormForWork = (projectName, workName, sectionName, workQty, workUnit, material, params = {}) => {
    return calculateMaterialNormForWork({
      projectName,
      workName,
      sectionName,
      workQty,
      workUnit,
      material,
      params,
      materialNorms,
      materialNormOverrides,
      baseRules: WORK_MATERIAL_NORM_RULES,
    });
  };

  const normRequirementsForWork = (workName, sectionName, workQty, workUnit, params = {}) => {
    return calculateNormRequirementsForWork({
      workName,
      sectionName,
      workQty,
      workUnit,
      params,
      materialNorms,
      materialNormOverrides,
      baseRules: WORK_MATERIAL_NORM_RULES,
    });
  };

  const estimateNormCoverageRows = (projectName, sourceEstimates = null) => buildEstimateNormCoverageRows({
    projectName,
    sourceEstimates,
    projects,
    activeEstimatesForProject,
    workNormRulesFor,
    normRequirementsForWork,
    materialNameKey,
  });

  const buildMaterialNormCoverageContent = (projectName) => buildMaterialNormCoverageDocContent(
    projectName,
    projectName ? estimateNormCoverageRows(projectName) : [],
    { companyRequisites, companyName: canonicalCompanyName, materialTitleForNormRule, materialNormCoverageComment },
  );

  return {
    buildMaterialNormCoverageContent,
    canonicalMaterialMeta,
    estimateMaterialPlanRows,
    estimateNormCoverageRows,
    estimateWorkNormRequirementRows,
    isPersonalMaterialRole,
    isSupplyDeliveryInvoice,
    materialAliasCandidates,
    materialAliasFor,
    materialAvailabilityMapForWork,
    materialControlSummaryForProject,
    materialHintForProject,
    materialNameKey,
    materialNameLookupKey,
    materialNormControlSummaryForProject,
    materialNormDeviationRows,
    materialNormForWork,
    materialReconciliationRows,
    materialRowsAvailableForWork,
    materialSuggestionsForWork,
    normRequirementsForWork,
    parseJournalMaterials,
    personalMaterialRowsForProject,
    warehouseInvoiceEstimateControl,
    warehouseInvoiceItems,
    workNeedsThicknessParam,
    workNormRulesFor,
  };
}
