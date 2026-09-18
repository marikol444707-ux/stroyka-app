const equal = (left, right) => JSON.stringify(left) === JSON.stringify(right);

export function clearSubmittedDrafts(batch, bindings) {
  const drafts = (batch.commands || []).slice(0, batch.next).flatMap(command => command.drafts || []);
  const prune = (previous, kind, field) => {
    const next = { ...previous };
    drafts.filter(draft => draft.kind === kind && Object.prototype.hasOwnProperty.call(draft, field)).forEach(draft => {
      if (Object.prototype.hasOwnProperty.call(next, draft.key) && equal(next[draft.key], draft[field])) delete next[draft.key];
    });
    return next;
  };
  bindings.setEstimateDoneDrafts?.(previous => prune(previous, 'estimate', 'done'));
  bindings.setEstimateWorkMaterials?.(previous => prune(previous, 'estimate', 'materials'));
  bindings.setEstimateWorkParams?.(previous => prune(previous, 'estimate', 'params'));
  bindings.setSelectedWorks?.(previous => prune(previous, 'pricelist', 'selection'));
  if (bindings.estimateDraftValueRef) {
    bindings.estimateDraftValueRef.current = prune(bindings.estimateDraftValueRef.current, 'estimate', 'done');
  }
}
