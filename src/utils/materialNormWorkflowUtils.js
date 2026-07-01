import { toNum } from './measureUtils';
import {
  materialNormSupplyMarker,
  materialNormSupplyNotes,
  materialTitleForNormRule,
  normListFromText,
} from './materialNormUtils';
import { materialLookupText } from './materialMatchUtils';

export const materialNormSupplyRequestExistsForRow = ({
  row,
  supplyRequests = [],
  isActiveSupplyRequestStatus,
}) => {
  const marker = materialNormSupplyMarker(row);
  return (supplyRequests || []).some(request =>
    request.project === row?.projectName &&
    isActiveSupplyRequestStatus(request.status) &&
    String(request.notes || '').includes(marker),
  );
};

export const buildMaterialNormSupplyRequestPayload = ({
  row,
  materialName,
  quantity,
  user,
}) => {
  const unit = row.requiredUnit || row.rule.materialUnit || row.materialUnit || 'шт';
  const rowPackage = row.packageName || row.workPackage || '';
  const requestRow = { ...row, materialName, requiredQty: quantity, requiredUnit: unit };
  return {
    materialName,
    quantity,
    unit,
    workPackage: rowPackage,
    items: [{ materialName, quantity, unit, workPackage: rowPackage }],
    project: row.projectName,
    createdBy: user?.name || '',
    date: new Date().toISOString().split('T')[0],
    notes: materialNormSupplyNotes([requestRow]),
    category: row.packageName || row.sectionName || '',
    urgency: 'обычная',
    requestedByRole: user?.role || '',
    requestedById: user?.id || null,
    selectedSuppliers: [],
  };
};

export const buildBatchMaterialNormSupplyRequestPayloads = ({
  rows = [],
  user,
  materialNameKey = materialLookupText,
}) => {
  const byKey = {};
  rows.forEach(row => {
    const materialName = row.materialName || materialTitleForNormRule(row.rule) || 'Материал';
    const unit = row.requiredUnit || row.rule?.materialUnit || row.materialUnit || 'шт';
    const workPackage = row.packageName || row.workPackage || '';
    const key = materialNameKey(materialName) + '|' + unit + '|' + workPackage;
    if (!byKey[key]) byKey[key] = { materialName, quantity: 0, unit, workPackage };
    byKey[key].quantity += toNum(row.shortageQty || row.requiredQty);
  });
  const items = Object.values(byKey).map(item => ({
    ...item,
    workPackage: item.workPackage || 'Основная',
    quantity: Number(item.quantity.toFixed(4)),
  }));
  const rowsByPackage = rows.reduce((acc, row) => {
    const pkg = String(row.packageName || row.workPackage || 'Основная').trim() || 'Основная';
    if (!acc[pkg]) acc[pkg] = [];
    acc[pkg].push(row);
    return acc;
  }, {});
  const itemsByPackage = items.reduce((acc, item) => {
    const pkg = String(item.workPackage || 'Основная').trim() || 'Основная';
    if (!acc[pkg]) acc[pkg] = [];
    acc[pkg].push(item);
    return acc;
  }, {});

  return Object.entries(itemsByPackage).map(([requestPackage, packageItems]) => ({
    requestPackage,
    items: packageItems,
    payload: {
      materialName: packageItems[0].materialName,
      quantity: packageItems[0].quantity,
      unit: packageItems[0].unit,
      workPackage: requestPackage,
      items: packageItems,
      project: rows[0]?.projectName,
      createdBy: user?.name || '',
      date: new Date().toISOString().split('T')[0],
      notes: materialNormSupplyNotes(
        rowsByPackage[requestPackage] || [],
        'Пакетная заявка из ведомости «Вся смета по нормам»: материалы нужны по нормам, но отсутствуют в смете или указаны без количества.',
      ),
      category: 'Нормы материалов',
      urgency: 'обычная',
      requestedByRole: user?.role || '',
      requestedById: user?.id || null,
      selectedSuppliers: [],
    },
  }));
};

export const autoFillNormMaterialsForWorkRows = ({
  projectName,
  workName,
  sectionName,
  workQty,
  workUnit,
  currentMaterials = [],
  params = {},
  materialRowsAvailableForWork,
  materialNormForWork,
  capMaterialWriteoffQty,
  materialNameKey = materialLookupText,
}) => {
  if (!projectName || toNum(workQty) <= 0) return currentMaterials || [];
  const workPackage = params.workPackage || params.work_package || '';
  const available = materialRowsAvailableForWork(projectName, workPackage);
  const matches = available
    .map(material => ({
      material,
      norm: materialNormForWork(projectName, workName, sectionName, workQty, workUnit, material, params),
    }))
    .filter(item => item.norm);
  if (!matches.length) return currentMaterials || [];

  const byRule = {};
  matches.forEach(match => {
    byRule[match.norm.ruleId] = (byRule[match.norm.ruleId] || 0) + 1;
  });
  const matchByName = {};
  matches.forEach(match => {
    matchByName[materialNameKey(match.material.name)] = match;
  });

  const present = new Set();
  const next = (currentMaterials || []).map(material => {
    const key = materialNameKey(material.name);
    present.add(key);
    const match = matchByName[key];
    if (!match) return material;
    const patch = {
      unit: material.unit || match.norm.unit,
      workPackage: material.workPackage || match.material.workPackage || '',
      normQuantity: match.norm.normQuantity,
      normSource: match.norm.normSource,
    };
    if (material.autoNorm || material.quantity === '' || material.quantity === undefined || material.quantity === null) {
      return {
        ...material,
        ...patch,
        quantity: capMaterialWriteoffQty(projectName, material.name, match.norm.quantity, patch.workPackage),
        autoNorm: true,
      };
    }
    return { ...material, ...patch, autoNorm: false };
  });

  matches
    .filter(match => byRule[match.norm.ruleId] === 1 && !present.has(materialNameKey(match.material.name)))
    .slice(0, Math.max(0, 5 - next.length))
    .forEach(match => next.push({
      name: match.material.name,
      unit: match.norm.unit || match.material.unit || 'шт',
      workPackage: match.material.workPackage || '',
      quantity: capMaterialWriteoffQty(projectName, match.material.name, match.norm.quantity, match.material.workPackage || ''),
      autoNorm: true,
      normQuantity: match.norm.normQuantity,
      normSource: match.norm.normSource,
    }));

  return next;
};

export const buildMaterialNormPayload = (newMaterialNorm) => ({
  ruleKey: newMaterialNorm.ruleKey.trim(),
  name: newMaterialNorm.name.trim(),
  work: normListFromText(newMaterialNorm.workText),
  blockWork: normListFromText(newMaterialNorm.blockWorkText),
  material: normListFromText(newMaterialNorm.materialText),
  workUnit: newMaterialNorm.workUnit || 'м2',
  materialUnit: newMaterialNorm.materialUnit || 'кг',
  qtyPerUnit: toNum(newMaterialNorm.qtyPerUnit),
  thicknessBaseMm: newMaterialNorm.thicknessBaseMm === '' ? null : toNum(newMaterialNorm.thicknessBaseMm),
  defaultThicknessMm: newMaterialNorm.defaultThicknessMm === '' ? null : toNum(newMaterialNorm.defaultThicknessMm),
  label: newMaterialNorm.label.trim(),
  active: true,
});
