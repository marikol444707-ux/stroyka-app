import React from 'react';

const amount = value => {
  const parsed = Number(value || 0);
  return Number.isFinite(parsed) ? parsed : 0;
};

const money = value => Math.round(value).toLocaleString('ru-RU') + ' ₽';

export default function ProjectBrigadeOverview({contract, items = [], payments = [], showFinance = false, C}) {
  const settlementV2 = Number(contract.settlementVersion) === 2;
  const plan = settlementV2
    ? amount(contract.planAmount)
    : items.reduce((sum, item) => sum + amount(item.quantity) * amount(item.priceBrigade), 0);
  const completed = settlementV2
    ? amount(contract.doneAmount)
    : items.reduce((sum, item) => sum + amount(item.doneQuantity) * amount(item.priceBrigade), 0);
  const paid = settlementV2
    ? amount(contract.paidAmount)
    : payments.reduce((sum, payment) => sum + amount(payment.amount), 0);
  const remaining = Math.max(0, completed - paid);
  const estimate = items.reduce((sum, item) => sum + amount(item.quantity) * amount(item.priceSmeta), 0);
  const nextStep = contract.status === 'Аннулирован' ? 'Договор аннулирован'
    : !contract.contractScanUrl ? 'Загрузите подписанный договор'
      : plan <= 0 ? 'Добавьте работы в расчёт'
        : completed <= 0 ? 'Отмечайте выполнение работ'
          : !settlementV2 && !contract.actScanUrl ? 'Загрузите подписанный акт'
            : remaining > 0 ? 'Проверьте расчёты и оплату'
              : 'Расчёты закрыты';
  const figures = [
    ['По договору', money(plan)],
    ['Выполнено', money(completed)],
    ['Оплачено', money(paid)],
    ['Остаток к оплате', money(remaining)],
  ];

  return (
    <section aria-label="Сводка по исполнителю" style={{marginTop: '14px', paddingTop: '14px', borderTop: '1px solid ' + C.border}}>
      <div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(120px,1fr))', gap: '8px'}}>
        {figures.map(([label, value]) => <div key={label} style={{padding: '10px 12px', borderRadius: '10px', backgroundColor: C.bg, border: '1px solid ' + C.border}}>
          <span style={{display: 'block', color: C.textSec, fontSize: '11px', marginBottom: '3px'}}>{label}</span>
          <b style={{color: label === 'Остаток к оплате' && remaining > 0 ? C.warning : C.text, fontSize: '15px'}}>{value}</b>
        </div>)}
      </div>
      {showFinance && !settlementV2 && plan > 0 && <p style={{color: C.textSec, fontSize: '12px', margin: '10px 0 0'}}>По смете заказчика: {money(estimate)} · разница: {money(estimate - plan)}</p>}
      <p style={{color: C.textSec, fontSize: '12px', margin: '10px 0 0'}}><b style={{color: C.text}}>Следующий шаг:</b> {nextStep}</p>
    </section>
  );
}
