import React from 'react';
import { render, screen } from '@testing-library/react';
import ProjectScheduleTab from './ProjectScheduleTab';

function show(payment) {
  render(<ProjectScheduleTab C={{}} ProjectScheduleSummaryPanel={() => null} project={{ name: 'Объект' }}
    projectStages={[{ id: 1, projectName: 'Объект', startDate: '2026-09-01', endDate: '2026-09-30' }]}
    projectPayments={[{ id: 1, projectName: 'Объект', note: 'Произвольное основание', ...payment }]}
    projectPlanDone={() => ({})} projectRealProgress={() => 0} materialControlSummaryForProject={() => ({})} />);
}

test.each([['payment', 100, 'Расход поставщику', '-100 ₽'],
  ['reversal', -100, 'Сторно расхода поставщику', '+100 ₽']])('ledger %s displays financial direction and label',
  (operationKind, amount, label, money) => {
    show({ sourceKind: 'supplier_payment_ledger', operationKind, amount });
    expect(screen.getByText(label + ' · Произвольное основание')).toBeInTheDocument();
    expect(screen.getByText(money)).toBeInTheDocument();
  });

test('legacy incoming display is unchanged', () => {
  show({ amount: 100 });
  expect(screen.getByText('+100 ₽')).toBeInTheDocument();
  expect(screen.getByText('Произвольное основание')).toBeInTheDocument();
});
