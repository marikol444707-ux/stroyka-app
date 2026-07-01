import React from 'react';
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

  const renderMaterialWriteoffStatus = (projectName, usedMaterials = []) => React.createElement(MaterialWriteoffStatus, {
    rows: materialWriteoffRows(projectName, usedMaterials),
    C,
    fmtMeasure,
    isMobile,
    isPersonalMaterialRole,
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
