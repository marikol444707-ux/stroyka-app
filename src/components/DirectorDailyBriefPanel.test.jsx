import {fireEvent, render, screen} from '@testing-library/react';

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
    expect(screen.queryByText('Просрочен срок объекта')).not.toBeInTheDocument();
    expect(screen.getByRole('button', {name: 'Подробнее'})).toHaveAttribute('aria-expanded', 'false');
    fireEvent.click(screen.getByRole('button', {name: 'Подробнее'}));
    expect(screen.getByText('Просрочки')).toBeInTheDocument();
    expect(screen.getAllByText('Школа').length).toBeGreaterThan(0);
    expect(screen.getByText('3 дн.')).toBeInTheDocument();
    expect(screen.getByText('Требует внимания')).toBeInTheDocument();
    expect(screen.getByText('Просрочен срок объекта')).toBeInTheDocument();
    expect(screen.getAllByText(/Ответственный: Не указан/)).toHaveLength(2);
    expect(screen.getByText('Проверить срок и ответственного по объекту')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', {name: 'Свернуть'}));
    expect(screen.queryByText('Просрочен срок объекта')).not.toBeInTheDocument();
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

  test('shows an optional short explanation only inside expanded details', () => {
    render(<DirectorDailyBriefPanel state={{status: 'ready', data: {
      completedAt: '2026-08-05T11:30:00',
      brief: {
        briefDate: '2026-08-05',
        summary: {total: 1, critical: 1, warning: 0, info: 0},
        sections: [],
      },
      explanation: {
        headline: 'Есть вопросы, требующие внимания',
        overview: 'Проверьте сроки объекта.',
        points: [{sourceCode: 'project.deadline_overdue', text: 'Срок требует проверки.'}],
      },
    }, error: ''}}/>);

    expect(screen.queryByText('Короткое объяснение')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', {name: 'Подробнее'}));
    expect(screen.getByText('Короткое объяснение')).toBeInTheDocument();
    expect(screen.getByText('Есть вопросы, требующие внимания')).toBeInTheDocument();
    expect(screen.getByText('Проверьте сроки объекта.')).toBeInTheDocument();
    expect(screen.getByText('Срок требует проверки.')).toBeInTheDocument();
    expect(screen.getByText('AI объясняет готовые данные и ничего не изменяет')).toBeInTheDocument();
  });
});
