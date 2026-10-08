import React from 'react';
import {brigadeBalance, balanceMoney} from './brigadeBalance';

const amount = value => {
  const parsed = Number(value || 0);
  return Number.isFinite(parsed) ? parsed : 0;
};

const money = balanceMoney;

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
  const balance = brigadeBalance(contract);
  const remaining = settlementV2 ? balance.remaining : Math.max(0, completed - paid);
  const estimate = items.reduce((sum, item) => sum + amount(item.quantity) * amount(item.priceSmeta), 0);
  const nextStep = contract.status === 'Аннулирован' ? 'Договор аннулирован'
    : !contract.contractScanUrl ? 'Загрузите подписанный договор'
      : plan <= 0 ? 'Добавьте работы в расчёт'
        : completed <= 0 ? 'Отмечайте выполнение работ'
          : !settlementV2 && !contract.actScanUrl ? 'Загрузите подписанный акт'
            : settlementV2 && !balance.known ? 'Откройте акты для проверки расчёта'
            : settlementV2 && amount(contract.settlementSummary?.unsignedActCount) > 0 ? 'Загрузите подписанный акт'
            : remaining > 0 ? 'Проверьте расчёты и оплату'
            : settlementV2 && amount(contract.settlementSummary?.grossAmount) < completed ? 'Сформируйте акт по выполненным работам'
              : completed < plan ? 'Продолжайте выполнение оставшихся работ'
                : settlementV2 ? 'Расчёт по актам завершён' : 'Выполненные работы оплачены';
  const figures = [
    ['По договору', money(plan)],
    ['Выполнено', money(completed)],
    ...(settlementV2 ? [['По актам после штрафов', money(balance.due)], ['Штрафы в актах', money(balance.fine)]] : []),
    ['Оплачено', money(settlementV2 ? balance.paid : paid)],
    [settlementV2 ? 'Остаток по актам' : 'Остаток к оплате', money(remaining)],
  ];

  return (
    <section aria-label="Сводка по исполнителю" style={{marginTop: '14px', paddingTop: '14px', borderTop: '1px solid ' + C.border}}>
      <div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(120px,1fr))', gap: '8px'}}>
        {figures.map(([label, value]) => <div key={label} style={{padding: '10px 12px', borderRadius: '10px', backgroundColor: C.bg, border: '1px solid ' + C.border}}>
          <span style={{display: 'block', color: C.textSec, fontSize: '11px', marginBottom: '3px'}}>{label}</span>
          <b style={{color: label.startsWith('Остаток') && remaining > 0 ? C.warning : C.text, fontSize: '15px'}}>{value}</b>
        </div>)}
      </div>
      {showFinance && !settlementV2 && plan > 0 && <p style={{color: C.textSec, fontSize: '12px', margin: '10px 0 0'}}>По смете заказчика: {money(estimate)} · разница: {money(estimate - plan)}</p>}
      <p style={{color: C.textSec, fontSize: '12px', margin: '10px 0 0'}}><b style={{color: C.text}}>Следующий шаг:</b> {nextStep}</p>
    </section>
  );
}
