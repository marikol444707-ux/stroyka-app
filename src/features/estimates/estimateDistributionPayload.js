export function isDistributableWorkItem(item) {
  const rawType = String(item?.itemType || item?.type || item?.kind || 'work').toLowerCase();
  const priceWork = Number(item?.priceWork || 0);
  const priceMaterial = Number(item?.priceMaterial || 0);
  const excludedTypes = [
    'material', 'материал', 'materials', 'материалы', 'equipment', 'оборудование',
    'delivery', 'доставка', 'other', 'прочее',
  ];
  if (excludedTypes.some(token => rawType.includes(token))) return false;
  return !(priceWork <= 0 && priceMaterial > 0);
}

export function getDistributableWorkRows(estimate) {
  const rows = [];
  const workPackage = estimate?.workPackage || estimate?.work_package || 'Основная';
  (estimate?.sections || []).forEach((section, sectionIndex) => {
    (section.items || []).forEach((item, itemIndex) => {
      if (!isDistributableWorkItem(item)) return;
      rows.push({
        section,
        sectionIndex,
        item,
        itemIndex,
        key: sectionIndex + '-' + itemIndex,
        workPackage,
        estimateItemKey: item.estimateItemKey
          || item.estimate_item_key
          || (String(estimate.id || '') + ':' + sectionIndex + ':' + itemIndex),
      });
    });
  });
  return rows;
}

export function buildEstimateDistributionAssignments(workRows, selectedAssignments, brigades) {
  const assignments = [];
  workRows.forEach(({
    section,
    sectionIndex,
    item,
    itemIndex,
    key,
    workPackage,
    estimateItemKey,
  }) => {
    const brigadeName = selectedAssignments[key];
    if (!brigadeName) return;
    const brigade = brigades.find(candidate => candidate.name === brigadeName);
    assignments.push({
      sectionIndex,
      itemIndex,
      estimateItemKey,
      section: section.name,
      name: item.name,
      unit: item.unit || 'шт',
      quantity: Number(item.quantity || 0),
      priceSmeta: Number(item.priceWork || 0),
      itemType: item.type || item.itemType || 'work',
      workPackage,
      brigadeName,
      contractorType: brigade?.contractorType || 'Своя бригада',
      contractorId: brigade?.contractorId || null,
      pricelistId: brigade?.pricelistId || null,
    });
  });
  return assignments;
}
