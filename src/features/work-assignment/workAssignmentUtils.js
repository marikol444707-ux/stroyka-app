export function toNumber(value) {
  const parsed = Number(String(value ?? 0).replace(/\s/g, '').replace(',', '.'));
  return Number.isFinite(parsed) ? parsed : 0;
}

export function formatMoney(value) {
  return Math.round(toNumber(value)).toLocaleString('ru-RU') + ' ₽';
}

export function formatQty(value, unit) {
  const qty = toNumber(value);
  return qty.toLocaleString('ru-RU', {maximumFractionDigits: 3}) + ' ' + (unit || 'шт');
}

export function estimatePackageName(estimate) {
  return estimate?.workPackage || estimate?.work_package || 'Основная';
}

export function estimateProjectName(estimate) {
  return estimate?.projectName || estimate?.project_name || '';
}

export function estimateItemKeyForRow(estimate, sectionIndex, itemIndex, item) {
  return (
    item?.estimateItemKey ||
    item?.estimate_item_key ||
    item?.workKey ||
    item?.work_key ||
    item?.key ||
    item?.id ||
    (String(estimate?.id || '') + ':' + sectionIndex + ':' + itemIndex)
  );
}

export function isWorkItem(item) {
  const rawType = String(item?.itemType || item?.type || item?.kind || 'work').toLowerCase();
  if (['material', 'материал', 'materials', 'материалы', 'equipment', 'оборудование', 'delivery', 'доставка', 'other', 'прочее', 'note', 'adjustment'].some(type => rawType.includes(type))) return false;
  return !(toNumber(item?.priceMaterial) > 0 && toNumber(item?.priceWork) <= 0);
}

function itemTotal(item) {
  const storedTotal = toNumber(item?.totalWork || item?.lineTotal || item?.currentTotal || item?.total || item?.baseTotal || item?.estimatedCost || item?.workTotal || item?.workSum || item?.amount || item?.sum);
  return storedTotal || 0;
}

export function unitPrice(item) {
  const directPrice = toNumber(
    item?.customerPricePerUnit ||
    item?.priceWork ||
    item?.priceSmeta ||
    item?.price ||
    item?.baseUnitPrice
  );
  if (directPrice > 0) return directPrice;
  const qty = toNumber(item?.quantity);
  if (qty > 0) {
    const total = itemTotal(item);
    if (total) return total / qty;
  }
  return 0;
}

export function workRowsForEstimate(estimate) {
  const rows = [];
  const workPackage = estimatePackageName(estimate);
  (estimate?.sections || []).forEach((section, sectionIndex) => {
    (section.items || []).forEach((item, itemIndex) => {
      if (!isWorkItem(item)) return;
      const quantity = toNumber(item.quantity);
      const priceSmeta = unitPrice(item);
      if (quantity <= 0 || priceSmeta <= 0) return;
      const estimateItemKey = estimateItemKeyForRow(estimate, sectionIndex, itemIndex, item);
      rows.push({
        id: sectionIndex + '-' + itemIndex,
        sectionIndex,
        itemIndex,
        section: section.name || '',
        name: item.name || item.description || 'Работа',
        unit: item.unit || 'шт',
        quantity,
        doneQuantity: toNumber(item.doneQuantity),
        priceSmeta,
        estimateItemKey,
        workPackage,
      });
    });
  });
  return rows;
}

export function contractName(contract = {}) {
  return contract.brigadeName || contract.brigade_name || contract.masterName || contract.master_name || '';
}

export function contractById(contracts = []) {
  return Object.fromEntries((contracts || []).map(contract => [String(contract.id), contract]));
}

export function itemMatchesWorkRow(contractItem = {}, row = {}, estimate = {}) {
  const itemProject = String(contractItem.projectName || contractItem.project_name || '').trim();
  const sameProject = !itemProject || itemProject === estimateProjectName(estimate);
  const itemPackage = String(contractItem.workPackage || contractItem.work_package || '').trim();
  const samePackage = itemPackage && itemPackage === estimatePackageName(estimate);
  const contractKey = String(contractItem.estimateItemKey || contractItem.estimate_item_key || '').trim();
  const sameKey = contractKey && row.estimateItemKey && contractKey === String(row.estimateItemKey);
  const contractNameValue = String(contractItem.name || contractItem.description || '').trim().toLowerCase();
  const contractSection = String(contractItem.estimateSection || contractItem.estimate_section || '').trim().toLowerCase();
  const contractUnit = String(contractItem.unit || '').trim().toLowerCase();
  const sameName = contractNameValue &&
    contractNameValue === String(row.name || '').trim().toLowerCase() &&
    (!contractSection || contractSection === String(row.section || '').trim().toLowerCase()) &&
    (!contractUnit || contractUnit === String(row.unit || '').trim().toLowerCase());
  return sameProject && samePackage && (sameKey || sameName);
}

export function assignmentsForEstimate(estimate, contractItems = [], contracts = []) {
  const rows = workRowsForEstimate(estimate);
  const contractMap = contractById(contracts);
  return rows.map(row => {
    const assignments = (contractItems || [])
      .filter(item => itemMatchesWorkRow(item, row, estimate))
      .map(item => ({
        ...item,
        contract: contractMap[String(item.contractId || item.contract_id)] || {},
        doneQuantity: toNumber(item.doneQuantity || item.done_quantity),
        quantity: toNumber(item.quantity),
        priceBrigade: toNumber(item.priceBrigade || item.price_brigade),
      }));
    return {...row, assignments};
  });
}

export function workAssignmentStats(assignmentRows = []) {
  const assignedRows = assignmentRows.filter(row => row.assignments.length > 0);
  const unassignedRows = assignmentRows.filter(row => row.assignments.length === 0);
  const assignmentCount = assignmentRows.reduce((sum, row) => sum + row.assignments.length, 0);
  const duplicateRows = assignmentRows.filter(row => row.assignments.length > 1);
  const planAmount = assignmentRows.reduce((sum, row) => (
    sum + row.assignments.reduce((inner, item) => inner + toNumber(item.quantity) * toNumber(item.priceBrigade), 0)
  ), 0);
  const doneAmount = assignmentRows.reduce((sum, row) => (
    sum + row.assignments.reduce((inner, item) => inner + toNumber(item.doneQuantity) * toNumber(item.priceBrigade), 0)
  ), 0);
  return {
    totalRows: assignmentRows.length,
    assignedRows: assignedRows.length,
    unassignedRows: unassignedRows.length,
    assignmentCount,
    duplicateRows: duplicateRows.length,
    planAmount,
    doneAmount,
  };
}
