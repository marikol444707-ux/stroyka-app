import { toNum } from './measureUtils';

export const buildMaterialWriteoffRows = ({
  projectName,
  usedMaterials = [],
  materialAvailabilityMapForWork,
  canonicalMaterialMeta,
  materialNameKey,
}) => {
  return (usedMaterials || [])
    .filter(m => m?.name)
    .map(m => {
      const workPackage = m.workPackage || m.work_package || '';
      const stockByName = materialAvailabilityMapForWork(projectName, workPackage);
      const meta = canonicalMaterialMeta(projectName, m.name, m.unit);
      const key = materialNameKey(meta.name);
      const stock = stockByName[key] || null;
      const qty = toNum(m.quantity);
      const normQty = toNum(m.normQuantity);
      const unit = meta.unit || m.unit || stock?.unit || 'шт';
      const available = toNum(stock?.quantity);
      const tolerance = normQty > 0 ? Math.max(0.001, normQty * 0.1) : 0;
      const overNormQty = normQty > 0 ? Math.max(0, qty - normQty) : 0;
      const overNorm = normQty > 0 && overNormQty > tolerance;
      const overStock = qty > available + 0.0001;
      const noNorm = qty > 0 && normQty <= 0;
      const restAfter = Math.max(0, available - qty);
      return {
        ...m,
        key,
        qty,
        unit,
        stock,
        available,
        normQty,
        overNorm,
        overNormQty,
        overStock,
        noNorm,
        restAfter,
      };
    });
};

export const getMaterialWriteoffAvailableQty = ({
  projectName,
  materialName,
  workPackage = '',
  materialAvailabilityMapForWork,
  canonicalMaterialMeta,
  materialNameKey,
}) => {
  const meta = canonicalMaterialMeta(projectName, materialName);
  const stock = materialAvailabilityMapForWork(projectName, workPackage)[materialNameKey(meta.name)];
  return stock ? toNum(stock.quantity) : 0;
};

export const capMaterialWriteoffQtyValue = ({
  projectName,
  materialName,
  quantity,
  workPackage = '',
  materialWriteoffAvailableQty,
}) => {
  const qty = toNum(quantity);
  if (qty <= 0) return quantity || '';
  const available = materialWriteoffAvailableQty(projectName, materialName, workPackage);
  if (available > 0 && qty > available) return Math.round(available * 1000) / 1000;
  return qty;
};

export const buildMaterialWriteoffBlockMessage = ({
  projectName,
  rows = [],
  isPersonalMaterialRole,
  fmtMeasure,
}) => {
  const bad = rows.filter(r => !r.stock || r.overStock);
  if (!bad.length) return '';
  return bad.map(r => {
    if (!r.stock) return isPersonalMaterialRole()
      ? 'Материал «' + r.name + '» не выдан вам или получение не подтверждено.'
      : 'Материал «' + r.name + '» не найден на складе объекта «' + projectName + '».';
    return 'Недостаточно материала «' + r.name + '»: выбрано ' + fmtMeasure(r.qty, r.unit) + ', доступно ' + fmtMeasure(r.available, r.stock.unit || r.unit) + '.';
  }).join('\n');
};

export const applyMaterialOverNormReasonToRows = ({
  usedMaterials = [],
  rows = [],
  reason = '',
  materialNameKey,
}) => {
  if (!reason) return usedMaterials || [];
  const overKeys = new Set(rows.filter(r => r.overNorm).map(r => r.key));
  return (usedMaterials || []).map(m => overKeys.has(materialNameKey(m.name)) ? { ...m, overNorm: true, overNormReason: reason } : m);
};
