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
        attentionQueue: {
          readOnly: true,
          count: 2,
          truncated: false,
          items: [
            {
              id: 'overdue:project.deadline_overdue:0',
              priority: 'critical',
              category: 'Просрочки',
              reason: 'Просрочен срок объекта',
              subject: 'Школа',
              project: 'Школа',
              owner: 'Не указан',
              nextAction: 'Проверить срок и ответственного по объекту',
              destination: 'projects',
              sourceCode: 'project.deadline_overdue',
            },
            {
              id: 'shortages:warehouse.below_minimum:0',
              priority: 'warning',
              category: 'Дефициты',
              reason: 'Остаток ниже минимума',
              subject: 'Кабель',
              project: 'Вся компания',
              owner: 'Не указан',
              nextAction: 'Проверить остаток и потребность склада',
              destination: 'warehouse',
              sourceCode: 'warehouse.below_minimum',
            },
          ],
        },
      },
    }} isMobile={false}/>);

    expect(screen.getByText('Последняя фоновая сводка')).toBeInTheDocument();
    expect(screen.getByText(/05\.08\.2026/)).toBeInTheDocument();
    expect(screen.getByText('Критично: 1')).toBeInTheDocument();
    expect(screen.getByText('Просрочки')).toBeInTheDocument();
    expect(screen.getAllByText('Школа').length).toBeGreaterThan(0);
    expect(screen.getByText('3 дн.')).toBeInTheDocument();
    expect(screen.getByText('Требует внимания')).toBeInTheDocument();
    expect(screen.getByText('Просрочен срок объекта')).toBeInTheDocument();
    expect(screen.getAllByText(/Ответственный: Не указан/)).toHaveLength(2);
    expect(screen.getByText('Проверить срок и ответственного по объекту')).toBeInTheDocument();
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
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
