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
