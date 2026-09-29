import React from 'react';
import { allocateWorkMaterialSources, workMaterialAccountingEnabled } from '../work-material-accounting/materialSources';
import { buildWorkMaterialSelectionRow } from '../../utils/materialDocumentUtils';
import {
  applyMaterialOverNormReasonToRows,
  buildMaterialWriteoffBlockMessage,
  buildMaterialWriteoffRows,
  capMaterialWriteoffQtyValue,
  getMaterialWriteoffAvailableQty,
  requestMaterialNormOverrunReason,
} from '../../utils/materialWriteoffUtils';

export const createMaterialWriteoffActions = ({
  C,
  MaterialWriteoffStatus,
  canonicalMaterialMeta,
  fmtMeasure,
  isMobile,
  isPersonalMaterialRole,
  materialAvailabilityMapForWork,
  materialNameKey,
  setEstimateWorkMaterials,
  setSelectedWorks,
  confirmFn = window.confirm,
  promptFn = window.prompt,
}) => {
  const materialWriteoffRows = (projectName, usedMaterials = []) => buildMaterialWriteoffRows({
    projectName,
    usedMaterials,
    materialAvailabilityMapForWork,
    canonicalMaterialMeta,
    materialNameKey,
  });

  const materialWriteoffAvailableQty = (projectName, materialName, workPackage = '') => getMaterialWriteoffAvailableQty({
    projectName,
    materialName,
    workPackage,
    materialAvailabilityMapForWork,
    canonicalMaterialMeta,
    materialNameKey,
  });

  const capMaterialWriteoffQty = (projectName, materialName, quantity, workPackage = '') => capMaterialWriteoffQtyValue({
    projectName,
    materialName,
    quantity,
    workPackage,
    materialWriteoffAvailableQty,
  });

  const materialWriteoffBlockMessage = (projectName, usedMaterials = []) => buildMaterialWriteoffBlockMessage({
    projectName,
    rows: materialWriteoffRows(projectName, usedMaterials),
    isPersonalMaterialRole,
    fmtMeasure,
  });

  const materialNormOverrunReason = (projectName, workName, usedMaterials = []) => requestMaterialNormOverrunReason({
    rows: materialWriteoffRows(projectName, usedMaterials),
    workName,
    fmtMeasure,
    confirmFn,
    promptFn,
  });

  const applyMaterialOverNormReason = (projectName, usedMaterials = [], reason = '') => applyMaterialOverNormReasonToRows({
    usedMaterials,
    rows: materialWriteoffRows(projectName, usedMaterials),
    reason,
    materialNameKey,
  });

  const prepareWorkMaterialGroups = (projectName, groups) => {
    if (!workMaterialAccountingEnabled()) return groups;
    const remaining = new Map();
    return groups.map(items => items.map(item => {
      const meta = canonicalMaterialMeta(projectName, item.name, item.unit);
      const nameKey = materialNameKey(meta.name);
      const workPackage = item.workPackage || 'Основная';
      const key = nameKey + '\u0000' + workPackage;
      if (!remaining.has(key)) remaining.set(key, { ...materialAvailabilityMapForWork(projectName, workPackage)[nameKey] });
      const stock = remaining.get(key);
      const prepared = allocateWorkMaterialSources(item, stock);
      const rows = buildMaterialWriteoffRows({ projectName, usedMaterials: [prepared],
        materialAvailabilityMapForWork: () => ({ [nameKey]: stock }), canonicalMaterialMeta, materialNameKey });
      const error = buildMaterialWriteoffBlockMessage({ projectName, rows, isPersonalMaterialRole, fmtMeasure });
      if (error) throw new Error(error);
      stock.personalAvailable = Math.round((stock.personalAvailable - prepared.personalQuantity) * 1e6) / 1e6;
      stock.warehouseAvailable = Math.round((stock.warehouseAvailable - prepared.warehouseQuantity) * 1e6) / 1e6;
      stock.quantity = Math.round((stock.personalAvailable + stock.warehouseAvailable) * 1e6) / 1e6;
      return prepared;
    }));
  };

  const renderMaterialWriteoffStatus = (projectName, usedMaterials = [], onSourceChange) => React.createElement(MaterialWriteoffStatus, {
    rows: materialWriteoffRows(projectName, usedMaterials),
    C,
    fmtMeasure,
    isMobile,
    isPersonalMaterialRole,
    onSourceChange,
  });

  const upsertSelectedWorkMaterial = (itemId, material, quantity = '') => {
    const key = materialNameKey(material.name);
    setSelectedWorks(prev => {
      const cur = prev[itemId] || {};
      const list = Array.isArray(cur.materials) ? cur.materials : [];
      const exists = list.some(m => materialNameKey(m.name) === key);
      const row = buildWorkMaterialSelectionRow(material, quantity);
      const next = exists
        ? list.map(m => materialNameKey(m.name) === key ? { ...m, ...row, quantity: quantity !== undefined ? quantity : m.quantity } : m)
        : [...list, row];
      return { ...prev, [itemId]: { ...cur, materials: next } };
    });
  };

  const removeSelectedWorkMaterial = (itemId, materialName) => {
    const key = materialNameKey(materialName);
    setSelectedWorks(prev => {
      const cur = prev[itemId] || {};
      const list = Array.isArray(cur.materials) ? cur.materials : [];
      return { ...prev, [itemId]: { ...cur, materials: list.filter(m => materialNameKey(m.name) !== key) } };
    });
  };

  const updateSelectedWorkMaterialQty = (itemId, materialName, quantity) => {
    const key = materialNameKey(materialName);
    setSelectedWorks(prev => {
      const cur = prev[itemId] || {};
      const list = Array.isArray(cur.materials) ? cur.materials : [];
      return { ...prev, [itemId]: { ...cur, materials: list.map(m => materialNameKey(m.name) === key ? { ...m, quantity, autoNorm: false } : m) } };
    });
  };

  const upsertEstimateWorkMaterial = (workKey, material, quantity = '') => {
    const key = materialNameKey(material.name);
    setEstimateWorkMaterials(prev => {
      const list = Array.isArray(prev[workKey]) ? prev[workKey] : [];
      const exists = list.some(m => materialNameKey(m.name) === key);
      const row = buildWorkMaterialSelectionRow(material, quantity);
      const next = exists
        ? list.map(m => materialNameKey(m.name) === key ? { ...m, ...row, quantity: quantity !== undefined ? quantity : m.quantity } : m)
        : [...list, row];
      return { ...prev, [workKey]: next };
    });
  };

  const removeEstimateWorkMaterial = (workKey, materialName) => {
    const key = materialNameKey(materialName);
    setEstimateWorkMaterials(prev => {
      const list = Array.isArray(prev[workKey]) ? prev[workKey] : [];
      return { ...prev, [workKey]: list.filter(m => materialNameKey(m.name) !== key) };
    });
  };

  const updateEstimateWorkMaterialQty = (workKey, materialName, quantity) => {
    const key = materialNameKey(materialName);
    setEstimateWorkMaterials(prev => {
      const list = Array.isArray(prev[workKey]) ? prev[workKey] : [];
      return { ...prev, [workKey]: list.map(m => materialNameKey(m.name) === key ? { ...m, quantity, autoNorm: false } : m) };
    });
  };

  return {
    prepareWorkMaterialGroups,
    applyMaterialOverNormReason,
    capMaterialWriteoffQty,
    materialNormOverrunReason,
    materialWriteoffAvailableQty,
    materialWriteoffBlockMessage,
    materialWriteoffRows,
    removeEstimateWorkMaterial,
    removeSelectedWorkMaterial,
    renderMaterialWriteoffStatus,
    updateEstimateWorkMaterialQty,
    updateSelectedWorkMaterialQty,
    upsertEstimateWorkMaterial,
    upsertSelectedWorkMaterial,
  };
};
