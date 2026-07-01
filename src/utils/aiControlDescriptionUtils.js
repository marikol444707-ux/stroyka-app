import { _normalizeUnit, fmtMeasure, normalizeMeasure, toNum } from './measureUtils';
import { materialLookupText } from './materialMatchUtils';

export const parseAiTaskPayload = (task) => {
  try {
    return JSON.parse(task?.actionPayload || '{}');
  } catch {
    return {};
  }
};

export const materialControlMarker = (type, projectName, materialName, unit = '') => (
  'MATERIAL_CONTROL:' + String(type || '') + ':' + materialLookupText(projectName) + ':' + materialLookupText(materialName) + '|' + _normalizeUnit(unit || '')
);

export const materialControlRowPackageKey = (row = {}) => String(row.workPackage || row.work_package || row.packageName || '').trim().toLowerCase();

export const materialControlSupplyMarker = (projectName, row) => (
  'MATERIAL_CONTROL_REQUEST:' + [
    materialLookupText(projectName),
    materialLookupText(row?.name),
    _normalizeUnit(row?.unit || ''),
    materialControlRowPackageKey(row),
  ].join('|')
);

export const invoiceControlProjectName = (invoice, control = {}) => control.projectName || invoice?.project || (invoice?.location && invoice.location !== 'Основной склад' ? invoice.location : '');

export const invoiceControlMaterialName = (control = {}, item = {}) => control.canonicalName || control.name || item.name || '';

export const invoiceControlUnit = (control = {}, item = {}) => control.rowUnit || control.unit || item.unit || 'шт';

export const invoiceControlLineKey = (projectName, invoice, control, item = {}) => [
  materialLookupText(projectName),
  String(invoice?.id || invoice?.number || invoice?.date || 'draft'),
  String(control?.index ?? ''),
  materialLookupText(invoiceControlMaterialName(control, item)),
  _normalizeUnit(invoiceControlUnit(control, item) || ''),
  materialControlRowPackageKey(control || item),
].join('|');

export const invoiceControlSupplyMarker = (projectName, invoice, control, item) => 'INVOICE_CONTROL_REQUEST:' + invoiceControlLineKey(projectName, invoice, control, item);

export const invoiceControlReviewMarker = (projectName, invoice, control, item) => 'INVOICE_MATERIAL_REVIEW:' + invoiceControlLineKey(projectName, invoice, control, item);

export const invoiceControlNeedsReview = (control = {}) => (
  control.status === 'Вне сметы'
    || toNum(control.overQty) > 0
    || toNum(control.priceOverSum) > 1
    || !!control.unitMismatch
);

export const invoiceControlReviewReason = (control = {}) => {
  if (control.status === 'Вне сметы') return 'материал есть в накладной, но не найден в активной смете объекта';
  if (control.unitMismatch) return 'единица измерения в накладной отличается от единицы в смете';
  if (toNum(control.overQty) > 0) return 'после этой накладной материал выходит сверх сметного плана';
  if (toNum(control.priceOverSum) > 1) return 'цена строки выше сметного ориентира';
  return 'строка требует проверки';
};

export const roomControlMarker = (type, projectName) => 'ROOM_CONTROL:' + String(type || '') + ':' + materialLookupText(projectName);

export const journalRoomLinkKey = (row) => [
  materialLookupText(row?.description || row?.workName || ''),
  String(row?.date || '').slice(0, 10),
  Math.round(toNum(row?.quantity) * 1000) / 1000,
  _normalizeUnit(normalizeMeasure(toNum(row?.quantity), row?.unit).unit || row?.unit || ''),
  materialLookupText(row?.masterName || ''),
].join('|');

export const materialControlDescription = (kind, projectName, row, reason = 'Фоновая проверка материалов') => {
  const lines = [
    'Автоконтроль материалов после события: ' + reason + '.',
    'Объект: ' + projectName + '.',
    'Материал: ' + (row.name || 'без названия') + ' (' + (row.unit || 'шт') + ').',
    '',
  ];
  if (kind === 'purchase') {
    lines.push(
      'План по смете: ' + fmtMeasure(row.planQty, row.unit) + '.',
      'Получено/перемещено на объект: ' + fmtMeasure(row.supplied, row.unit) + '.',
      'В заявках и пути: ' + fmtMeasure(toNum(row.requested) + toNum(row.inTransit), row.unit) + '.',
      'К докупке: ' + fmtMeasure(row.toBuy, row.unit) + '.',
      '',
      'Что сделать: проверить заявки, КП и поставки. Если материала действительно не хватает — оформить или уточнить заявку снабжения.',
    );
  } else if (kind === 'outside') {
    const c = row.aliasCandidate || null;
    lines.push(
      'Материал есть в поставках, перемещениях или списании, но в активной смете нет плановой строки.',
      'Поступило/перемещено: ' + fmtMeasure(row.supplied, row.unit) + '. Списано: ' + fmtMeasure(row.used, row.unit) + '.',
      c ? 'Похожая строка в смете: ' + c.name + ' (' + (c.unit || row.unit || 'шт') + '), уверенность ' + Math.min(99, Math.round(45 + toNum(c.score) * 4)) + '%.' : '',
      '',
      c
        ? 'Что сделать: если это тот же материал — подтвердить сопоставление. Если нет — добавить позицию в смету или оформить изменение к смете.'
        : 'Что сделать: проверить, это материал вне сметы, ошибка импорта сметы или неверное наименование. При необходимости добавить позицию в смету или оформить изменение к смете.',
    );
  } else if (kind === 'writeoff') {
    lines.push(
      'Мастер/бригада списали больше, чем им подписано передано.',
      'Выдано по актам передачи: ' + fmtMeasure(row.issued, row.unit) + '.',
      'Списано в журнале работ: ' + fmtMeasure(row.used, row.unit) + '.',
      'Сверх выдачи: ' + fmtMeasure(row.usedWithoutIssue, row.unit) + '.',
      '',
      'Что сделать: проверить передачу материала мастеру и записи ЖПР. Либо оформить недостающую передачу, либо исправить списание.',
    );
  } else if (kind === 'norm_over') {
    lines.push(
      'По журналу работ списано больше нормативной потребности.',
      'Списано: ' + fmtMeasure(row.qty, row.unit) + '. Норма: ' + fmtMeasure(row.normQty, row.unit) + '.',
      'Перерасход: ' + fmtMeasure(row.overQty, row.unit) + ' (' + (row.overPct || 0) + '%).',
      '',
      'Что сделать: проверить толщину/параметры работ, норму расхода и фактическое списание мастера.',
    );
  } else if (kind === 'without_norm') {
    lines.push(
      'Материал списан в журнале работ, но система не нашла норму расхода.',
      'Списано без нормы: ' + fmtMeasure(row.withoutNormQty, row.unit) + '.',
      '',
      'Что сделать: добавить норму расхода для работы или подтвердить, что списание ручное и норму применять не нужно.',
    );
  }
  return lines.join('\n');
};

export const roomControlDescription = (kind, projectName, rows, reason = 'Фоновая проверка помещений') => {
  const lines = [
    'Автоконтроль помещений после события: ' + reason + '.',
    'Объект: ' + projectName + '.',
    '',
  ];
  if (kind === 'measurements') {
    lines.push('Найдены помещения или проёмы с неполным обмером: ' + rows.length + '.');
    rows.slice(0, 8).forEach((r, idx) => {
      lines.push((idx + 1) + '. ' + (r.room?.name || 'Помещение') + ' — ' + (r.check?.issues || []).slice(0, 4).join('; '));
    });
    if (rows.length > 8) lines.push('...и ещё ' + (rows.length - 8) + ' помещений.');
    lines.push('', 'Что сделать: открыть вкладку `Помещения`, заполнить размеры пола/стен/потолка/высоты, размеры окон/дверей и глубину откосов. После исправления задача закроется автоматически.');
  } else if (kind === 'work_links') {
    lines.push('В журнале работ есть записи без привязки к помещению: ' + rows.length + '.');
    rows.slice(0, 10).forEach((w, idx) => {
      lines.push((idx + 1) + '. ' + String(w.date || '') + ' — ' + (w.description || 'Работа') + '; ' + fmtMeasure(w.quantity, w.unit) + '; ' + (w.masterName || 'исполнитель не указан') + '.');
    });
    if (rows.length > 10) lines.push('...и ещё ' + (rows.length - 10) + ' записей.');
    lines.push('', 'Что сделать: новые работы закрывать через выбор помещения/поверхности. По старым записям проверить, нужно ли перенести факт в `room_works` или оставить как общую работу без помещения.');
  }
  return lines.join('\n');
};
