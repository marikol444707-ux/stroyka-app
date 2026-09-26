export const isSupplierLedgerPayment = payment => payment?.sourceKind === 'supplier_payment_ledger';

export const projectPaymentSignedAmountValue = (payment) => {
  const amount = Number(payment?.amount || 0);
  if (isSupplierLedgerPayment(payment)) return -amount;
  const note = String(payment?.note || '').trim().toLowerCase();
  const outgoing = (
    amount < 0
    || note.startsWith('оплата счёта')
    || note.startsWith('оплата бригаде')
    || note.startsWith('возмещение')
    || note.startsWith('выплата исполнителю')
  );
  return outgoing ? -Math.abs(amount) : Math.max(0, amount);
};

export const projectPaymentIncomingAmount = (payment) => isSupplierLedgerPayment(payment)
  ? 0 : Math.max(0, projectPaymentSignedAmountValue(payment));

// Ledger reversals reduce supplier expense; they are not customer receipts.
export const projectPaymentOutgoingAmount = payment => isSupplierLedgerPayment(payment)
  ? Number(payment.amount || 0) : Math.max(0, -projectPaymentSignedAmountValue(payment));

export const formatSignedRubValue = (amount) => (
  `${amount >= 0 ? '+' : '-'}${Math.round(Math.abs(amount)).toLocaleString('ru-RU')} ₽`
);
