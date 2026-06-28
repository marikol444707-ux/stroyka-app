import {
  clampPercent,
  getSignalCounts,
} from './directorMapRules';

const SOURCE_KEYS = [
  'stage',
  'estimate',
  'workJournal',
  'supply',
  'warehouse',
  'documents',
  'payments',
];

function normalizeSignals(signals = []) {
  return signals.map((signal, index) => ({
    id: signal.id || `signal-${index + 1}`,
    type: signal.type || 'info',
    severity: signal.severity || signal.tone || 'info',
    title: signal.title || signal.text || 'Сигнал',
    explanation: signal.explanation || signal.text || '',
    nextAction: signal.nextAction || null,
  }));
}

function normalizeSourceRefs(sourceRefs = {}) {
  return SOURCE_KEYS.reduce((acc, key) => {
    acc[key] = sourceRefs[key] || { status: 'missing', futureSource: '' };
    return acc;
  }, {});
}

function normalizeSupplyChain(supplyChain = []) {
  return supplyChain.map((step, index) => ({
    id: step.id || step.step || `step-${index + 1}`,
    step: step.step || `step-${index + 1}`,
    title: step.title || `Шаг ${index + 1}`,
    status: step.status || 'info',
    value: step.value || '',
    description: step.description || '',
  }));
}

function normalizeItem(item = {}, index = 0) {
  const plannedProgress = clampPercent(item.plannedProgress);
  const factProgress = clampPercent(item.factProgress);
  const timeline = item.timeline || {};
  return {
    id: item.id || `director-item-${index + 1}`,
    type: item.type || 'work_node',
    title: item.title || 'Этап без названия',
    workPackage: item.workPackage || item.work_package || 'Основная',
    zone: item.zone || item.roomName || 'Без зоны',
    status: item.status || 'На проверке',
    priority: item.priority || 'normal',
    responsible: item.responsible || 'Не назначен',
    startDate: item.startDate || '',
    endDate: item.endDate || '',
    plannedProgress,
    factProgress,
    lagPercent: Math.max(0, plannedProgress - factProgress),
    reviewState: item.reviewState || 'ok',
    money: {
      plan: Number(item.money?.plan || 0),
      fact: Number(item.money?.fact || 0),
      obligations: Number(item.money?.obligations || 0),
      factSourceRule: item.money?.factSourceRule || 'project_payments_only',
    },
    sourceRefs: normalizeSourceRefs(item.sourceRefs),
    signals: normalizeSignals(item.signals),
    supplyChain: normalizeSupplyChain(item.supplyChain),
    tags: item.tags || [],
    timeline: {
      startPercent: clampPercent(timeline.startPercent ?? index * 18),
      widthPercent: Math.max(10, Math.min(36, Number(timeline.widthPercent || 18))),
    },
  };
}

function buildSummary(contractSummary = {}, items = []) {
  const counts = getSignalCounts(items);
  const average = items.length
    ? Math.round(items.reduce((sum, item) => sum + item.factProgress, 0) / items.length)
    : 0;
  const planned = items.length
    ? Math.round(items.reduce((sum, item) => sum + item.plannedProgress, 0) / items.length)
    : 0;
  const moneyFact = items.reduce((sum, item) => sum + item.money.fact, 0);
  const obligations = items.reduce((sum, item) => sum + item.money.obligations, 0);
  return {
    plannedProgress: contractSummary.plannedProgress ?? planned,
    factProgress: contractSummary.factProgress ?? average,
    lagPercent: contractSummary.lagPercent ?? Math.max(0, planned - average),
    redSignals: contractSummary.redSignals ?? counts.red,
    yellowSignals: contractSummary.yellowSignals ?? counts.yellow,
    reviewItems: contractSummary.reviewItems ?? counts.review,
    moneyFact: contractSummary.moneyFact ?? moneyFact,
    moneyObligations: contractSummary.moneyObligations ?? obligations,
  };
}

export function adaptDirectorMapContract(contract = {}) {
  const items = (contract.items || []).map(normalizeItem);
  return {
    contractVersion: contract.contractVersion || 'director-map.local',
    mode: contract.mode || 'sandbox_unbound',
    integrationPolicy: contract.integrationPolicy || {},
    project: {
      id: contract.project?.id || 'mock-project',
      name: contract.project?.name || 'Демо-объект',
      status: contract.project?.status || 'В работе',
      deadline: contract.project?.deadline || '',
      directorViewTitle: contract.project?.directorViewTitle || 'Карта руководителя',
    },
    summary: buildSummary(contract.summary || {}, items),
    items,
    unlinked: contract.unlinked || {},
    guards: contract.guards || [],
  };
}
