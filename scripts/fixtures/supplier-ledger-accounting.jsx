import React from 'react';
import AccountingSummaryPanel from '../../src/components/AccountingSummaryPanel';
import AccountingPaymentsPanel from '../../src/components/AccountingPaymentsPanel';
import AccountingDocumentsPanel from '../../src/components/AccountingDocumentsPanel';
import ProjectScheduleTab from '../../src/features/projects/ProjectScheduleTab';
import { projectPaymentIncomingAmount } from '../../src/utils/projectPaymentUtils';

const C = { text: '#182536', textSec: '#354961', textMuted: '#526477', border: '#cbd5e1',
  bg: '#f6f8fa', bgCard: '#fff', danger: '#a12622', success: '#166534', info: '#075985' };
const card = { border: '1px solid #cbd5e1', padding: 16, marginBottom: 16, background: '#fff' };
const project = { id: 10, companyId: 2, name: 'Тестовый объект', status: 'В работе' };

export default function LedgerAccountingPreview() {
  const [reversed, setReversed] = React.useState(false);
  const [expanded, setExpanded] = React.useState(null);
  const base = { id: 1, companyId: 2, projectId: 10, projectName: project.name,
    sourceKind: 'supplier_payment_ledger', operationKind: 'payment', amount: 100,
    note: 'Оплата бригаде — произвольное основание платежа поставщику', date: '2026-09-18' };
  const payments = [base, ...(reversed ? [{ ...base, id: 2, operationKind: 'reversal', amount: -100 }] : [])];
  const materialControl = () => ({ outsideRows: [], stockMismatchRows: [], toBuyRows: [] });
  return <main style={{ padding: 24, fontFamily: 'sans-serif', background: '#f6f8fa' }}>
    <h1>Тест бухгалтерских итогов</h1>
    <p>Вымышленный платёж поставщику: 100 ₽. Назначение намеренно похоже на выплату бригаде.</p>
    <label><input type="checkbox" checked={reversed} onChange={event => setReversed(event.target.checked)} />Добавить сторно 100 ₽</label>
    <h2>Сводка</h2>
    <AccountingSummaryPanel C={C} card={card} projects={[]} invoices={[]}
      projectPaymentInAmount={projectPaymentIncomingAmount} projectPayments={payments} />
    <h2>Оплаты по объектам</h2>
    <AccountingPaymentsPanel C={C} card={card} inp={{}} btnO={{}} btnG={{}} btnGr={{}}
      matchSearch={() => true} listSearch="" setListSearch={() => {}} toNum={Number} user={{}}
      projects={[project]} companyContext={{ companies: [{ companyId: 2, companyName: 'Тестовая компания' }] }}
      projectPaymentInAmount={projectPaymentIncomingAmount} expandedProject={expanded} setExpandedProject={setExpanded}
      supplierInvoices={[]} projectPayments={payments} />
    <h2>Документы объекта</h2>
    <AccountingDocumentsPanel C={C} card={card} btnO={{}} btnG={{}} btnB={{}}
      accountingDocProject={project.name} projects={[project]} projectPayments={payments}
      projectPlanDone={() => ({ done: 0 })} badge={() => null} materialControlSummaryForProject={materialControl} />
    <h2>История в графике</h2>
    <ProjectScheduleTab C={C} ProjectScheduleSummaryPanel={() => null} project={project}
      projectStages={[{ id: 1, name: 'Тестовый этап', progress: 0, projectName: project.name,
        startDate: '2026-09-01', endDate: '2026-09-30' }]}
      projectPayments={payments} projectPlanDone={() => ({})} projectRealProgress={() => 0}
      materialControlSummaryForProject={materialControl} />
  </main>;
}
