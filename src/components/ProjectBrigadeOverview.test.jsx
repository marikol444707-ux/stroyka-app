import React from 'react';
import {render, screen} from '@testing-library/react';
import ProjectBrigadeOverview from './ProjectBrigadeOverview';

const signed = {status: 'Подписан', contractScanUrl: '/contract', actScanUrl: '/act'};

test.each([1, 2])('keeps remaining work visible after the current stage is paid (settlement %s)', settlementVersion => {
  render(<ProjectBrigadeOverview
    contract={{...signed, settlementVersion, planAmount: 1000, doneAmount: 400, paidAmount: 400,
      settlementSummary: {grossAmount: 400, fineAmount: 0, netAmount: 400, paidAmount: 400, remainingAmount: 0}}}
    items={[{quantity: 10, doneQuantity: 4, priceBrigade: 100}]}
    payments={[{amount: 400}]} C={{}} />);

  expect(screen.getByRole('region', {name: 'Сводка по исполнителю'}))
    .toHaveTextContent('Следующий шаг: Продолжайте выполнение оставшихся работ');
  expect(screen.queryByText(/Расчёты закрыты/)).not.toBeInTheDocument();
});

test('describes paid work without claiming the contract is closed', () => {
  render(<ProjectBrigadeOverview contract={signed}
    items={[{quantity: 4, doneQuantity: 4, priceBrigade: 100}]}
    payments={[{amount: 400}]} C={{}} />);

  expect(screen.getByRole('region', {name: 'Сводка по исполнителю'}))
    .toHaveTextContent('Следующий шаг: Выполненные работы оплачены');
});

test('prioritizes an unpaid completed stage before the remaining work', () => {
  render(<ProjectBrigadeOverview contract={signed}
    items={[{quantity: 10, doneQuantity: 4, priceBrigade: 100}]}
    payments={[{amount: 150}]} C={{}} />);

  expect(screen.getByRole('region', {name: 'Сводка по исполнителю'}))
    .toHaveTextContent('Следующий шаг: Проверьте расчёты и оплату');
});

 test('fully deducted fine is settled without pretending there was a payment', () => {
  render(<ProjectBrigadeOverview contract={{...signed, settlementVersion: 2,
    planAmount: 10000, doneAmount: 10000, paidAmount: 0,
    settlementSummary: {grossAmount: 10000, fineAmount: 10000, netAmount: 0, paidAmount: 0, remainingAmount: 0}}} C={{}} />);
  expect(screen.getByRole('region')).toHaveTextContent('Следующий шаг: Расчёт по актам завершён');
  expect(screen.getByText('Остаток по актам').parentElement).toHaveTextContent('0 ₽');
});

test('accepted work without an act asks to form one rather than reporting payment complete', () => {
  render(<ProjectBrigadeOverview contract={{...signed, settlementVersion: 2,
    planAmount: 10000, doneAmount: 10000,
    settlementSummary: {grossAmount: 0, fineAmount: 0, netAmount: 0, paidAmount: 0, remainingAmount: 0}}} C={{}} />);
  expect(screen.getByRole('region')).toHaveTextContent('Сформируйте акт по выполненным работам');
});

test('zero net unsigned act still requires the signed document', () => {
  render(<ProjectBrigadeOverview contract={{...signed, settlementVersion: 2,
    planAmount: 10000, doneAmount: 10000,
    settlementSummary: {grossAmount: 10000, fineAmount: 10000, netAmount: 0, paidAmount: 0,
      remainingAmount: 0, unsignedActCount: 1}}} C={{}} />);
  expect(screen.getByRole('region')).toHaveTextContent('Загрузите подписанный акт');
});
