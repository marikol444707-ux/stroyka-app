import React from 'react';
import { render } from '@testing-library/react';
import DashboardPage from './DashboardPage';

const mockTopBar = jest.fn(() => <div data-testid="dashboard-top-bar" />);

jest.mock('../../components/DashboardTopBar', () => (props) => mockTopBar(props));
jest.mock('./useLatestDirectorDailyBrief', () => ({
  useLatestDirectorDailyBrief: () => ({}),
}));

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
