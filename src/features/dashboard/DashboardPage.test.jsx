import React from 'react';
import { render, screen } from '@testing-library/react';
import DashboardPage from './DashboardPage';

jest.mock('../../app/lazyComponents', () => ({
  DashboardActivityPanel: () => null,
  DashboardDirectorAiPanel: () => null,
  DashboardProductionSummaryPanel: () => null,
  DashboardSupplyPanel: () => null,
}));

describe('DashboardPage loading contract', () => {
  it('does not render business totals before the initial object data load completes', () => {
    render(
      <DashboardPage
        data={{
          initialDataLoaded: false,
          projects: [{ id: 1, name: 'Объект', budget: 1000000 }],
          user: { id: 7, name: 'Директор', role: 'директор' },
        }}
        ui={{ darkMode: true, isMobile: false }}
      />,
    );

    expect(screen.getByText('Загружаю данные объекта')).toBeInTheDocument();
    expect(screen.queryByText('1 000 000')).not.toBeInTheDocument();
  });
});
