import { estimateSectionsOf, estimateItemTotal, isEstimateWorkItem, estimatePackage } from '../../utils/estimateUtils';
import { customerProjectRecord } from './projectSelection';

export function customerProgress(project, estimates = [], journal = []) {
  if (estimates.some(estimate => estimate.sectionsLoaded !== true)) {
    return { plan: null, done: null, percent: null, source: 'loading' };
  }
  if (new Set(estimates.map(estimatePackage)).size !== estimates.length) {
    return { plan: null, done: null, percent: null, source: 'conflict' };
  }
  const lines = new Map();
  let plan = 0;
  for (const estimate of estimates) {
    for (const [sectionIndex, section] of estimateSectionsOf(estimate).entries()) {
      for (const [itemIndex, item] of (section.items || []).entries()) {
        if (!isEstimateWorkItem(item, section.name)) continue;
        const quantity = Number(item.quantity);
        const total = Number(estimateItemTotal(item));
        if (!Number.isFinite(quantity) || quantity <= 0 || !Number.isFinite(total) || total <= 0) continue;
        lines.set(`${estimate.id}:${sectionIndex}:${itemIndex}`, { quantity, total, done: 0 });
        plan += total;
      }
    }
  }
  if (!plan) {
    const value = project?.progress;
    const percent = value !== null && value !== undefined && value !== '' && Number.isFinite(Number(value))
      ? Math.max(0, Math.min(100, Number(value))) : null;
    return { plan: 0, done: null, percent, source: 'manual' };
  }
  let unmatched = false;
  for (const entry of journal) {
    if (!customerProjectRecord(entry, project) || entry.status !== 'Подтверждено') continue;
    const line = lines.get(entry.estimateItemKey);
    const quantity = Number(entry.quantity);
    if (entry.unexpectedWorkId || !line || !Number.isFinite(quantity) || quantity < 0) {
      unmatched = true;
      continue;
    }
    line.done += quantity;
  }
  if (unmatched) return { plan, done: null, percent: null, source: 'unlinked' };
  const done = [...lines.values()].reduce((sum, line) => sum + Math.min(line.done, line.quantity) / line.quantity * line.total, 0);
  return { plan, done, percent: Math.round(done / plan * 100), source: 'confirmed' };
}
