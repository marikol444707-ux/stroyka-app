export function createEstimateVersionActions({
  API,
  alertFn = window.alert,
  estimateVersionRequestRef,
  fetchFn = fetch,
  readApiResult,
  selectedEstimate,
  setEstimateVersions,
  setSelectedVersionsToCompare,
  setShowVersionHistory,
}) {
  const requestRef = estimateVersionRequestRef || { current: 0 };

  const handleOpenSelectedEstimateHistory = async () => {
    if (!selectedEstimate?.id) return false;
    requestRef.current += 1;
    const requestId = requestRef.current;
    const estimateId = selectedEstimate.id;
    setEstimateVersions([]);
    setSelectedVersionsToCompare([]);
    try {
      const versions = await readApiResult(
        await fetchFn(API + '/estimates/' + estimateId + '/versions'),
      );
      if (requestRef.current !== requestId) return false;
      setEstimateVersions(Array.isArray(versions) ? versions : []);
      setShowVersionHistory(true);
      return true;
    } catch (error) {
      if (requestRef.current === requestId) alertFn('Не удалось загрузить историю');
      return false;
    }
  };

  return { handleOpenSelectedEstimateHistory };
}
