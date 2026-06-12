import React from 'react';

export default function AccountingSummaryPanel({
  C,
  card,
  projects,
  projectPayments,
  projectPaymentInAmount,
  ownExpenses,
  accountablePayments,
  supplierInvoices,
  brigadeContracts,
  piecework,
  isLeadership,
}) {
  const activeProjectsCount = (projects || []).filter(project => project.status === 'В работе').length;
  const totalBudget = (projects || []).reduce((sum, project) => sum + Number(project.budget || 0), 0);
  const totalPayIn = (projectPayments || []).reduce((sum, payment) => sum + projectPaymentInAmount(payment), 0);
  const totalOwnExpenses = (ownExpenses || []).reduce((sum, expense) => sum + Number(expense.amount || 0), 0);
  const totalAccountable = (accountablePayments || []).reduce((sum, payment) => sum + Number(payment.amount || 0), 0);
  const totalSuppliers = (supplierInvoices || []).reduce((sum, invoice) => sum + Number(invoice.paidAmount || 0), 0);
  const totalBrigades = (brigadeContracts || []).reduce((sum, contract) => sum + Number(contract.paidAmount || 0), 0);
  const totalPiecework = (piecework || []).reduce((sum, row) => sum + Number(row.total || 0), 0);
  const totalExpenses = totalOwnExpenses + totalAccountable + totalSuppliers + totalBrigades;
  const netProfit = totalPayIn - totalExpenses;

  const cards = [
    { label: 'Активных проектов', value: activeProjectsCount + ' из ' + (projects || []).length, color: C.accent },
    { label: 'Общий бюджет', value: Math.round(totalBudget).toLocaleString('ru-RU') + ' ₽', color: C.text },
    { label: 'Поступило от заказчиков', value: Math.round(totalPayIn).toLocaleString('ru-RU') + ' ₽', color: C.success },
    { label: 'Оплачено поставщикам', value: Math.round(totalSuppliers).toLocaleString('ru-RU') + ' ₽', color: C.warning },
    { label: 'Оплачено бригадам', value: Math.round(totalBrigades).toLocaleString('ru-RU') + ' ₽', color: C.warning },
    { label: 'Возмещения сотрудникам', value: Math.round(totalOwnExpenses).toLocaleString('ru-RU') + ' ₽', color: C.warning },
    { label: 'Подотчётные на руках', value: Math.round(totalAccountable).toLocaleString('ru-RU') + ' ₽', color: C.warning },
    ...(isLeadership ? [{ label: 'Всего расходов', value: Math.round(totalExpenses).toLocaleString('ru-RU') + ' ₽', color: C.danger }] : []),
    ...(isLeadership ? [{ label: 'Чистая прибыль', value: Math.round(netProfit).toLocaleString('ru-RU') + ' ₽', color: netProfit >= 0 ? C.success : C.danger }] : []),
    { label: 'Зарплата-сделка (начислено)', value: Math.round(totalPiecework).toLocaleString('ru-RU') + ' ₽', color: C.textSec },
  ];

  return (
    <div>
      <b style={{ color: C.text, fontSize: '15px', fontWeight: '700', display: 'block', marginBottom: '15px' }}>
        📊 Финансовая сводка по компании
      </b>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(180px,1fr))', gap: '12px', marginBottom: '20px' }}>
        {cards.map(cardItem => (
          <div key={cardItem.label} style={{ ...card, padding: '16px' }}>
            <p style={{ color: C.textSec, fontSize: '11px', margin: '0 0 6px' }}>{cardItem.label}</p>
            <b style={{ color: cardItem.color, fontSize: '18px' }}>{cardItem.value}</b>
          </div>
        ))}
      </div>
    </div>
  );
}
