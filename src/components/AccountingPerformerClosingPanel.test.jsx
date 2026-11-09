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

test.each(['Иван', 'Старое имя'])('advance to one exact employee is not deducted from a namesake (%s)', givenTo => {
  const month = new Date().toISOString().slice(0, 7);
  const work = { status: 'Подтверждено', date: month + '-01', project: 'Объект',
    masterName: 'Иван', roomName: 'Комната', workPackage: 'Основная', executionTotal: 200, quantity: 1 };
  render(<AccountingPerformerClosingPanel C={{}} card={{}} inp={{}} projects={[]} listSearch=""
    matchSearch={() => true} staff={[{ id: 1, name: 'Иван' }, { id: 2, name: 'Иван' }]}
    workJournal={[{ ...work, id: 1, masterId: 1 }, { ...work, id: 2, masterId: 2 }]}
    accountablePayments={[{ id: 9, companyId: 4, projectName: 'Объект', givenToId: 1, givenTo,
      date: month + '-01', amount: 100 }]} projectPayments={[]} />);
  const balances = screen.getAllByText('Выплачено / остаток').map(node => node.parentElement.querySelector('b').textContent);
  expect(balances).toEqual(['0 ₽ / 100 ₽', '0 ₽ / 200 ₽']);
  expect(screen.getByText('Авансы/подотчет').parentElement).toHaveTextContent('100 ₽');
});

const closingWork = overrides => ({
  id: 1, status: 'Подтверждено', date: new Date().toISOString().slice(0, 7) + '-01',
  project: 'Объект', masterName: 'Иван', masterId: 1, roomName: 'Комната',
  executionTotal: 200, quantity: 1, ...overrides,
});
const closingPanel = workJournal => <AccountingPerformerClosingPanel C={{}} card={{}} inp={{}}
  projects={[]} staff={[]} listSearch="" workJournal={workJournal} />;

test.each([
  { roomName: 'Без помещения' },
  { roomName: '  Без помещения  ' },
  { roomName: '', room_name: 'Без помещения' },
  { roomName: '' },
  { roomName: null },
  { roomName: '   ' },
])('excluded room produces a warning and becomes payable after correction: %j', room => {
  const { rerender } = render(closingPanel([closingWork(room)]));
  expect(screen.getByText(/Не попадут в акт:/)).toHaveTextContent('1 подтверждённых строк');
  expect(screen.queryByText('Выплачено / остаток')).not.toBeInTheDocument();
  expect(screen.getByText('Зафиксировать месяц')).toBeDisabled();
  rerender(closingPanel([closingWork({ ...room, roomName: 'Комната' })]));
  expect(screen.queryByText(/Не попадут в акт:/)).not.toBeInTheDocument();
  expect(screen.getByText('Выплачено / остаток').parentElement.querySelector('b')).toHaveTextContent('0 ₽ / 200 ₽');
});

test('warning counts only excluded legacy confirmed works in the closing month, once per work', () => {
  render(closingPanel([
    closingWork({ id: 1, roomName: 'Без помещения', executionTotal: 0 }),
    closingWork({ id: 2, executionTotal: 0 }),
    closingWork({ id: 3, roomName: 'Без помещения', status: 'На проверке' }),
    closingWork({ id: 4, roomName: 'Без помещения', confirmedAt: '2001-01-01' }),
    closingWork({ id: 5, roomName: 'Без помещения', settlementVersion: 2 }),
    closingWork({ id: 6 }),
  ]));
  expect(screen.getByText(/Не попадут в акт:/)).toHaveTextContent('2 подтверждённых строк');
  expect(screen.getAllByText('Выплачено / остаток')).toHaveLength(1);
});
