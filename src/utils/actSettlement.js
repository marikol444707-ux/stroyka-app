export const actCashPaid = act => Number(act?.paidAmount ?? act?.paid_amount ?? 0);
export const actAdvance = act => Number(act?.advanceAmount || 0);
export const actRetention = act => Math.max(0, Number(act?.retentionOutstanding ?? (Number(act?.retentionAmount || 0) - Number(act?.retentionReleased || 0))));
export const actToolDeduction = act => Number(act?.toolDeductionAmount || 0);
export const actRemaining = act => Math.max(0, Number(act?.remainingAmount ?? (
  Number(act?.totalAmount ?? act?.total_amount ?? 0) - actCashPaid(act) - actAdvance(act) - actRetention(act) - actToolDeduction(act)
)));
