import React from 'react';

const datePattern = /^\d{4}-\d{2}-\d{2}$/;
const dateLabel = value => value.split('-').reverse().join('.');
const states = { paid: 'Счёт полностью оплачен', cancelled: 'Счёт аннулирован',
  review_required: 'Срок оплаты требует проверки', waiting_acceptance: 'Ожидается приёмка — отсрочка ещё не началась' };

export default function SupplierPaymentDeadline({ value }) {
  if (value == null) return null;
  const valid = value.schemaVersion === 1 && Number.isSafeInteger(value.invoiceId) && value.invoiceId > 0
    && datePattern.test(value.asOf) && Array.isArray(value.stages) && value.stages.length <= 20
    && (value.status === 'active' || Object.hasOwn(states, value.status));
  if (!valid || (value.status === 'active' && (!value.stages.length || value.stages.some(s =>
    !s || typeof s.title !== 'string' || typeof s.amount !== 'string' || !/^\d+\.\d{2}$/.test(s.amount)
    || !Number.isInteger(s.daysAfter) || s.daysAfter < 0 || s.daysAfter > 3650
    || !datePattern.test(s.dueDate) || !Number.isSafeInteger(s.remainingDays))))) {
    return <p role="alert">Срок оплаты требует проверки</p>;
  }
  return <section aria-label="Отсрочка оплаты">
    <p><b>Отсрочка по счёту #{value.invoiceId}</b> · на {dateLabel(value.asOf)}</p>
    {value.status !== 'active' ? <p>{states[value.status]}</p> : <>
      <ul>{value.stages.map((stage, index) => <li key={index}>
        {stage.title} · {stage.amount} ₽ по графику · {stage.daysAfter} календарных дней после приёмки
        {' · до '}{dateLabel(stage.dueDate)}{' · '}
        <b>{stage.remainingDays < 0 ? `Срок прошёл ${-stage.remainingDays} дн.`
          : stage.remainingDays === 0 ? 'Срок сегодня' : `Осталось ${stage.remainingDays} дн.`}</b>
      </li>)}</ul>
      <small>Это график общего счёта, не отдельный долг каждой отгрузки. Частичные платежи по этапам ещё не распределены.</small>
    </>}
  </section>;
}
