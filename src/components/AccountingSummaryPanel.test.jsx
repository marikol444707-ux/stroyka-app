import React from 'react';
import { render, screen } from '@testing-library/react';
import AccountingSummaryPanel from './AccountingSummaryPanel';
import { projectPaymentIncomingAmount } from '../utils/projectPaymentUtils';

test.each([false, true])('ledger supplier classification and net reversal %s', reversed => {
  const payment = { sourceKind: 'supplier_payment_ledger', operationKind: 'payment', amount: 100, note: 'Оплата бригаде' };
  render(<AccountingSummaryPanel C={{}} card={{}} projects={[]} invoices={[]}
    projectPaymentInAmount={projectPaymentIncomingAmount}
    projectPayments={[payment, ...(reversed ? [{ ...payment, operationKind: 'reversal', amount: -100 }] : [])]} />);
  expect(screen.getByText('Поступило от заказчиков').parentElement.querySelector('b')).toHaveTextContent(/^0 ₽$/);
  expect(screen.getByText('Оплачено поставщикам').parentElement.querySelector('b')).toHaveTextContent(reversed ? /^0 ₽$/ : /^100 ₽$/);
  expect(screen.getByText('Оплачено бригадам').parentElement.querySelector('b')).toHaveTextContent(/^0 ₽$/);
  expect(screen.getByText('Платежи по журналу').parentElement.querySelector('b')).toHaveTextContent(reversed ? /^0 ₽$/ : /^100 ₽$/);
});

test('legacy brigade and act expenses retain their category', () => {
  render(<AccountingSummaryPanel C={{}} card={{}} projects={[]} invoices={[]}
    projectPaymentInAmount={projectPaymentIncomingAmount} projectPayments={[
      { amount: 20, note: 'Оплата бригаде' }, { amount: 30, note: 'Выплата исполнителю по акту' },
    ]} />);
  expect(screen.getByText('Оплачено бригадам').parentElement.querySelector('b')).toHaveTextContent(/^50 ₽$/);
});


test('partial receipt chain shows net supplier cash once after an allocated refund', () => {
  render(<AccountingSummaryPanel C={{}} card={{}} projects={[]} invoices={[]} isLeadership
    supplierInvoices={[{ id: 1, paidAmount: 95 }]}
    projectPaymentInAmount={projectPaymentIncomingAmount}
    projectPayments={[
      { sourceKind: 'supplier_payment_ledger', operationKind: 'payment', amount: 120, note: 'Аванс' },
      { sourceKind: 'supplier_payment_ledger', operationKind: 'refund', amount: -25, note: 'Возврат поставщиком' },
    ]} />);
  const value = label => screen.getByText(label).parentElement.querySelector('b');
  expect(value('Поступило от заказчиков')).toHaveTextContent(/^0 ₽$/);
  expect(value('Оплачено поставщикам')).toHaveTextContent(/^95 ₽$/);
  expect(value('Платежи по журналу')).toHaveTextContent(/^95 ₽$/);
  expect(value('Всего расходов')).toHaveTextContent(/^95 ₽$/);
  expect(value('Чистая прибыль')).toHaveTextContent(/^-95 ₽$/);
});
