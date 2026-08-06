import { workRowsForEstimate } from '../work-assignment/workAssignmentUtils';

export function getDistributableWorkRows(estimate) {
  return workRowsForEstimate(estimate).map(row => ({...row, key: row.id}));
}

export function buildEstimateDistributionAssignments(workRows, selectedAssignments, brigades) {
  const assignments = [];
  workRows.forEach(({
    sectionIndex,
    itemIndex,
    key,
    workPackage,
    estimateItemKey,
    section,
    name,
    unit,
    quantity,
    priceSmeta,
  }) => {
    const brigadeName = selectedAssignments[key];
    if (!brigadeName) return;
    const brigade = brigades.find(candidate => candidate.name === brigadeName);
    assignments.push({
      sectionIndex,
      itemIndex,
      estimateItemKey,
      section,
      name,
      unit,
      quantity,
      priceSmeta,
      itemType: 'work',
      workPackage,
      brigadeName,
      contractorType: brigade?.contractorType || 'Своя бригада',
      contractorId: brigade?.contractorId || null,
      pricelistId: brigade?.pricelistId || null,
    });
  });
  return assignments;
}
