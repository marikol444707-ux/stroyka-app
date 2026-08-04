import {
  buildEstimateDiff,
  estimateDiffTextKey,
  estimateKind,
  estimatePackage,
  estimateRowsForDiff,
} from './estimateUtils';
import { normalizeMeasure } from './measureUtils';

const estimateDiffMetaLabel = (estimate) => [
  estimate?.name || 'Смета',
  (estimate?.version || estimate?.versionLabel) ? 'v' + (estimate.version || estimate.versionLabel) : '',
  estimate?.status || '',
  estimate?.createdAt ? String(estimate.createdAt).slice(0, 10) : '',
].filter(Boolean).join(' · ');

const estimateDiffDocUnitKey = (unit) => estimateDiffTextKey(normalizeMeasure(1, unit).unit || unit || '');

const estimateDiffDocNameScore = (left, right) => {
  const leftKey = estimateDiffTextKey(left);
  const rightKey = estimateDiffTextKey(right);
  if (!leftKey || !rightKey) return 0;
  if (leftKey === rightKey) return 1;
  if (leftKey.includes(rightKey) || rightKey.includes(leftKey)) return 0.92;
  const leftWords = leftKey.split(' ').filter(word => word.length > 3);
  const rightWords = rightKey.split(' ').filter(word => word.length > 3);
  if (!leftWords.length || !rightWords.length) return 0;
  return leftWords.filter(word => rightWords.includes(word)).length / Math.max(leftWords.length, rightWords.length);
};

const estimateDiffChangeRequiredQty = (change) => {
  const type = change?.changeType || 'Работа вне сметы';
  const base = Number(change?.baseQuantity || 0);
  const delta = Number(change?.deltaQuantity || change?.quantity || 0);
  let raw = Number(change?.newRequiredQuantity || 0);
  if (raw <= 0 && (base > 0 || delta > 0)) raw = type === 'Исключение объёма' ? Math.max(0, base - delta) : base + delta;
  const normalized = normalizeMeasure(raw || delta, change?.unit);
  return { qty: Number(normalized.qty || 0), unit: normalized.unit || change?.unit || '' };
};

const findEstimateDiffChangeCandidate = ({ change, nextEstimate, diff }) => {
  const names = [...new Set([change?.estimateItemName, change?.description].map(value => String(value || '').trim()).filter(Boolean))];
  const unitKey = estimateDiffDocUnitKey(change?.unit);
  const nextRows = estimateRowsForDiff(nextEstimate);
  const priorityRows = [
    ...diff.added.map(row => ({ ...row, _kind: 'Добавлена' })),
    ...diff.changed.map(row => ({ ...row.next, _kind: 'Изменена' })),
    ...nextRows.map(row => ({ ...row, _kind: 'Найдена' })),
  ];
  let best = null;
  priorityRows.forEach(row => {
    if (!names.length) return;
    const rowUnitKey = estimateDiffDocUnitKey(row.unit);
    if (unitKey && rowUnitKey && unitKey !== rowUnitKey) return;
    const sectionBonus = estimateDiffTextKey(change?.sectionName) &&
      estimateDiffTextKey(change?.sectionName) === estimateDiffTextKey(row.section) ? 0.08 : 0;
    const score = Math.min(0.99, Math.max(...names.map(name => estimateDiffDocNameScore(name, row.name))) + sectionBonus);
    if (score >= 0.7 && (!best || score > best.score)) best = { row, score, kind: row._kind };
  });
  return best;
};

const signedEstimateChangeAmount = (change) => (
  Number(change?.total || 0) * (change?.changeType === 'Исключение объёма' ? -1 : 1)
);

const estimateDiffRowHasValue = (row = {}) => (
  Math.abs(Number(row.qty || 0)) > 0.0001 || Math.abs(Number(row.sum || 0)) > 0.005
);

export const estimateDiffChangedRows = (diff = {}, meta = {}) => [
  ...(diff.changed || []).map(({ base = {}, next = {}, impact = 0 }) => ({
    kind: 'changed',
    ...meta,
    section: next.section || base.section || '',
    name: next.name || base.name || '',
    unit: next.unit || base.unit || '',
    itemType: next.itemType || base.itemType || '',
    baseQty: Number(base.qty || 0),
    nextQty: Number(next.qty || 0),
    baseUnitPrice: Number(base.unitPrice || 0),
    nextUnitPrice: Number(next.unitPrice || 0),
    baseSum: Number(base.sum || 0),
    nextSum: Number(next.sum || 0),
    impact: Number(impact || 0),
  })),
  ...(diff.added || []).filter(estimateDiffRowHasValue).map((row) => ({
    kind: 'added',
    ...meta,
    section: row.section || '',
    name: row.name || '',
    unit: row.unit || '',
    itemType: row.itemType || '',
    baseQty: 0,
    nextQty: Number(row.qty || 0),
    baseUnitPrice: 0,
    nextUnitPrice: Number(row.unitPrice || 0),
    baseSum: 0,
    nextSum: Number(row.sum || 0),
    impact: Number(row.impact || 0),
  })),
  ...(diff.removed || []).filter(estimateDiffRowHasValue).map((row) => ({
    kind: 'removed',
    ...meta,
    section: row.section || '',
    name: row.name || '',
    unit: row.unit || '',
    itemType: row.itemType || '',
    baseQty: Number(row.qty || 0),
    nextQty: 0,
    baseUnitPrice: Number(row.unitPrice || 0),
    nextUnitPrice: 0,
    baseSum: Number(row.sum || 0),
    nextSum: 0,
    impact: Number(row.impact || 0),
  })),
];

export const buildProjectEstimateDiffSummaryPayload = ({ projectName = '', pairs = [] } = {}) => {
  const packageDiffs = (pairs || []).map(({ base, next }) => {
    const diff = buildEstimateDiff(base, next);
    const workPackage = estimatePackage(next || base);
    return {
      base,
      next,
      workPackage,
      diff,
      rows: estimateDiffChangedRows(diff, {
        workPackage,
        baseEstimateName: base?.name || '',
        nextEstimateName: next?.name || '',
        baseVersion: base?.version || base?.versionLabel || '',
        nextVersion: next?.version || next?.versionLabel || '',
      }),
    };
  });
  const rows = packageDiffs.flatMap(item => item.rows)
    .sort((left, right) => String(left.workPackage || '').localeCompare(String(right.workPackage || ''), 'ru')
      || Math.abs(Number(right.impact || 0)) - Math.abs(Number(left.impact || 0)));
  return {
    projectName: projectName || packageDiffs[0]?.next?.projectName || packageDiffs[0]?.base?.projectName || '',
    packageCount: packageDiffs.length,
    changedPackageCount: packageDiffs.filter(item => item.rows.length > 0).length,
    baseTotal: packageDiffs.reduce((sum, item) => sum + Number(item.diff.baseTotal || 0), 0),
    nextTotal: packageDiffs.reduce((sum, item) => sum + Number(item.diff.nextTotal || 0), 0),
    impact: packageDiffs.reduce((sum, item) => sum + Number(item.diff.impact || 0), 0),
    rows,
    packageDiffs,
  };
};

export const projectEstimateRevisionPairs = ({ project = {}, estimates = [], reconciliations = [] } = {}) => {
  const projectId = Number(project?.id || 0);
  const projectName = String(project?.name || '');
  const scoped = (estimates || []).filter((estimate) => {
    const estimateProjectId = Number(estimate?.projectId || 0);
    return projectId && estimateProjectId
      ? projectId === estimateProjectId
      : String(estimate?.projectName || estimate?.project || '') === projectName;
  });
  const groups = new Map();
  scoped.forEach((estimate) => {
    const key = `${estimateKind(estimate)}|${estimatePackage(estimate)}`;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(estimate);
  });
  const pairs = [];
  groups.forEach((group) => {
    const activeRows = group.filter(estimate => estimate.status === 'Активная')
      .sort((left, right) => Number(right.id || 0) - Number(left.id || 0));
    if (activeRows.length !== 1) return;
    const next = activeRows[0];
    const latestReconciliation = (reconciliations || [])
      .filter(rec => Number(rec?.nextEstimateId || 0) === Number(next.id || 0))
      .sort((left, right) => Number(right.id || 0) - Number(left.id || 0))[0];
    const reconciledBase = latestReconciliation
      ? group.find(estimate => Number(estimate.id || 0) === Number(latestReconciliation.baseEstimateId || 0))
      : null;
    const fallbackCandidates = group
      .filter(estimate => Number(estimate.id || 0) !== Number(next.id || 0));
    const fallbackBase = fallbackCandidates
      .filter(estimate => Number(estimate.id || 0) < Number(next.id || 0))
      .sort((left, right) => Number(right.id || 0) - Number(left.id || 0))[0]
      || fallbackCandidates.sort((left, right) => Number(right.id || 0) - Number(left.id || 0))[0];
    const base = reconciledBase || fallbackBase;
    if (base) pairs.push({ base, next });
  });
  return pairs.sort((left, right) => estimatePackage(left.next).localeCompare(estimatePackage(right.next), 'ru'));
};

export const buildEstimateDiffDocumentPayload = ({
  baseEstimate,
  nextEstimate,
  unexpectedWorksList = [],
  isApprovedEstimateChangeStatus,
  estimateChangeAutoDecision,
} = {}) => {
  const diff = buildEstimateDiff(baseEstimate, nextEstimate);
  const projectName = nextEstimate?.projectName || baseEstimate?.projectName || '';
  const relatedChanges = (unexpectedWorksList || []).filter(change =>
    change.projectName === projectName &&
    (isApprovedEstimateChangeStatus(change.status) || change.status === 'Включено в новую смету') &&
    (!change.includedInEstimateId || Number(change.includedInEstimateId) === Number(nextEstimate?.id))
  );
  const changeRows = relatedChanges.map(change => {
    const decision = estimateChangeAutoDecision(change, nextEstimate, diff);
    const fallbackCandidate = findEstimateDiffChangeCandidate({ change, nextEstimate, diff });
    const candidate = decision?.candidate ? { row: decision.candidate, score: decision.score || 0 } : fallbackCandidate;
    const required = estimateDiffChangeRequiredQty(change);
    const included = change.status === 'Включено в новую смету' && Number(change.includedInEstimateId) === Number(nextEstimate?.id);
    const covered = included || Boolean(decision?.autoInclude);
    const status = included
      ? 'Уже включено в новую смету'
      : decision?.autoInclude
        ? 'Новая смета закрывает изменение: ' + (decision.reason || 'найдено совпадение')
        : candidate?.row
          ? 'Похоже найдено, нужна проверка: ' + (decision?.reason || 'совпадение не подтверждено автоматически')
          : 'Остаётся отдельной допработой вне новой сметы';
    return {
      change,
      candidate: candidate?.row || null,
      score: candidate?.score || 0,
      required,
      status,
      covered,
      needsReview: !covered && Boolean(candidate?.row),
      amount: signedEstimateChangeAmount(change),
    };
  });
  const changeSummary = {
    total: changeRows.length,
    covered: changeRows.filter(row => row.covered).length,
    review: changeRows.filter(row => row.needsReview).length,
    outside: changeRows.filter(row => !row.covered).length,
    outsideSum: changeRows.filter(row => !row.covered).reduce((sum, row) => sum + row.amount, 0),
  };
  return {
    baseMeta: estimateDiffMetaLabel(baseEstimate),
    nextMeta: estimateDiffMetaLabel(nextEstimate),
    projectName,
    estimateType: estimateKind(nextEstimate || baseEstimate),
    workPackage: estimatePackage(nextEstimate || baseEstimate),
    diff,
    changeRows,
    changeSummary,
  };
};
