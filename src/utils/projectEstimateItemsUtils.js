import {
  estimateItemDoneTotal,
  estimateItemTotal,
  estimatePackage,
  estimateSectionsOf,
  isEstimateWorkItem,
} from './estimateUtils';

export const projectPlanDoneFor = (activeEstimates = []) => {
  if (!activeEstimates.length) return {plan: 0, done: 0};
  let plan = 0;
  let done = 0;
  activeEstimates.forEach(est => estimateSectionsOf(est).forEach(section => (section.items || []).forEach(item => {
    plan += estimateItemTotal(item);
    done += estimateItemDoneTotal(item);
  })));
  return {plan, done};
};

export const ks2ItemsFromActiveEstimates = ({ project = {}, activeEstimates = [], workJournal = [] } = {}) => {
  if (activeEstimates.length === 0) return [];
  const itemByKey = {};
  const fallbackByName = {};

  activeEstimates.forEach(est => estimateSectionsOf(est).forEach((section, sectionIdx) => (section.items || []).forEach((item, itemIdx) => {
    if (!isEstimateWorkItem(item, section.name)) return;
    const pkg = estimatePackage(est);
    const key = [est.id, sectionIdx, itemIdx].join(':');
    const row = {
      section: (pkg && pkg !== 'Основная' ? pkg + ' / ' : '') + (section.name || ''),
      workPackage: pkg,
      description: item.name || '',
      unit: item.unit || '',
      pricePerUnit: Number(estimateItemTotal(item)) / Math.max(1, Number(item.quantity || 0)),
      item,
    };
    itemByKey[key] = row;
    fallbackByName[(pkg || '') + '|' + (section.name || '') + '|' + (item.name || '')] = row;
    const nameKey = (item.name || '').trim().toLowerCase();
    fallbackByName[nameKey] = fallbackByName[nameKey] || row;
  })));

  const linkedJournal = (workJournal || []).filter(j => j.project === project.name && !j.unexpectedWorkId && j.estimateItemKey);
  if (linkedJournal.length > 0) {
    const grouped = {};
    linkedJournal.filter(j => j.status === 'Подтверждено').forEach(j => {
      const meta = itemByKey[j.estimateItemKey] ||
        fallbackByName[(j.workPackage || '') + '|' + (j.sectionName || '') + '|' + (j.estimateItemName || j.description || '')] ||
        fallbackByName[(j.estimateItemName || j.description || '').trim().toLowerCase()];
      if (!meta) return;
      const key = j.estimateItemKey || (meta.section + '|' + meta.description);
      if (!grouped[key]) grouped[key] = {...meta, quantity: 0, total: 0};
      const qty = Number(j.quantity || 0);
      grouped[key].quantity += qty;
      grouped[key].total += Number(j.customerTotal || 0) || qty * Number(meta.pricePerUnit || 0);
    });
    return Object.values(grouped)
      .map(r => ({...r, total: Math.round(r.total)}))
      .filter(r => Number(r.quantity || 0) > 0);
  }

  const rows = [];
  activeEstimates.forEach(est => estimateSectionsOf(est).forEach(section => (section.items || []).forEach(item => {
    if (!isEstimateWorkItem(item, section.name)) return;
    const quantity = Number(item.doneQuantity || 0);
    if (quantity <= 0) return;
    const total = estimateItemDoneTotal(item);
    const price = quantity > 0 ? total / quantity : 0;
    const pkg = estimatePackage(est);
    rows.push({
      section: (pkg && pkg !== 'Основная' ? pkg + ' / ' : '') + (section.name || ''),
      workPackage: pkg,
      description: item.name || '',
      unit: item.unit || '',
      quantity,
      pricePerUnit: price,
      total: Math.round(total),
    });
  })));
  return rows;
};

export const estimateItemOptionsFromActiveEstimates = (activeEstimates = []) => {
  if (activeEstimates.length === 0) return [];
  const rows = [];
  activeEstimates.forEach(est => estimateSectionsOf(est).forEach((section, sectionIdx) => (section.items || []).forEach((item, itemIdx) => {
    if (!isEstimateWorkItem(item, section.name)) return;
    rows.push({
      key: [est.id, sectionIdx, itemIdx].join(':'),
      estimateId: est.id,
      workPackage: estimatePackage(est),
      sectionName: section.name || '',
      name: item.name || '',
      unit: item.unit || 'шт',
      quantity: Number(item.quantity || 0),
      pricePerUnit: Number(item.priceWork || 0) + Number(item.priceMaterial || 0),
      total: estimateItemTotal(item),
    });
  })));
  return rows;
};
