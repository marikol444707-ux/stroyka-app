import {render, screen} from '@testing-library/react';

import DirectorDailyBriefPanel from './DirectorDailyBriefPanel';


describe('DirectorDailyBriefPanel', () => {
  test('renders a compact ready brief with section details', () => {
    render(<DirectorDailyBriefPanel state={{
      status: 'ready',
      error: '',
      data: {
        completedAt: '2026-08-05T11:30:00',
        brief: {
          briefDate: '2026-08-05',
          summary: {total: 3, critical: 1, warning: 1, info: 1},
          sections: [
            {
              key: 'overdue',
              title: 'Просрочки',
              status: 'attention',
              count: 1,
              truncated: false,
              items: [{severity: 'critical', subject: 'Школа', project: 'Школа', metricValue: 3, metricUnit: 'days'}],
            },
          ],
        },
      },
    }} isMobile={false}/>);

    expect(screen.getByText('Последняя фоновая сводка')).toBeInTheDocument();
    expect(screen.getByText(/05\.08\.2026/)).toBeInTheDocument();
    expect(screen.getByText('Критично: 1')).toBeInTheDocument();
    expect(screen.getByText('Просрочки')).toBeInTheDocument();
    expect(screen.getByText('Школа')).toBeInTheDocument();
    expect(screen.getByText('3 дн.')).toBeInTheDocument();
  });

  test('explains that one company must be selected', () => {
    render(<DirectorDailyBriefPanel state={{status: 'select-company', data: null, error: ''}}/>);

    expect(screen.getByText('Выберите одну компанию, чтобы увидеть её сводку.')).toBeInTheDocument();
  });

  test('shows a clear empty state without a generate button', () => {
    render(<DirectorDailyBriefPanel state={{status: 'empty', data: null, error: ''}}/>);

    expect(screen.getByText('Готовая фоновая сводка пока не сформирована.')).toBeInTheDocument();
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });
});
