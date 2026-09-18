const completed = batch => (batch?.commands || []).slice(0, batch?.next || 0);

export function pruneDefectDraft(batch, path, draft) {
  const next = { ...draft, quantities: { ...draft.quantities } };
  completed(batch).filter(command => command.path === path + '/material-defects').forEach(({ payload }) => {
    if (next.reason === payload.reason) next.reason = '';
    if (JSON.stringify(next.photos) === JSON.stringify(payload.photos)) next.photos = [];
    (payload.items || []).forEach(item => {
      if (String(next.quantities[item.entryId]) === String(item.quantity)) delete next.quantities[item.entryId];
    });
  });
  return next;
}

export function acknowledgedPayment(batch, contractId, actId, amount, paidDate) {
  return completed(batch).some(command => command.path === '/brigade-payments'
    && command.payload.contractId === contractId && command.payload.actId === actId
    && String(command.payload.amount) === String(amount) && command.payload.paidDate === paidDate);
}
