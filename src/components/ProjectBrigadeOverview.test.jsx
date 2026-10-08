import React from 'react';
import {render, screen} from '@testing-library/react';
import ProjectBrigadeOverview from './ProjectBrigadeOverview';

const signed = {status: 'Подписан', contractScanUrl: '/contract', actScanUrl: '/act'};

test.each([1, 2])('keeps remaining work visible after the current stage is paid (settlement %s)', settlementVersion => {
  render(<ProjectBrigadeOverview
    contract={{...signed, settlementVersion, planAmount: 1000, doneAmount: 400, paidAmount: 400}}
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
