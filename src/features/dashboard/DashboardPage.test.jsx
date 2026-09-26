import React from 'react';
import { render } from '@testing-library/react';
import DashboardPage from './DashboardPage';
import { projectPaymentSignedAmountValue } from '../../utils/projectPaymentUtils';

const mockTopBar = jest.fn(() => <div data-testid="dashboard-top-bar" />);
const mockStatsGrid = jest.fn(() => null);
jest.mock('../../components/DashboardStatsGrid', () => props => mockStatsGrid(props));
jest.mock('../../app/lazyComponents', () => ({
  DashboardActivityPanel: () => null,
  DashboardDirectorAiPanel: () => null,
  DashboardProductionSummaryPanel: () => null,
  DashboardSupplyPanel: () => null,
}));

jest.mock('../../components/DashboardTopBar', () => (props) => mockTopBar(props));
jest.mock('./useLatestDirectorDailyBrief', () => ({
  useLatestDirectorDailyBrief: () => ({}),
}));

test.each(['Аванс', 'Оплата счёта', 'Оплата бригаде'])('dashboard nets ledger reversal regardless of reason %s', note => {
  mockStatsGrid.mockClear();
  render(<DashboardPage ui={{ C: {} }} data={{ initialDataLoaded: true, user: {},
    projectPayments: [{ sourceKind: 'supplier_payment_ledger', operationKind: 'payment', amount: 100, note },
      { sourceKind: 'supplier_payment_ledger', operationKind: 'reversal', amount: -100, note }] }}
    actions={{ projectPaymentSignedAmount: projectPaymentSignedAmountValue }} />);
  expect(mockStatsGrid.mock.calls[0][0].totalExpenses).toBe(0);
});

test('dashboard keeps legacy brigade and act expenses', () => {
  mockStatsGrid.mockClear();
  render(<DashboardPage ui={{ C: {} }} data={{ initialDataLoaded: true, user: {},
    projectPayments: [{ amount: 20, note: 'Оплата бригаде' }, { amount: 30, note: 'Выплата исполнителю по акту' }] }}
    actions={{ projectPaymentSignedAmount: projectPaymentSignedAmountValue }} />);
  expect(mockStatsGrid.mock.calls[0][0].totalExpenses).toBe(50);
});

describe('DashboardPage notifications wiring', () => {
  beforeEach(() => {
    mockTopBar.mockClear();
  });

  it('passes the notification reader from actions to the top bar', () => {
    const myNotifications = jest.fn(() => [{ id: 'notice-1' }]);

    render(
      <DashboardPage
        actions={{ myNotifications }}
        data={{ initialDataLoaded: false }}
        ui={{}}
      />,
    );

    expect(mockTopBar).toHaveBeenCalled();
    expect(mockTopBar.mock.calls[0][0].myNotifications).toBe(myNotifications);
  });
});
