import {
  estimateImportedPlanMeasure,
  estimateMaterialPlanIssue,
  estimateSectionsOf,
  isEstimateMaterialItem,
  linkEstimateResourcesToWorks,
  normalizeEstimateWorkingItem,
} from './estimateUtils';
import { toNum } from './measureUtils';

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
  projectName,
  masterName = '',
  periodFrom = '',
  periodTo = '',
  materialTransfers = [],
  activeEstimates = [],
} = {}) => {
  const inRange = date => !date ? false : (!periodFrom || date >= periodFrom) && (!periodTo || date <= periodTo);
  const transfers = (materialTransfers || []).filter(transfer => (
    transfer.projectName === projectName
    && (!masterName || transfer.toPerson === masterName)
    && inRange(transfer.transferDate || transfer.date)
  ));
  const byMaterial = {};

  transfers.forEach(transfer => {
    const key = (transfer.materialName || '').trim().toLowerCase();
    if (!key) return;
    if (!byMaterial[key]) byMaterial[key] = { name: transfer.materialName, unit: transfer.unit || '', limit: 0, issued: 0 };
    byMaterial[key].issued += Number(transfer.quantity || 0);
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
        if (!byMaterial[key]) byMaterial[key] = { name: item.name, unit: planMeasure.unit || item.unit || '', limit: 0, issued: 0 };
        if (!byMaterial[key].unit && planMeasure.unit) byMaterial[key].unit = planMeasure.unit;
        byMaterial[key].limit += limit;
      })
    ))
  ));

  return Object.values(byMaterial).sort((a, b) => (b.issued / b.limit || 0) - (a.issued / a.limit || 0));
};

export const buildM29Rows = ({
  projectName,
  periodFrom = '',
  periodTo = '',
  activeEstimates = [],
  materialTransfers = [],
  workJournal = [],
} = {}) => {
  const inRange = date => !date ? false : (!periodFrom || String(date).slice(0, 10) >= periodFrom) && (!periodTo || String(date).slice(0, 10) <= periodTo);
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
        if (!planByName[key]) planByName[key] = { name: item.name || '', unit: planMeasure.unit || item.unit || '', plan: 0, issued: 0, fact: 0 };
        if (!planByName[key].unit && planMeasure.unit) planByName[key].unit = planMeasure.unit;
        planByName[key].plan += planQty;
      })
    ))
  ));

  (materialTransfers || []).filter(transfer => transfer.projectName === projectName && inRange(transfer.transferDate || transfer.date)).forEach(transfer => {
    const key = (transfer.materialName || '').trim().toLowerCase();
    if (!key) return;
    if (!planByName[key]) planByName[key] = { name: transfer.materialName || '', unit: transfer.unit || '', plan: 0, issued: 0, fact: 0 };
    planByName[key].issued += Number(transfer.quantity || 0);
  });

  (workJournal || [])
    .filter(work => work.project === projectName && work.status !== 'Отклонено' && inRange(work.date))
    .forEach(work => (
      parseJournalMaterialsValue(work.materialsUsed !== undefined ? work.materialsUsed : work.materials_used).forEach(material => {
        const key = (material.name || '').trim().toLowerCase();
        if (!key) return;
        if (!planByName[key]) planByName[key] = { name: material.name || '', unit: material.unit || '', plan: 0, issued: 0, fact: 0 };
        planByName[key].fact += Number(material.quantity || 0);
      })
    ));

  return Object.values(planByName).sort((a, b) => (b.fact - b.plan) - (a.fact - a.plan));
};
