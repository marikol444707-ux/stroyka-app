export async function persistEstimateAction({
  API,
  est,
  estimateListWithUpdatedEstimate,
  estimatesList,
  fetchFn = fetch,
  queueEstimateNormReviewTask,
  queueEstimateQualityReviewTask,
}) {
  if (!est || !est.id) return;
  try {
    const res = await fetchFn(API + '/estimates/' + est.id, {method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(est)});
    if (res.ok) {
      const nextEstimates = estimateListWithUpdatedEstimate ? estimateListWithUpdatedEstimate(est) : estimatesList;
      await queueEstimateQualityReviewTask(est, 'Смета сохранена');
      await queueEstimateNormReviewTask(est, 'Смета сохранена', nextEstimates);
    }
  } catch (e) {}
}
