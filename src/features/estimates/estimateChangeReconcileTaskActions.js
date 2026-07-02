import { parseAiTaskPayload } from '../../utils/aiControlDescriptionUtils';

export function createEstimateChangeReconcileTaskActions({
  API,
  user,
  estimatesList,
  estimateDiffBaseFor,
  buildEstimateDiff,
  includableEstimateChanges,
  estimateChangeAutoDecision,
  setUnexpectedWorksList,
  patchAiTaskSilent,
  fetchFn = fetch,
  alertFn = window.alert,
}) {
  const estimateChangeReconcileEstimatesForTask = (task) => {
    const payload = parseAiTaskPayload(task);
    const nextEstimate = (estimatesList || []).find(e => Number(e.id) === Number(payload.nextEstimateId));
    const baseEstimate = (estimatesList || []).find(e => Number(e.id) === Number(payload.baseEstimateId))
      || (nextEstimate ? estimateDiffBaseFor(nextEstimate) : null);
    return { payload, baseEstimate, nextEstimate };
  };

  const estimateChangeReconcileRowsForTask = (task) => {
    const { payload, baseEstimate, nextEstimate } = estimateChangeReconcileEstimatesForTask(task);
    if (payload.type !== 'estimate_change_reconcile') return [];
    if (!baseEstimate || !nextEstimate) return [];
    const diff = buildEstimateDiff(baseEstimate, nextEstimate);
    const projectName = payload.projectName || task.projectName || nextEstimate.projectName || baseEstimate.projectName || '';
    return includableEstimateChanges(projectName).map(change => estimateChangeAutoDecision(change, nextEstimate, diff));
  };

  const confirmEstimateChangeIncluded = async (task, decision) => {
    const payload = parseAiTaskPayload(task);
    const changeId = Number(decision?.change?.id);
    const estimateId = Number(payload.nextEstimateId);
    if (!changeId || !estimateId) return;

    const res = await fetchFn(API + '/estimates/' + estimateId + '/reconcile-changes', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({changeIds: [changeId], updatedBy: user.name}),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      alertFn(data.detail || 'Не удалось включить изменение в новую смету');
      return;
    }

    const included = new Set((data.includedChangeIds || []).map(Number));
    if (!included.size) return;

    setUnexpectedWorksList(prev => (prev || []).map(item => included.has(Number(item.id))
      ? {
          ...item,
          status: 'Включено в новую смету',
          includedInEstimateId: estimateId,
          reason: item.reason || ('Подтверждено при сверке с новой сметой №' + estimateId),
        }
      : item));

    const remaining = estimateChangeReconcileRowsForTask(task).filter(row => Number(row.change?.id) !== changeId);
    if (remaining.length === 0 && task?.id) await patchAiTaskSilent(task.id, {status: 'Закрыто'});
  };

  return {
    confirmEstimateChangeIncluded,
    estimateChangeReconcileEstimatesForTask,
    estimateChangeReconcileRowsForTask,
  };
}
