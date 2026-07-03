import { useEffect } from 'react';

export function useEstimateExecutionFillPercentSync({
  selectedEstimate,
  selectedEstimateExecutionFillPercent,
  setExecutionPriceFillPercent,
}) {
  useEffect(() => {
    if (!selectedEstimate?.id || !selectedEstimateExecutionFillPercent) return;
    setExecutionPriceFillPercent(prev => (
      String(prev) === selectedEstimateExecutionFillPercent
        ? prev
        : selectedEstimateExecutionFillPercent
    ));
  }, [selectedEstimate?.id, selectedEstimateExecutionFillPercent, setExecutionPriceFillPercent]);
}
