import React from 'react';
import {
  ACCOUNTING_INVOICE_STATUSES,
  accountingStatusGroupLabels,
  buildAccountingInvoiceRows,
} from '../utils/accountingInvoices';

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
  invoices,
  warehouseInvoiceEstimateControl,
  setAccountingTab,
}) {
  const projectPaymentSignedAmount = (payment) => {
    const amount = Number(payment?.amount || 0);
    const note = String(payment?.note || '').trim().toLowerCase();
    const outgoing = amount < 0 ||
      note.startsWith('оплата счёта') ||
      note.startsWith('оплата бригаде') ||
      note.startsWith('возмещение') ||
      note.startsWith('выплата исполнителю');
    return outgoing ? -Math.abs(amount) : Math.max(0, amount);
  };

  const activeProjectsCount = (projects || []).filter(project => project.status === 'В работе').length;
  const totalBudget = (projects || []).reduce((sum, project) => sum + Number(project.budget || 0), 0);
  const totalPayIn = (projectPayments || []).reduce((sum, payment) => sum + projectPaymentInAmount(payment), 0);
  const totalProjectPaymentsOut = (projectPayments || []).reduce((sum, payment) => {
    const signed = projectPaymentSignedAmount(payment);
    return signed < 0 ? sum + Math.abs(signed) : sum;
  }, 0);
  const pendingOwnExpenses = (ownExpenses || [])
    .filter(expense => expense.status === 'Ожидает')
    .reduce((sum, expense) => sum + Number(expense.amount || 0), 0);
  const reimbursedOwnExpenses = (ownExpenses || [])
    .filter(expense => expense.status === 'Возмещено')
    .reduce((sum, expense) => sum + Number(expense.amount || 0), 0);
  const totalAccountable = (accountablePayments || []).reduce((sum, payment) => sum + Number(payment.amount || 0), 0);
  const totalSuppliers = (supplierInvoices || []).reduce((sum, invoice) => sum + Number(invoice.paidAmount || 0), 0);
  const totalBrigades = (brigadeContracts || []).reduce((sum, contract) => sum + Number(contract.paidAmount || 0), 0);
  const totalPiecework = (piecework || []).reduce((sum, row) => sum + Number(row.total || 0), 0);
  const totalExpenses = totalAccountable + totalProjectPaymentsOut;
  const netProfit = totalPayIn - totalExpenses;
  const accountingInvoiceRows = React.useMemo(
    () => buildAccountingInvoiceRows(invoices, warehouseInvoiceEstimateControl),
    [invoices, warehouseInvoiceEstimateControl]
  );
  const invoiceQueueCards = ACCOUNTING_INVOICE_STATUSES
    .map(status => {
      const rows = accountingInvoiceRows.filter(row => row.status === status);
      const amount = rows.reduce((sum, row) => sum + (row.status === 'Оплачена' ? row.paidAmount : row.debt || row.amount), 0);
      return { status, count: rows.length, amount };
    })
    .filter(item => item.count > 0 || ['Нет фото', 'На проверке', 'К оплате'].includes(item.status));

  const cards = [
    { label: 'Активных проектов', value: activeProjectsCount + ' из ' + (projects || []).length, color: C.accent },
    { label: 'Общий бюджет', value: Math.round(totalBudget).toLocaleString('ru-RU') + ' ₽', color: C.text },
    { label: 'Поступило от заказчиков', value: Math.round(totalPayIn).toLocaleString('ru-RU') + ' ₽', color: C.success },
    { label: 'Оплачено поставщикам', value: Math.round(totalSuppliers).toLocaleString('ru-RU') + ' ₽', color: C.warning },
    { label: 'Оплачено бригадам', value: Math.round(totalBrigades).toLocaleString('ru-RU') + ' ₽', color: C.warning },
    { label: 'Платежи по журналу', value: Math.round(totalProjectPaymentsOut).toLocaleString('ru-RU') + ' ₽', color: C.danger },
    { label: 'К возмещению сотрудникам', value: Math.round(pendingOwnExpenses).toLocaleString('ru-RU') + ' ₽', color: C.warning },
    { label: 'Возмещено сотрудникам', value: Math.round(reimbursedOwnExpenses).toLocaleString('ru-RU') + ' ₽', color: C.textSec },
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
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(150px,1fr))', gap: '10px', marginBottom: '20px' }}>
        {invoiceQueueCards.map(item => {
          const color = item.status === 'Нет фото' ? C.danger : item.status === 'К оплате' ? C.accent : item.status === 'Оплачена' ? C.success : C.warning;
          const bg = item.status === 'Нет фото' ? C.dangerLight : item.status === 'К оплате' ? C.accentLight : item.status === 'Оплачена' ? C.successLight : C.warningLight;
          const border = item.status === 'Нет фото' ? C.dangerBorder : item.status === 'К оплате' ? C.accentBorder : item.status === 'Оплачена' ? C.successBorder : C.warningBorder;
          return (
            <button
              key={item.status}
              onClick={() => setAccountingTab && setAccountingTab('incoming')}
              style={{ ...card, padding: '14px', textAlign: 'left', cursor: 'pointer', backgroundColor: bg, border: '1.5px solid ' + border }}
            >
              <p style={{ color, fontSize: '11px', margin: '0 0 5px', fontWeight: 800 }}>{accountingStatusGroupLabels[item.status]}</p>
              <b style={{ color, fontSize: '18px' }}>{item.count}</b>
              <span style={{ display: 'block', color, fontSize: '11px', marginTop: '3px' }}>{Math.round(item.amount).toLocaleString('ru-RU') + ' ₽'}</span>
            </button>
          );
        })}
      </div>
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
