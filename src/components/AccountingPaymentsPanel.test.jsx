import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import AccountingPaymentsPanel from './AccountingPaymentsPanel';
import { projectPaymentIncomingAmount } from '../utils/projectPaymentUtils';

test('ledger payment and reversal net expenses without customer income', () => {
  render(<CompanyGroups extra={{ projectPaymentInAmount: projectPaymentIncomingAmount,
    projectPayments: ['payment', 'reversal'].map((operationKind, i) => ({ id: i + 1,
      companyId: 2, projectId: 10, projectName: 'Жилой комплекс', sourceKind: 'supplier_payment_ledger',
      operationKind, amount: i ? -100 : 100, note: 'Аванс' })) }} />);
  const group = screen.getByRole('button', { name: /Строй А/ });
  expect(group).toHaveTextContent('Поступило: 0 ₽ · Оплачено: 0 ₽');
  fireEvent.click(group);
  expect(screen.getByText(/Сторно.*Аванс/)).toBeInTheDocument();
  expect(screen.getByText('-100 ₽')).toBeInTheDocument();
});

const deadline = { schemaVersion: 1, invoiceId: 10, asOf: '2026-09-15', status: 'active',
  stages: [{ title: 'Остаток', amount: '100.00', daysAfter: 30, dueDate: '2026-09-22', remainingDays: 7 }] };

function show(value = deadline, changes = {}, setExpandedProject = () => {}) {
  return render(<AccountingPaymentsPanel C={{}} card={{}} inp={{}} btnO={{}} btnG={{}} btnGr={{}}
    matchSearch={() => true} listSearch="" setListSearch={() => {}} projects={[{ id: 10, companyId: 2, name: 'Объект А' }]}
    toNum={Number} user={{}} projectPaymentInAmount={row => row.amount}
    expandedProject={'pay-' + JSON.stringify([2, 'project', 10])} setExpandedProject={setExpandedProject}
    supplierInvoices={[{ id: 10, companyId: 2, projectId: 10, projectName: 'Объект А', supplierName: 'Поставщик',
      invoiceNumber: 'СЧ-10', totalAmount: 200, paidAmount: 100, paymentDeadline: value, ...changes }]} />);
}

function CompanyGroups({ extra = {} }) {
  const [expanded, setExpanded] = React.useState(null);
  const [search, setSearch] = React.useState('');
  return <AccountingPaymentsPanel C={{}} card={{}} inp={{}} btnO={{}} btnG={{}} btnGr={{}}
    matchSearch={(query, value) => value.includes(query)} listSearch={search} setListSearch={setSearch} toNum={Number} user={{}}
    projects={[{ id: 10, companyId: 2, name: 'Жилой комплекс' }, { id: 20, companyId: 3, name: 'Жилой комплекс' }]}
    companyContext={{ companies: [{ companyId: 2, companyName: 'Строй А' }, { companyId: 3, companyName: 'Строй Б' }] }}
    projectPaymentInAmount={row => row.amount} expandedProject={expanded} setExpandedProject={setExpanded}
    supplierInvoices={[
      { id: 1, companyId: 2, projectId: 10, projectName: 'Жилой комплекс', invoiceNumber: 'А-1', totalAmount: 200, paidAmount: 50 },
      { id: 2, companyId: 3, projectId: 20, projectName: 'Жилой комплекс', invoiceNumber: 'Б-1', totalAmount: 500, paidAmount: 200 },
    ]} {...extra} />;
}

test('same-name objects from two companies keep independent debt and expansion', () => {
  render(<CompanyGroups />);
  const first = screen.getByRole('button', { name: /Строй А/ });
  const second = screen.getByRole('button', { name: /Строй Б/ });
  expect(first).toHaveTextContent('150 ₽');
  expect(second).toHaveTextContent('300 ₽');
  expect(screen.getByText('450 ₽')).toBeInTheDocument();
  fireEvent.click(first);
  expect(screen.getByText(/А-1/)).toBeInTheDocument();
  expect(screen.queryByText(/Б-1/)).not.toBeInTheDocument();
  fireEvent.click(second);
  expect(screen.queryByText(/А-1/)).not.toBeInTheDocument();
  expect(screen.getByText(/Б-1/)).toBeInTheDocument();
});

test('a record without company ownership remains visibly unassigned', () => {
  show(null, { companyId: null });
  expect(screen.getByText('Компания не определена')).toBeInTheDocument();
  expect(screen.getByText(/Принадлежность записей требует проверки/)).toBeInTheDocument();
});

test('mixed accounting collections preserve company totals and expense exclusions', () => {
  render(<CompanyGroups extra={{
    projectPayments: [{ companyId: 2, projectId: 10, projectName: 'Жилой комплекс', amount: 1000 },
      { companyId: 3, projectId: 20, projectName: 'Жилой комплекс', amount: 500 }],
    manualExpenses: [{ companyId: 2, projectId: 10, project: 'Жилой комплекс', amount: 40 },
      { companyId: 2, projectId: 10, project: 'Жилой комплекс', amount: 100, source: 'own_expense' }],
    ownExpenses: [{ companyId: 2, projectId: 10, projectName: 'Жилой комплекс', amount: 100, status: 'Возмещено' }],
    accountablePayments: [{ companyId: 3, projectId: 20, projectName: 'Жилой комплекс', amount: 30 }],
    interimActs: [{ companyId: 2, projectId: 10, project: 'Жилой комплекс', totalAmount: 100, paidAmount: 60 }],
  }} />);
  expect(screen.getByRole('button', { name: /Строй А/ })).toHaveTextContent('Поступило: 1 000 ₽ · Оплачено: 40 ₽');
  expect(screen.getByRole('button', { name: /Строй Б/ })).toHaveTextContent('Поступило: 500 ₽ · Оплачено: 30 ₽');
  expect(screen.getByText('70 ₽')).toBeInTheDocument();
});

test('search can distinguish companies with the same object name', () => {
  render(<CompanyGroups />);
  fireEvent.change(screen.getByPlaceholderText('🔍 Поиск по компании или объекту'), { target: { value: 'Строй Б' } });
  expect(screen.queryByRole('button', { name: /Строй А/ })).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: /Строй Б/ })).toBeInTheDocument();
});

test('same-name objects allow opening the company-aware payment form', () => {
  render(<CompanyGroups />);
  fireEvent.click(screen.getByRole('button', { name: 'Поступление' }));
  expect(screen.getByLabelText('Компания поступления')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Сохранить поступление' })).toBeDisabled();
});

test('accounting object shows exact invoice deferral without extra requests', () => {
  show();
  expect(screen.getByText('Осталось 7 дн.')).toBeInTheDocument();
  expect(screen.getByText(/Отсрочка по счёту #10/)).toBeInTheDocument();
  expect(screen.getByText(/не отдельный долг каждой отгрузки/)).toBeInTheDocument();
});

test('legacy receipt does not invent payment terms', () => {
  show(null);
  expect(screen.queryByLabelText('Отсрочка оплаты')).not.toBeInTheDocument();
});

test('deadline for another invoice is not displayed as this invoice schedule', () => {
  show({ ...deadline, invoiceId: 99 });
  expect(screen.queryByText('Осталось 7 дн.')).not.toBeInTheDocument();
  expect(screen.getByText('Срок оплаты требует проверки')).toBeInTheDocument();
});

test('cancelled invoice keeps history but no longer contributes debt', () => {
  show({ ...deadline, status: 'cancelled' }, { status: 'Аннулирован' });
  expect(screen.getByText('Счёт аннулирован')).toBeInTheDocument();
  expect(screen.queryByText(/Долг поставщикам/)).not.toBeInTheDocument();
  expect(screen.queryByText(/⚠️ долг 100/)).not.toBeInTheDocument();
});

test('non-accounting stock receipt does not enter supplier payments', () => {
  show(null, { accountingRequired: false });
  expect(screen.getByText('Движений денег пока нет')).toBeInTheDocument();
});

test('project invoice group can be toggled using keyboard', () => {
  const toggle = jest.fn();
  show(deadline, {}, toggle);
  fireEvent.keyDown(screen.getByRole('button', { name: /Объект А/ }), { key: 'Enter' });
  expect(toggle).toHaveBeenCalledWith(null);
});
