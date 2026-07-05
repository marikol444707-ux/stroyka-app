export const DIRECTOR_MAP_FILTERS = [
  { id: 'all', label: 'Все' },
  { id: 'red', label: 'Красные' },
  { id: 'material', label: 'Материалы' },
  { id: 'supply', label: 'Поставка' },
  { id: 'documents', label: 'Документы' },
  { id: 'money', label: 'Деньги' },
  { id: 'review', label: 'Проверить связи' },
];

export const SOURCE_COLUMNS = [
  { id: 'estimate', label: 'Смета' },
  { id: 'workJournal', label: 'ЖПР' },
  { id: 'supply', label: 'Поставка' },
  { id: 'warehouse', label: 'Склад' },
  { id: 'documents', label: 'Документы' },
  { id: 'payments', label: 'Деньги' },
];

const severityRank = {
  red: 4,
  danger: 4,
  yellow: 3,
  warning: 3,
  amber: 3,
  blue: 2,
  info: 2,
  green: 1,
  ok: 1,
};

export function clampPercent(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return 0;
  return Math.max(0, Math.min(100, Math.round(number)));
}

export function getSignalTone(signal = {}) {
  const severity = String(signal.severity || signal.tone || '').toLowerCase();
  if (severity === 'red' || severity === 'danger') return 'danger';
  if (severity === 'yellow' || severity === 'warning' || severity === 'amber') return 'warning';
  if (severity === 'green' || severity === 'ok') return 'success';
  return 'info';
}

export function getItemTone(item = {}) {
  const signals = item.signals || [];
  if (!signals.length) return item.status === 'Завершен' || item.status === 'Завершён' ? 'success' : 'info';
  const highest = signals.reduce((current, signal) => {
    const severity = String(signal.severity || signal.tone || 'info').toLowerCase();
    return severityRank[severity] > severityRank[current] ? severity : current;
  }, 'info');
  if (highest === 'red' || highest === 'danger') return 'danger';
  if (highest === 'yellow' || highest === 'warning' || highest === 'amber') return 'warning';
  return 'info';
}

export function getStageStatusTone(item = {}) {
  if (item.status === 'Завершен' || item.status === 'Завершён') return 'success';
  if (getItemTone(item) === 'danger') return 'danger';
  if (getItemTone(item) === 'warning') return 'warning';
  if (item.status === 'Не начат') return 'warning';
  return 'info';
}

export function getSupplyStepTone(status) {
  const value = String(status || '').toLowerCase();
  if (value === 'danger' || value === 'red') return 'danger';
  if (value === 'warning' || value === 'amber' || value === 'yellow') return 'warning';
  if (value === 'ok' || value === 'green' || value === 'success') return 'success';
  return 'info';
}

export function formatMoneyShort(value) {
  const number = Number(value || 0);
  if (!Number.isFinite(number) || number === 0) return '0';
  const abs = Math.abs(number);
  if (abs >= 1000000) {
    const result = number / 1000000;
    return result.toLocaleString('ru-RU', { maximumFractionDigits: 2 }) + ' млн';
  }
  if (abs >= 1000) {
    const result = number / 1000;
    return result.toLocaleString('ru-RU', { maximumFractionDigits: 0 }) + ' тыс.';
  }
  return number.toLocaleString('ru-RU');
}

export function getSignalCounts(items = []) {
  return items.reduce((acc, item) => {
    (item.signals || []).forEach(signal => {
      const tone = getSignalTone(signal);
      if (tone === 'danger') acc.red += 1;
      else if (tone === 'warning') acc.yellow += 1;
      else acc.info += 1;
      acc.total += 1;
    });
    if (item.reviewState === 'needs_review') acc.review += 1;
    return acc;
  }, { red: 0, yellow: 0, info: 0, total: 0, review: 0 });
}

export function getItemTags(item = {}) {
  const tags = new Set(item.tags || []);
  const sourceRefs = item.sourceRefs || {};
  Object.keys(sourceRefs).forEach(key => {
    if (sourceRefs[key]?.status && sourceRefs[key].status !== 'missing') tags.add(key);
  });
  if (sourceRefs.payments?.status && sourceRefs.payments.status !== 'missing') tags.add('money');
  if (sourceRefs.supply?.status && sourceRefs.supply.status !== 'missing') tags.add('supply');
  if (sourceRefs.warehouse?.status && sourceRefs.warehouse.status !== 'missing') tags.add('material');
  if (sourceRefs.documents?.status && sourceRefs.documents.status !== 'missing') tags.add('documents');
  if (Number(item.money?.fact || 0) || Number(item.money?.obligations || 0)) tags.add('money');
  (item.signals || []).forEach(signal => {
    if (signal.type) tags.add(signal.type);
    if (signal.type === 'material') tags.add('material');
    if (signal.type === 'document') tags.add('documents');
    if (signal.type === 'money') tags.add('money');
    if (signal.type === 'supply') tags.add('supply');
    if (signal.type === 'link_quality') tags.add('review');
  });
  if (item.reviewState === 'needs_review') tags.add('review');
  if ((item.supplyChain || []).length) tags.add('supply');
  return tags;
}

export function filterDirectorMapItems(items = [], filter = 'all') {
  if (filter === 'all') return items;
  if (filter === 'red') return items.filter(item => getItemTone(item) === 'danger');
  return items.filter(item => getItemTags(item).has(filter));
}

export function getSourceCell(sourceRef = {}, item = {}) {
  const status = sourceRef.status || 'missing';
  if (status === 'confirmed' || status === 'ok') return { tone: 'success', text: sourceRef.label || 'есть связь' };
  if (status === 'needs_review') return { tone: 'warning', text: sourceRef.label || 'needs_review' };
  if (status === 'mock') {
    const itemTone = getItemTone(item);
    return { tone: itemTone === 'danger' ? 'danger' : 'info', text: sourceRef.label || 'мок' };
  }
  if (status === 'warning') return { tone: 'warning', text: sourceRef.label || 'проверить' };
  return { tone: 'neutral', text: sourceRef.label || 'нет связи' };
}

export function getDefaultActionDisabled(onAction) {
  return typeof onAction !== 'function';
}

export function getDirectorMapActionTarget({ item, action, isFinanceRole = () => false } = {}) {
  const isFinanceUser = typeof isFinanceRole === 'function' ? isFinanceRole() : Boolean(isFinanceRole);
  if (action === 'create_task') return 'ИИ-контроль';
  const signals = item?.signals || [];
  const types = signals.map(signal => signal.type);
  if (types.includes('material')) return 'Материалы';
  if (types.includes('document')) {
    return signals.some(signal => String(signal.title || '').includes('Входной')) ? 'Входной контроль' : 'АОСР';
  }
  if (types.includes('money')) return isFinanceUser ? 'Финансы' : 'Смета';
  if (types.includes('link_quality')) return 'Производство работ';
  if (action === 'review_link') return 'Производство работ';
  return 'Карта руководителя';
}
