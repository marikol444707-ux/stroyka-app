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
  const normCoverage = notes.includes('Создано из ведомости') ||
    notes.includes('NORM_COVERAGE_REQUEST:') ||
    notes.includes('NORM_ESTIMATE_REQUEST:') ||
    notes.includes('Пакетная заявка из черновика сметы') ||
    (notes.includes('Норма:') && notes.includes('Расчётная потребность'));
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

export const supplyRequestHasReviewIssue = (req) => {
  const items = parseSupplyItems(req);
  return items.some(item => {
    const control = item?.estimateControl || item?.estimate_control || null;
    return ['no_active_estimate', 'no_estimate_material', 'over_estimate_need'].includes(control?.status || '');
  });
};

export const supplyRequestSourceBucket = (req) => {
  if (supplyRequestHasReviewIssue(req)) return 'review';
  return supplyRequestOrigin(req) ? 'estimate' : 'manual';
};

export const supplyRequestEstimateGroupLabel = (req) => {
  const lines = supplyNoteLines(req);
  const notePackage = supplyNoteValue(lines, 'Пакет работ') || supplyNoteValue(lines, 'Раздел сметы');
  const itemPackage = parseSupplyItems(req).map(item => item.workPackage || item.work_package || '').find(Boolean);
  const raw = req?.workPackage || req?.work_package || notePackage || itemPackage || 'Основная';
  return String(raw || 'Основная').trim() || 'Основная';
};

export const supplyRequestListGroup = (req) => {
  const bucket = supplyRequestSourceBucket(req);
  const project = req?.project || '— Без объекта —';
  if (bucket === 'estimate') {
    const estimateGroup = supplyRequestEstimateGroupLabel(req);
    return {
      key: project + '|estimate|' + estimateGroup,
      project,
      label: estimateGroup,
      bucket,
    };
  }
  if (bucket === 'review') {
    return {
      key: project + '|review',
      project,
      label: 'Требуют проверки',
      bucket,
    };
  }
  return {
    key: project + '|manual',
    project,
    label: 'Вручную',
    bucket,
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

export const supplierRecipientStatusSummary = (offerStatuses = []) => {
  const counts = (offerStatuses || []).reduce((acc, item) => {
    const status = item?.status || 'Ожидает ответа';
    acc[status] = (acc[status] || 0) + 1;
    return acc;
  }, {});
  return Object.entries(counts).map(([status, count]) => status + ': ' + count).join(' · ');
};

export const supplierRecipientLinkAction = (row = {}) => {
  if (!row || row.visibleToSupplier) return null;
  const supplierId = Number(row.linkSupplierId || row.targetSupplierId || row.supplierId || 0);
  if (!Number.isFinite(supplierId) || supplierId <= 0) return null;
  return {
    type: row.linkAction || 'link_supplier_user',
    supplierId,
    supplierName: row.linkSupplierName || row.targetSupplierName || row.supplierName || '',
    email: row.linkUserEmail || row.targetSupplierEmail || row.supplierEmail || '',
    reason: row.problemReason || '',
  };
};
