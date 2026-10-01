import {
  estimateImportedPlanMeasure,
  estimateMaterialPlanIssue,
  estimateSectionsOf,
  isEstimateMaterialItem,
  linkEstimateResourcesToWorks,
  normalizeEstimateWorkingItem,
} from './estimateUtils';
import { toNum } from './measureUtils';
import {
  buildM8DocContent,
  buildM29DocContent,
  buildMaterialRequirementDocContent,
} from './printDocumentBuilders';

export const parseJournalMaterialsValue = (value) => {
  if (!value) return [];
  if (Array.isArray(value)) return value;
  try {
    const parsed = JSON.parse(value);
    return Array.isArray(parsed) ? parsed : [];
  } catch (_) {
    return [];
  }
};

export const buildWorkMaterialSelectionRow = (material = {}, quantity = '') => ({
  name: material.name,
  sourcePreference: material.sourcePreference || 'auto',
  quantity,
  unit: material.unit || 'шт',
  workPackage: material.workPackage || '',
  autoNorm: !!material.autoNorm,
  normQuantity: material.normQuantity || '',
  normSource: material.normSource || '',
  normRuleId: material.normRuleId || material.ruleId || '',
  normThicknessMm: material.normThicknessMm || material.thicknessMm || '',
});

export const packageMatches = (candidatePackage = '', workPackage = '') => {
  const candidate = String(candidatePackage || '').trim();
  const required = String(workPackage || '').trim();
  if (!required) return true;
  return candidate === required;
};

export const buildWarehouseInvoiceItems = (
  invoice,
  {
    materials = [],
    warehouseMain = [],
    materialInspections = [],
    history = [],
  } = {},
) => {
  const direct = Array.isArray(invoice?.items) ? invoice.items.filter(item => (item?.name || '').trim()) : [];
  if (direct.length > 0) return { items: direct, reconstructed: false, source: '' };
  const norm = (value) => String(value || '').toLowerCase().replace(/[.,;:()«»"']/g, ' ').replace(/\s+/g, ' ').trim();
  const place = invoice?.location === 'Основной склад' ? 'Основной склад' : (invoice?.project || invoice?.location || '');
  const metaFor = (name, workPackage = '') => {
    const normalizedName = norm(name);
    const pkg = String(workPackage || '').trim();
    const projectItems = (materials || []).filter(material => material.project === place && (!pkg || String(material.workPackage || material.work_package || '').trim() === pkg));
    const pools = [...projectItems, ...(materials || []), ...(warehouseMain || [])];
    return pools.find(material => norm(material.name) === normalizedName)
      || pools.find(material => normalizedName && (norm(material.name).includes(normalizedName) || normalizedName.includes(norm(material.name))))
      || {};
  };
  const rowsFromInspections = (materialInspections || [])
    .filter(inspection => String(inspection.invoiceId || '') === String(invoice?.id || ''))
    .map(inspection => {
      const workPackage = inspection.workPackage || inspection.work_package || '';
      const meta = metaFor(inspection.materialName, workPackage);
      const price = Number(meta.price || 0);
      const qty = Number(inspection.quantity || 0);
      return {
        name: inspection.materialName || '',
        category: meta.category || '',
        quantity: qty,
        unit: inspection.unit || meta.unit || 'шт',
        price,
        total: qty * price,
        workPackage,
      };
    })
    .filter(item => item.name && item.quantity > 0);
  if (rowsFromInspections.length > 0) return { items: rowsFromInspections, reconstructed: true, source: 'журнала входного контроля' };

  const byName = {};
  const invoiceDate = String(invoice?.date || '').slice(0, 10);
  (history || [])
    .filter(row => String(row.date || '').slice(0, 10) === invoiceDate && (row.project || '') === place)
    .filter(row => String(row.type || '').toLowerCase().includes('приход') && !String(row.type || '').toLowerCase().includes('откат'))
    .forEach(row => {
      const workPackage = row.workPackage || row.work_package || '';
      const key = norm(row.material) + '|' + workPackage;
      if (!key) return;
      const meta = metaFor(row.material, workPackage);
      if (!byName[key]) byName[key] = { name: row.material || '', category: meta.category || '', quantity: 0, unit: meta.unit || 'шт', price: Number(meta.price || 0), total: 0, workPackage };
      byName[key].quantity += Number(row.quantity || 0);
      byName[key].total = byName[key].quantity * Number(byName[key].price || 0);
    });
  const rowsFromHistory = Object.values(byName).filter(item => item.name && item.quantity > 0);
  return { items: rowsFromHistory, reconstructed: rowsFromHistory.length > 0, source: 'истории склада' };
};

export const buildM8Rows = ({
  project,
  masterName = '',
  periodFrom = '',
  periodTo = '',
  materialTransfers = [],
  activeEstimates = [],
  legacyNameMatchAllowed = true,
} = {}) => {
  const projectName = typeof project === 'string' ? project : (project?.name || '');
  const projectId = Number(typeof project === 'object' ? project?.id : 0) || null;
  const inRange = date => !date ? false : (!periodFrom || date >= periodFrom) && (!periodTo || date <= periodTo);
  const matchesProject = transfer => {
    const frozenId = Number(transfer?.issuePartySnapshot?.project?.id || transfer?.projectId || 0) || null;
    return projectId && frozenId ? projectId === frozenId : legacyNameMatchAllowed && transfer.projectName === projectName;
  };
  const transfers = (materialTransfers || []).filter(transfer => (
    matchesProject(transfer)
    && (transfer.status || 'Активна') !== 'Аннулирована'
    && (!masterName || (transfer.receiptPartySnapshot?.receiver?.name || transfer.issuePartySnapshot?.intendedReceiver?.name || transfer.toPerson) === masterName)
    && inRange(transfer.transferDate || transfer.date)
  ));
  const byMaterial = {};

  transfers.forEach(transfer => {
    const material = transfer.issuePartySnapshot?.material || {};
    const name = material.name || transfer.materialName || '';
    const unit = material.unit || transfer.unit || '';
    const quantity = Number(material.quantity ?? transfer.quantity ?? 0);
    const key = name.trim().toLowerCase();
    if (!key) return;
    if (!byMaterial[key]) byMaterial[key] = { name, unit, limit: 0, issued: 0, accepted: 0, pending: 0, historical: 0 };
    byMaterial[key].issued += quantity;
    if (transfer.signed) byMaterial[key].accepted += quantity;
    else byMaterial[key].pending += quantity;
    if (!transfer.issuePartySnapshot) byMaterial[key].historical += quantity;
  });

  (activeEstimates || []).forEach(estimate => (
    linkEstimateResourcesToWorks(estimateSectionsOf(estimate)).forEach(section => (
      (section.items || []).forEach(rawItem => {
        const item = normalizeEstimateWorkingItem(rawItem, section.name);
        if (!isEstimateMaterialItem(item, section.name)) return;
        if (estimateMaterialPlanIssue(item, section.name)) return;
        const planMeasure = estimateImportedPlanMeasure(item);
        const limit = toNum(planMeasure.qty);
        if (limit <= 0) return;
        const key = (item.name || '').trim().toLowerCase();
        if (!key) return;
        if (!byMaterial[key]) byMaterial[key] = { name: item.name, unit: planMeasure.unit || item.unit || '', limit: 0, issued: 0, accepted: 0, pending: 0, historical: 0 };
        if (!byMaterial[key].unit && planMeasure.unit) byMaterial[key].unit = planMeasure.unit;
        byMaterial[key].limit += limit;
      })
    ))
  ));

  return Object.values(byMaterial).sort((a, b) => (b.issued / b.limit || 0) - (a.issued / a.limit || 0));
};

export const buildM29Rows = ({
  project,
  periodFrom = '',
  periodTo = '',
  activeEstimates = [],
  materialTransfers = [],
  workJournal = [],
  legacyNameMatchAllowed = true,
} = {}) => {
  const projectName = typeof project === 'string' ? project : (project?.name || '');
  const projectId = Number(typeof project === 'object' ? project?.id : 0) || null;
  const inRange = date => !date ? false : (!periodFrom || String(date).slice(0, 10) >= periodFrom) && (!periodTo || String(date).slice(0, 10) <= periodTo);
  const transferMatchesProject = transfer => {
    const frozenId = Number(transfer?.issuePartySnapshot?.project?.id || transfer?.projectId || 0) || null;
    return projectId && frozenId ? projectId === frozenId : legacyNameMatchAllowed && transfer.projectName === projectName;
  };
  const workMatchesProject = work => {
    const workProjectId = Number(work?.projectId || work?.project_id || 0) || null;
    return projectId && workProjectId ? projectId === workProjectId : legacyNameMatchAllowed && work.project === projectName;
  };
  const planByName = {};

  (activeEstimates || []).forEach(estimate => (
    estimateSectionsOf(estimate).forEach(section => (
      (section.items || []).forEach(item => {
        if (!isEstimateMaterialItem(item, section.name)) return;
        if (estimateMaterialPlanIssue(item, section.name)) return;
        const planMeasure = estimateImportedPlanMeasure(item);
        const planQty = toNum(planMeasure.qty);
        if (planQty <= 0) return;
        const key = (item.name || '').trim().toLowerCase();
        if (!key) return;
        if (!planByName[key]) planByName[key] = { name: item.name || '', unit: planMeasure.unit || item.unit || '', plan: 0, issued: 0, accepted: 0, pending: 0, fact: 0, historical: 0 };
        if (!planByName[key].unit && planMeasure.unit) planByName[key].unit = planMeasure.unit;
        planByName[key].plan += planQty;
      })
    ))
  ));

  (materialTransfers || []).filter(transfer => (
    transferMatchesProject(transfer)
    && (transfer.status || 'Активна') !== 'Аннулирована'
    && inRange(transfer.transferDate || transfer.date)
  )).forEach(transfer => {
    const material = transfer.issuePartySnapshot?.material || {};
    const name = material.name || transfer.materialName || '';
    const unit = material.unit || transfer.unit || '';
    const quantity = Number(material.quantity ?? transfer.quantity ?? 0);
    const key = name.trim().toLowerCase();
    if (!key) return;
    if (!planByName[key]) planByName[key] = { name, unit, plan: 0, issued: 0, accepted: 0, pending: 0, fact: 0, historical: 0 };
    planByName[key].issued += quantity;
    if (transfer.signed) planByName[key].accepted += quantity;
    else planByName[key].pending += quantity;
    if (!transfer.issuePartySnapshot) planByName[key].historical += quantity;
  });

  (workJournal || [])
    .filter(work => workMatchesProject(work) && !['Отклонено', 'Аннулировано'].includes(work.status) && inRange(work.date))
    .forEach(work => (
      parseJournalMaterialsValue(work.materialsUsed !== undefined ? work.materialsUsed : work.materials_used).forEach(material => {
        const key = (material.name || '').trim().toLowerCase();
        if (!key) return;
        if (!planByName[key]) planByName[key] = { name: material.name || '', unit: material.unit || '', plan: 0, issued: 0, accepted: 0, pending: 0, fact: 0, historical: 0 };
        planByName[key].fact += Number(material.quantity || 0);
      })
    ));

  return Object.values(planByName).sort((a, b) => (b.fact - b.plan) - (a.fact - a.plan));
};

export const buildM8ReportContent = ({
  project,
  masterName,
  periodFrom,
  periodTo,
  projects = [],
  materialTransfers = [],
  activeEstimatesForProject = () => [],
  printDocContext = {},
} = {}) => {
  const selectedProject = typeof project === 'object' ? project : ((projects || []).find(row => row.name === project) || {});
  const projectName = selectedProject.name || String(project || '');
  const legacyNameMatchAllowed = (projects || []).filter(row => row.name === projectName).length <= 1;
  const rows = buildM8Rows({
    project: selectedProject,
    masterName,
    periodFrom,
    periodTo,
    materialTransfers,
    activeEstimates: activeEstimatesForProject(selectedProject, 'Заказчик'),
    legacyNameMatchAllowed,
  });
  return buildM8DocContent({ projectName, masterName, periodFrom, periodTo, rows }, printDocContext);
};

export const buildMaterialRequirementReportContent = ({
  projectName,
  projects = [],
  activeEstimatesForProject = () => [],
  materialReconciliationRows = () => [],
  estimateWorkNormRequirementRows = () => [],
  materialNormControlSummaryForProject = () => ({}),
  printDocContext = {},
} = {}) => {
  const projectMatches = (projects || []).filter(row => row.name === projectName);
  const project = projectMatches.length === 1 ? projectMatches[0] : null;
  return buildMaterialRequirementDocContent({
    projectName,
    activeEstimates: activeEstimatesForProject(project, 'Заказчик'),
    rows: materialReconciliationRows(project),
    normRows: estimateWorkNormRequirementRows(project),
    normCtrl: materialNormControlSummaryForProject(projectName),
  }, printDocContext);
};

export const buildM29ReportContent = ({
  project,
  periodFrom,
  periodTo,
  projects = [],
  materialTransfers = [],
  workJournal = [],
  activeEstimatesForProject = () => [],
  printDocContext = {},
} = {}) => {
  const selectedProject = typeof project === 'object' ? project : ((projects || []).find(row => row.name === project) || {});
  const projectName = selectedProject.name || String(project || '');
  const legacyNameMatchAllowed = (projects || []).filter(row => row.name === projectName).length <= 1;
  const rows = buildM29Rows({
    project: selectedProject,
    periodFrom,
    periodTo,
    activeEstimates: activeEstimatesForProject(selectedProject, 'Заказчик'),
    materialTransfers,
    workJournal,
    legacyNameMatchAllowed,
  });
  return buildM29DocContent({ projectName, periodFrom, periodTo, rows }, printDocContext);
};
