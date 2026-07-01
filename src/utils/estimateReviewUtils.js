import { _normalizeUnit, fmtMeasure, normalizeMeasure, toNum } from './measureUtils';
import {
  estimateDiffTextKey,
  estimateItemTotal,
  estimatePackage,
  estimateRowsForDiff,
  estimateSectionsOf,
  normalizeEstimateItemType,
  normalizeEstimateWorkingItem,
} from './estimateUtils';
import { materialTitleForNormRule } from './materialNormUtils';

const fmtReviewMoney = (value) => (Math.round(Number(value || 0) * 100) / 100).toLocaleString('ru-RU') + ' ₽';
export const estimatePieceUnitKeys = new Set(['шт', 'компл', 'комплект', 'пара', 'набор', 'секция', 'труба', 'лист', 'рулон', 'упак', 'упаковка', 'пачка', 'ящик', 'бухта', 'мешок']);
export const estimateNormReviewIssueStatuses = ['Некорректное количество', 'Нехватка материала по норме', 'Нет материала в смете', 'Материал без количества', 'Материал без работы', 'Нет нормы'];

export const estimateQualityRows = (est) => {
  if (!est?.id) return [];
  const rows = [];
  const push = (status, section, item, sectionIdx, itemIdx, message, severity = 'warning') => {
    const normalized = normalizeMeasure(toNum(item?.quantity), item?.unit);
    rows.push({
      key: [est.id, sectionIdx, itemIdx, status].join('|'),
      status,
      severity,
      projectName: est.projectName || '',
      estimateId: est.id,
      estimateName: est.name || '',
      packageName: estimatePackage(est),
      sectionIdx,
      itemIdx,
      sectionName: section?.name || 'Без раздела',
      itemName: item?.name || 'Без названия',
      itemType: normalizeEstimateItemType(item, section?.name || ''),
      unit: item?.unit || '',
      quantity: item?.quantity,
      normalizedQuantity: normalized.qty,
      normalizedUnit: normalized.unit || item?.unit || '',
      priceWork: item?.priceWork,
      priceMaterial: item?.priceMaterial,
      total: estimateItemTotal(item),
      message,
    });
  };
  estimateSectionsOf(est).forEach((section, sectionIdx) => (section.items || []).forEach((rawItem, itemIdx) => {
    const item = normalizeEstimateWorkingItem(rawItem, section?.name || '');
    const name = String(item?.name || '').trim();
    const rawQtyText = String(item?.quantity ?? '').trim();
    const qty = toNum(item?.quantity);
    const unit = String(item?.unit || '').trim();
    const normalized = normalizeMeasure(qty, unit);
    const normUnitKey = _normalizeUnit(normalized.unit || unit);
    const itemType = normalizeEstimateItemType(item, section?.name || '');
    const priceWork = toNum(item?.priceWork);
    const priceMaterial = toNum(item?.priceMaterial);
    const isImportedResourceAdjustment = item?.isImported && item?.importKind === 'resource_adjustment';
    if (itemType === 'adjustment') return;
    if (isImportedResourceAdjustment) return;
    if (!name) push('Нет наименования', section, item, sectionIdx, itemIdx, 'У позиции нет названия — её нельзя надёжно сопоставить с работой, материалом или новой сметой.', 'critical');
    if (!unit) push('Нет единицы', section, item, sectionIdx, itemIdx, 'Не указана единица измерения. Без неё нельзя корректно закрывать объёмы, нормы и КС.', 'critical');
    if (!rawQtyText) {
      push('Нет количества', section, item, sectionIdx, itemIdx, 'Количество пустое. Нужно указать плановый объём по смете.', 'critical');
    } else if (qty < 0) {
      if (itemType === 'adjustment') {
        push('Корректировка ресурса', section, item, sectionIdx, itemIdx, 'Минусовая ресурсная строка сохранена для аудита импорта, но не участвует в суммах, КС и закрытии работ.', 'info');
      } else {
        push('Отрицательное количество', section, item, sectionIdx, itemIdx, 'Количество меньше нуля. Такая строка ломает сумму сметы, остатки и сопоставление с новой редакцией.', 'critical');
      }
    } else if (qty === 0) {
      push('Нулевое количество', section, item, sectionIdx, itemIdx, 'Количество равно 0. Если строка нужна, укажите объём; если не нужна — перенесите в исключение/архив.', 'warning');
    }
    if (qty > 0 && estimatePieceUnitKeys.has(normUnitKey) && Math.abs(normalized.qty - Math.round(normalized.qty)) > 0.001) {
      push('Дробное количество шт', section, item, sectionIdx, itemIdx, 'Штучная единица после нормализации получилась дробной: ' + fmtMeasure(qty, unit) + '. Проверьте, не должна ли единица быть «100 шт»/«компл.» или другое основание.', 'warning');
    }
    if (priceWork < 0 || priceMaterial < 0) {
      push('Отрицательная цена', section, item, sectionIdx, itemIdx, 'Цена работ или материалов меньше нуля. Для уменьшения объёма лучше использовать изменение к смете/исключение, а не минусовую цену.', 'critical');
    }
    if (itemType === 'work' && qty > 0 && Math.abs(estimateItemTotal(item)) < 0.01) {
      push('Нулевая сумма работы', section, item, sectionIdx, itemIdx, 'У рабочей строки есть объём, но сумма равна 0. Заполните цену или проверьте тип позиции.', 'warning');
    }
  }));
  const rank = { critical: 0, warning: 1, info: 2 };
  return rows.sort((a, b) => (rank[a.severity] ?? 9) - (rank[b.severity] ?? 9)
    || String(a.sectionName).localeCompare(String(b.sectionName), 'ru')
    || String(a.itemName).localeCompare(String(b.itemName), 'ru'));
};

export const estimateQualityDescription = (est, rows, reason) => {
  const counts = [...new Set(rows.map(r => r.status))]
    .map(status => ({ status, count: rows.filter(r => r.status === status).length }))
    .sort((a, b) => b.count - a.count);
  const lines = [
    'Автопроверка качества сметы после события: ' + (reason || 'сохранение сметы') + '.',
    'Объект: ' + (est.projectName || '') + '. Смета: ' + (est.name || '') + '. Пакет: ' + estimatePackage(est) + '.',
    '',
    'Найдено ошибок данных: ' + rows.length + '.',
    ...counts.map(x => '• ' + x.status + ': ' + x.count),
    '',
    'Первые строки для исправления:',
  ];
  rows.slice(0, 12).forEach((row, idx) => {
    lines.push((idx + 1) + '. ' + row.status + ' — ' + row.sectionName + ' / ' + row.itemName + '; ' + String(row.quantity ?? 'пусто') + ' ' + (row.unit || 'без ед.') + '; сумма ' + Math.round(row.total || 0).toLocaleString('ru-RU') + ' ₽. ' + row.message);
  });
  if (rows.length > 12) lines.push('...и ещё ' + (rows.length - 12) + ' строк.');
  lines.push(
    '',
    'Порядок исправления:',
    '1. Сначала исправить отрицательные/пустые количества, единицы и цены в самой смете.',
    '2. После сохранения система заново проверит нормы материалов и сопоставление с новой сметой.',
    '3. До исправления такие строки нельзя использовать как основание для КС, заявок снабжения и списания материалов.',
  );
  return lines.join('\n');
};

export const estimateNormReviewMarker = (estimateId) => 'ESTIMATE_NORM_REVIEW:' + String(estimateId || '');

export const estimateQualityReviewMarker = (estimateId) => 'ESTIMATE_QUALITY_REVIEW:' + String(estimateId || '');

export const estimateDiffReviewMarker = (baseEstimateId, nextEstimateId) => 'ESTIMATE_DIFF_REVIEW:' + String(baseEstimateId || '') + ':' + String(nextEstimateId || '');

export const estimateChangeReconcileMarker = (nextEstimateId) => 'ESTIMATE_CHANGE_RECONCILE:' + String(nextEstimateId || '');

export const estimateNormReviewDescription = (est, rows, reason) => {
  const counts = estimateNormReviewIssueStatuses
    .map(status => ({ status, count: rows.filter(r => r.status === status).length }))
    .filter(x => x.count > 0);
  const lines = [
    'Автопроверка сметы после события: ' + (reason || 'сохранение сметы') + '.',
    'Объект: ' + (est.projectName || '') + '. Смета: ' + (est.name || '') + '. Пакет: ' + estimatePackage(est) + '.',
    '',
    'Найдено замечаний: ' + rows.length + '.',
    ...counts.map(x => '• ' + x.status + ': ' + x.count),
    '',
    'Первые строки для проверки:',
  ];
  rows.slice(0, 12).forEach((row, idx) => {
    const need = row.requiredQty ? ', потребность ' + fmtMeasure(row.requiredQty, row.requiredUnit) : '';
    const inEstimate = row.materialQty ? ', в смете ' + fmtMeasure(row.materialQty, row.materialUnit) : '';
    lines.push((idx + 1) + '. ' + row.status + ' — ' + (row.sectionName || 'Без раздела') + ' / ' + (row.workName || row.materialName || 'позиция') + '; материал: ' + (row.materialName || materialTitleForNormRule(row.rule) || '—') + need + inEstimate + '.');
  });
  if (rows.length > 12) lines.push('...и ещё ' + (rows.length - 12) + ' строк.');
  lines.push(
    '',
    'Порядок исправления:',
    '1. `Некорректное количество` и `Материал без количества` — сначала исправить количество в смете.',
    '2. `Нет материала в смете` — добавить строку материала, создать заявку снабжения или подтвердить, что материал не нужен.',
    '3. `Нет нормы` и `Материал без работы` — уточнить правило нормы или привязку материала к работе.',
    '4. После правки сохранить смету: задача обновится или закроется автоматически.',
  );
  return lines.join('\n');
};

export const estimateDiffReviewDescription = (baseEst, nextEst, diff, reason) => {
  const lines = [
    'Автосверка смет после события: ' + (reason || 'активация новой сметы') + '.',
    'Объект: ' + (nextEst.projectName || baseEst.projectName || '') + '. Пакет: ' + estimatePackage(nextEst) + '.',
    '',
    'База: ' + (baseEst.name || '') + ' (' + (baseEst.version ? 'v' + baseEst.version + ', ' : '') + (baseEst.status || '') + ').',
    'Новая смета: ' + (nextEst.name || '') + ' (' + (nextEst.version ? 'v' + nextEst.version + ', ' : '') + (nextEst.status || '') + ').',
    '',
    'Было: ' + fmtReviewMoney(diff.baseTotal) + '. Стало: ' + fmtReviewMoney(diff.nextTotal) + '. Разница: ' + (diff.impact > 0 ? '+' : '') + fmtReviewMoney(diff.impact) + '.',
    'Изменено: ' + diff.changed.length + '. Добавлено: ' + diff.added.length + '. Исключено: ' + diff.removed.length + '.',
    '',
    'Первые позиции по влиянию:',
  ];
  const rows = [
    ...diff.changed.map(x => ({ kind: 'Изменено', name: x.next.name, section: x.next.section, impact: x.impact })),
    ...diff.added.map(x => ({ kind: 'Добавлено', name: x.name, section: x.section, impact: x.impact })),
    ...diff.removed.map(x => ({ kind: 'Исключено', name: x.name, section: x.section, impact: x.impact })),
  ].sort((a, b) => Math.abs(b.impact) - Math.abs(a.impact)).slice(0, 12);
  rows.forEach((row, idx) => lines.push((idx + 1) + '. ' + row.kind + ' — ' + row.section + ' / ' + row.name + '; влияние ' + (row.impact > 0 ? '+' : '') + fmtReviewMoney(row.impact) + '.'));
  if (!rows.length) lines.push('Существенных изменений по позициям не найдено.');
  lines.push('', 'Что сделать: открыть сопоставительную ведомость, проверить добавленные/исключённые объёмы и решить, что уже закрывает утверждённые изменения к смете, а что остаётся отдельной допработой.');
  return lines.join('\n');
};

export const estimateChangeReconcileDescription = (baseEst, nextEst, decisions, includedCount, reason) => {
  const unresolved = decisions || [];
  const lines = [
    'Фоновая сверка утверждённых изменений к смете после события: ' + (reason || 'новая смета') + '.',
    'Объект: ' + (nextEst.projectName || baseEst.projectName || '') + '. Пакет: ' + estimatePackage(nextEst) + '.',
    'База: ' + (baseEst.name || '') + '. Новая смета: ' + (nextEst.name || '') + '.',
    '',
    'Автоматически включено в новую смету: ' + includedCount + '.',
    'Нужно проверить вручную: ' + unresolved.length + '.',
    '',
    'Спорные позиции:',
  ];
  unresolved.slice(0, 12).forEach((d, idx) => {
    const u = d.change || {};
    lines.push((idx + 1) + '. ' + (u.changeType || 'Изменение') + ' — ' + (u.sectionName ? u.sectionName + ' / ' : '') + (u.estimateItemName || u.description || 'без названия') + '; ' + fmtMeasure(u.deltaQuantity || u.quantity, u.unit) + '; причина: ' + (d.reason || 'не сопоставлено') + '.');
  });
  if (unresolved.length > 12) lines.push('...и ещё ' + (unresolved.length - 12) + ' поз.');
  if (!unresolved.length) lines.push('Спорных позиций нет.');
  lines.push('', 'Что сделать: открыть сопоставительную ведомость и изменения к смете, проверить спорные позиции и решить, оставить их отдельной допработой или выпустить корректировку сметы.');
  return lines.join('\n');
};

const estimateChangeUnitKey = (unit) => estimateDiffTextKey(normalizeMeasure(1, unit).unit || unit || '');

const estimateChangeNameScore = (left, right) => {
  const a = estimateDiffTextKey(left);
  const b = estimateDiffTextKey(right);
  if (!a || !b) return 0;
  if (a === b) return 1;
  if (a.includes(b) || b.includes(a)) return 0.92;
  const aw = a.split(' ').filter(w => w.length > 3);
  const bw = b.split(' ').filter(w => w.length > 3);
  if (!aw.length || !bw.length) return 0;
  const overlap = aw.filter(w => bw.includes(w)).length;
  return overlap / Math.max(aw.length, bw.length);
};

const estimateChangeTargetNames = (change) => [...new Set([change?.estimateItemName, change?.description].map(v => String(v || '').trim()).filter(Boolean))];

const estimateChangeNormalizedQty = (qty, unit) => {
  const n = normalizeMeasure(toNum(qty), unit);
  return { qty: toNum(n.qty), unit: n.unit || unit || '' };
};

const estimateChangeRequiredQty = (change) => {
  const type = change?.changeType || 'Работа вне сметы';
  const base = toNum(change?.baseQuantity);
  const delta = toNum(change?.deltaQuantity || change?.quantity);
  let raw = toNum(change?.newRequiredQuantity);
  if (raw <= 0 && (base > 0 || delta > 0)) {
    raw = type === 'Исключение объёма' ? Math.max(0, base - delta) : base + delta;
  }
  return estimateChangeNormalizedQty(raw || delta, change?.unit);
};

const findEstimateChangeRowMatch = (change, rows = []) => {
  const names = estimateChangeTargetNames(change);
  const unitKey = estimateChangeUnitKey(change?.unit);
  if (!names.length) return null;
  const exactKeys = names.map(name => [
    estimateDiffTextKey(change?.sectionName),
    estimateDiffTextKey(name),
    unitKey,
  ].join('|'));
  let best = null;
  rows.forEach(row => {
    if (!row) return;
    const rowUnitKey = estimateChangeUnitKey(row.unit);
    if (unitKey && rowUnitKey && unitKey !== rowUnitKey) return;
    const exact = exactKeys.includes(row.key);
    const nameScore = Math.max(...names.map(name => estimateChangeNameScore(name, row.name)));
    const sectionScore = estimateDiffTextKey(change?.sectionName) && estimateDiffTextKey(change?.sectionName) === estimateDiffTextKey(row.section) ? 0.08 : 0;
    const score = exact ? 1 : Math.min(0.99, nameScore + sectionScore);
    if (score >= 0.72 && (!best || score > best.score)) best = { row, score, exact };
  });
  return best;
};

export const estimateChangeAutoDecision = (change, nextEst, diff) => {
  const type = change?.changeType || 'Работа вне сметы';
  const required = estimateChangeRequiredQty(change);
  const tolerance = Math.max(0.001, Math.abs(required.qty || 0) * 0.01);
  const nextRows = estimateRowsForDiff(nextEst);
  const addedRows = diff.added || [];
  const changedNextRows = (diff.changed || []).map(x => x.next);
  const removedRows = diff.removed || [];
  if (type === 'Исключение объёма') {
    const removed = findEstimateChangeRowMatch(change, removedRows);
    if (removed && required.qty <= tolerance) {
      return { change, autoInclude: true, reason: 'строка исключена из новой сметы', candidate: removed.row, score: removed.score };
    }
    const changed = findEstimateChangeRowMatch(change, changedNextRows) || findEstimateChangeRowMatch(change, nextRows);
    if (changed && changed.row.qty <= required.qty + tolerance) {
      return { change, autoInclude: true, reason: 'объём уменьшен до ' + fmtMeasure(required.qty, required.unit), candidate: changed.row, score: changed.score };
    }
    return { change, autoInclude: false, reason: 'не найдено уверенное уменьшение объёма', candidate: changed?.row || removed?.row || null, score: changed?.score || removed?.score || 0 };
  }
  if (type === 'Дополнительный объём к строке сметы') {
    const changed = findEstimateChangeRowMatch(change, changedNextRows) || findEstimateChangeRowMatch(change, nextRows);
    if (changed && required.qty > 0 && changed.row.qty + tolerance >= required.qty) {
      return { change, autoInclude: true, reason: 'новая смета содержит требуемый объём ' + fmtMeasure(required.qty, required.unit), candidate: changed.row, score: changed.score };
    }
    return { change, autoInclude: false, reason: 'новая смета не закрывает требуемый объём', candidate: changed?.row || null, score: changed?.score || 0 };
  }
  const added = findEstimateChangeRowMatch(change, addedRows);
  const qty = estimateChangeNormalizedQty(change?.deltaQuantity || change?.quantity, change?.unit);
  if (added && (!qty.qty || added.row.qty + tolerance >= qty.qty * 0.95)) {
    return { change, autoInclude: true, reason: 'работа появилась новой строкой сметы', candidate: added.row, score: added.score };
  }
  const candidate = findEstimateChangeRowMatch(change, nextRows);
  return { change, autoInclude: false, reason: 'работа не найдена как новая строка сметы', candidate: candidate?.row || null, score: candidate?.score || 0 };
};
