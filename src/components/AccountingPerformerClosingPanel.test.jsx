import React from 'react';
import { render, screen } from '@testing-library/react';
import AccountingPerformerClosingPanel from './AccountingPerformerClosingPanel';

function show(payments) {
  const month = new Date().toISOString().slice(0, 7);
  render(<AccountingPerformerClosingPanel C={{}} card={{}} inp={{}} projects={[]} listSearch=""
    matchSearch={() => true} staff={[]} workJournal={[{ id: 1, status: 'Подтверждено',
      date: month + '-01', project: 'Объект', masterName: 'Иван', roomName: 'Комната',
      workPackage: 'Основная', executionTotal: 200, quantity: 1 }]}
    projectPayments={payments.map(row => ({ projectName: 'Объект', workPackage: 'Основная',
      note: 'Выплата исполнителю: Иван · ' + month + ' · Основная', ...row }))} />);
}

test.each([['payment', 100], ['reversal', -100]])('ledger %s never counts as performer payment', (operationKind, amount) => {
  show([{ sourceKind: 'supplier_payment_ledger', operationKind, amount }]);
  expect(screen.getByText('Выплачено / остаток').parentElement.querySelector('b')).toHaveTextContent(/^0 ₽ \/ 200 ₽$/);
});

test('legacy performer payment still reduces payable', () => {
  show([{ amount: -100 }]);
  expect(screen.getByText('Выплачено / остаток').parentElement.querySelector('b')).toHaveTextContent(/^100 ₽ \/ 100 ₽$/);
});
