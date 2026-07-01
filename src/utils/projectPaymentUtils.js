export const projectPaymentSignedAmountValue = (payment) => {
  const amount = Number(payment?.amount || 0);
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

export const projectPaymentIncomingAmount = (payment) => Math.max(0, projectPaymentSignedAmountValue(payment));

export const formatSignedRubValue = (amount) => (
  `${amount >= 0 ? '+' : '-'}${Math.round(Math.abs(amount)).toLocaleString('ru-RU')} ₽`
);
