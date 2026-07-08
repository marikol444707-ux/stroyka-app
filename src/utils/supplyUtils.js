import { toNum } from './measureUtils';

export const parseSupplyItems = (req) => {
  if (!req) return [];
  if (req.itemsJson) {
    try {
      const arr = typeof req.itemsJson === 'string' ? JSON.parse(req.itemsJson) : req.itemsJson;
      if (Array.isArray(arr) && arr.length > 0) {
        return arr.map(it => ({
          ...it,
          workPackage: it.workPackage || it.work_package || req.workPackage || req.work_package || '',
        }));
      }
    } catch (_) {}
  }
  if (req.materialName) {
    return [{
      materialName: req.materialName,
      quantity: Number(req.quantity) || 0,
      unit: req.unit || 'шт',
      workPackage: req.workPackage || req.work_package || '',
    }];
  }
  return [];
};

export const materialControlRequestItems = (req) => parseSupplyItems(req).map(item => ({
  ...item,
  materialName: item.materialName || item.name || '',
  quantity: toNum(item.quantity),
  unit: item.unit || req?.unit || 'шт',
  workPackage: item.workPackage || item.work_package || req?.workPackage || req?.work_package || '',
}));

export const parseOfferItems = (offer) => {
  if (!offer) return [];
  if (offer.itemsKpJson) {
    try {
      const arr = typeof offer.itemsKpJson === 'string' ? JSON.parse(offer.itemsKpJson) : offer.itemsKpJson;
      if (Array.isArray(arr) && arr.length > 0) return arr;
    } catch (_) {}
  }
  return [];
};

export const supplyNoteLines = (req) => String(req?.notes || '')
  .split(/\r?\n/)
  .map(s => s.trim())
  .filter(Boolean);

export const supplyNoteValue = (lines, label) => {
  const prefix = String(label || '').toLowerCase() + ':';
  const line = (lines || []).find(l => l.toLowerCase().startsWith(prefix));
  return line ? line.slice(label.length + 1).trim() : '';
};

export const supplyRequestOrigin = (req) => {
  const lines = supplyNoteLines(req);
  if (!lines.length) return null;
  const notes = lines.join('\n');
  const materialControl = lines.some(l => l.startsWith('MATERIAL_CONTROL_REQUEST:')) || notes.includes('Создано из контроля материалов');
  const normCoverage = notes.includes('Создано из ведомости') || (notes.includes('Норма:') && notes.includes('Расчётная потребность'));
  if (!materialControl && !normCoverage) return null;
  const projectName = supplyNoteValue(lines, 'Объект') || req.project || '';
  const materialName = supplyNoteValue(lines, 'Материал') || req.materialName || '';
  const facts = materialControl ? [
    ['Сметных строк', supplyNoteValue(lines, 'Сметных строк')],
    ['Разделы', supplyNoteValue(lines, 'Разделы')],
    ['Работы', supplyNoteValue(lines, 'Работы')],
    ['План', supplyNoteValue(lines, 'План по смете')],
    ['Поставлено', supplyNoteValue(lines, 'Поставлено/перемещено')],
    ['Заявки/путь', supplyNoteValue(lines, 'В заявках и пути')],
    ['Нехватка', supplyNoteValue(lines, 'Расчётная нехватка')],
  ] : [
    ['Смета', supplyNoteValue(lines, 'Смета')],
    ['Раздел', supplyNoteValue(lines, 'Раздел')],
    ['Работа', supplyNoteValue(lines, 'Работа')],
    ['Объём', supplyNoteValue(lines, 'Объём работы')],
    ['Норма', supplyNoteValue(lines, 'Норма')],
    ['Потребность', supplyNoteValue(lines, 'Расчётная потребность')],
  ];
  return {
    type: materialControl ? 'material-control' : 'norm-coverage',
    label: materialControl ? 'Из контроля материалов' : 'Из норм материалов',
    projectName,
    materialName,
    facts: facts.filter(([, value]) => value),
  };
};

export const supplyMaterialKey = (value) => String(value || '')
  .toLowerCase()
  .replace(/[.,;:()«»"']/g, ' ')
  .replace(/\s+/g, ' ')
  .trim();

export const supplyUnitKey = (value) => String(value || '')
  .toLowerCase()
  .replace(/[²]/g, '2')
  .replace(/[³]/g, '3')
  .replace(/\s+/g, '')
  .trim();

export const isSameSupplyMaterial = (left, right) => {
  const leftKey = supplyMaterialKey(left);
  const rightKey = supplyMaterialKey(right);
  if (!leftKey || !rightKey) return false;
  return leftKey === rightKey || leftKey.includes(rightKey) || rightKey.includes(leftKey);
};

export const isActiveSupplyRequestStatus = (status) => (
  ['Новая', 'Подтверждена прорабом', 'Утверждена', 'КП запрошены', 'В пути', 'Частично поставлено', 'Проблема поставки', 'Утверждено']
    .includes(status || 'Новая')
);

export const isHistoricalSupplierOfferStatus = (status) => ['Отклонено', 'Отозвано'].includes(status || '');

export const splitSupplierOffersByStatus = (offers = []) => {
  const active = [];
  const history = [];

  (offers || []).forEach(offer => {
    if (isHistoricalSupplierOfferStatus(offer?.status)) {
      history.push(offer);
    } else {
      active.push(offer);
    }
  });

  return { active, history };
};
