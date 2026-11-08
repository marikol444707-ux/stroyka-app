import { estimateMutationPayload, estimateSaveFailure, readEstimateMutationResponse } from './estimateSaveClient';

export async function persistEstimateAction({
  API,
  est,
  beginEstimateSave,
  estimateListRef,
  options = {},
  setEstimatesList,
  estimateListWithUpdatedEstimate,
  estimatesList,
  fetchFn = fetch,
  queueEstimateNormReviewTask,
  queueEstimateQualityReviewTask,
}) {
  if (!est || !est.id) return;
  const operation = beginEstimateSave?.(est, options);
  let acknowledged = est;
  const isCurrent = () => Boolean(operation?.isCurrent())
    && (options.source !== 'list' || estimateListRef?.current.find(item => item.id === est.id) === acknowledged);
  let data;
  try {
    const payload = estimateMutationPayload(est, est);
    data = await readEstimateMutationResponse(await fetchFn(API + '/estimates/' + est.id, {
      method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload),
    }));
  } catch (error) {
    if (isCurrent()) operation.finish(estimateSaveFailure(error));
    return {ok: false, error, stale: !isCurrent(), isCurrent};
  }
  // Without an editor/session token there is no safe basis for background reviews.
  if (!isCurrent()) return {ok: true, stale: true, revision: data.revision, isCurrent};
  const saved = {...est, revision: data.revision};
  operation.finish({status: 'saved', revision: data.revision});
  setEstimatesList?.(prev => prev.map(item => item.id === est.id ? saved : item));
  acknowledged = saved;
  const nextEstimates = estimateListWithUpdatedEstimate ? estimateListWithUpdatedEstimate(saved) : estimatesList;
  try {
    await queueEstimateQualityReviewTask(saved, 'Смета сохранена');
    if (isCurrent()) await queueEstimateNormReviewTask(saved, 'Смета сохранена', nextEstimates);
  } catch (error) {
    // The PUT succeeded; a background review failure must not change save status.
  }
  return {ok: true, revision: data.revision, estimate: saved, isCurrent};
}
