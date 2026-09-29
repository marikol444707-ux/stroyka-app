import { _normalizeUnit, toNum } from '../../utils/measureUtils';

export const workMaterialAccountingEnabled = () => process.env.REACT_APP_WORK_MATERIAL_ACCOUNTING_ENABLED === '1';
const packageName = value => String(value || '').trim() || 'Основная';
const round = value => Math.round(value * 1e6) / 1e6;

export function buildWorkMaterialAvailability({ personalRows = [], warehouseRows = [], projectName,
  workPackage = '', canonicalMaterialMeta, materialNameKey }) {
  const result = {};
  const add = (item, source) => {
    if (item.project !== projectName || packageName(item.workPackage || item.work_package) !== packageName(workPackage)) return;
    const amount = toNum(item.quantity);
    if (!Number.isFinite(amount) || amount <= 0) return;
    if (source === 'warehouse' && (!Number.isSafeInteger(item.id) || item.id <= 0)) return;
    const meta = canonicalMaterialMeta(projectName, item.name, item.unit);
    const key = materialNameKey(meta.name);
    if (!key) return;
    const unit = _normalizeUnit(item.unit || 'шт');
    const row = result[key] || (result[key] = { id: 'work-material:' + key + ':' + packageName(workPackage), name: meta.name, unit, workPackage: packageName(workPackage),
      quantity: 0, personalAvailable: 0, warehouseAvailable: 0, warehouseMaterialId: null,
      sourceConflict: false, aliases: [], materialAccountingVersion: 2 });
    if (row.unit !== unit || (meta.unit && _normalizeUnit(meta.unit) !== unit)) row.sourceConflict = true;
    if (source === 'personal') row.personalAvailable = round(row.personalAvailable + amount);
    else {
      if (row.warehouseMaterialId !== null) row.sourceConflict = true;
      row.warehouseMaterialId = item.id;
      row.warehouseAvailable = amount;
    }
    if (item.name !== row.name && !row.aliases.includes(item.name)) row.aliases.push(item.name);
  };
  personalRows.forEach(row => add(row, 'personal'));
  warehouseRows.forEach(row => add(row, 'warehouse'));
  Object.values(result).forEach(row => {
    if (row.sourceConflict) { row.warehouseAvailable = 0; row.warehouseMaterialId = null; }
    row.quantity = round(row.personalAvailable + row.warehouseAvailable);
  });
  return result;
}

export function allocateWorkMaterialSources(item, stock) {
  const total = toNum(item.quantity);
  const personal = item.sourcePreference === 'warehouse' ? 0
    : item.sourcePreference === 'personal' ? total : Math.min(total, Math.max(0, toNum(stock?.personalAvailable)));
  const warehouse = round(total - personal);
  return { ...item, personalQuantity: personal, warehouseQuantity: warehouse,
    warehouseMaterialId: warehouse > 0 && !stock?.sourceConflict ? stock?.warehouseMaterialId ?? null : null,
    materialAccountingVersion: 2 };
}
