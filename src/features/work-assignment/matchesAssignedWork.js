const text = value => String(value || '').trim();
const folded = value => text(value).toLowerCase();

export function matchesAssignedWork(contractItem, {projectName, itemKey, itemName, sectionName, itemUnit}) {
  const contractKey = text(contractItem.estimateItemKey || contractItem.estimate_item_key);
  const contractName = folded(contractItem.name || contractItem.description);
  const contractUnit = folded(contractItem.unit);
  const contractSection = folded(contractItem.estimateSection || contractItem.estimate_section);
  const contractProject = text(contractItem.projectName || contractItem.project_name);
  const sameProject = !contractProject || contractProject === projectName;
  const sameKey = itemKey && contractKey && contractKey === itemKey;
  const sameName = contractName && contractName === itemName
    && (!contractSection || !sectionName || contractSection === sectionName)
    && (!itemUnit || !contractUnit || contractUnit === itemUnit);
  // A matching label must not override two different stored row identities.
  return Boolean(sameProject && (itemKey && contractKey ? sameKey : sameName));
}
