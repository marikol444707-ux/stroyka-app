export function brigadeBalance(contract) {
  if (Number(contract.settlementVersion) === 2) {
    const summary = contract.settlementSummary;
    const fields = ['netAmount', 'paidAmount', 'remainingAmount', 'fineAmount'];
    if (!summary || summary.needsReconciliation || fields.some(key => summary[key] == null || !Number.isFinite(Number(summary[key])))) return {due: null, paid: null, remaining: null, fine: null, known: false};
    return {due: Number(summary.netAmount), paid: Number(summary.paidAmount),
      remaining: Number(summary.remainingAmount), fine: Number(summary.fineAmount), known: true};
  }
  const due = Number(contract.doneAmount || 0);
  const paid = Number(contract.paidAmount || 0);
  return {due, paid, remaining: Math.max(0, due - paid), fine: 0, known: true};
}

export const balanceMoney = value => value == null ? '—'
  : Number(value).toLocaleString('ru-RU', {maximumFractionDigits: 2}) + ' ₽';
