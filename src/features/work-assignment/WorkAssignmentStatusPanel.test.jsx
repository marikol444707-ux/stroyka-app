import { fireEvent, render, screen } from '@testing-library/react';
import WorkAssignmentStatusPanel from './WorkAssignmentStatusPanel';

describe('WorkAssignmentStatusPanel', () => {
  it('shows assignment status without a duplicate assign action', () => {
    render(
      <WorkAssignmentStatusPanel
        selectedEstimate={{
          id: 25,
          projectName: 'Объект',
          sections: [{
            name: 'Монтаж',
            items: [{name: 'Монтаж шкафа', unit: 'шт', quantity: 1, priceWork: 2000}],
          }],
        }}
        brigadeContracts={[]}
        brigadeContractItems={[]}
        API="/api"
        loadAll={jest.fn()}
        C={{
          text: '#111',
          textSec: '#555',
          textMuted: '#777',
          success: '#080',
          warning: '#b70',
          accent: '#08c',
          border: '#ddd',
          bg: '#f5f5f5',
          bgWhite: '#fff',
          warningBorder: '#db8',
          warningLight: '#fff8e6',
          successBorder: '#ada',
          successLight: '#f0fff0',
          danger: '#c00',
          dangerBorder: '#eaa',
          dangerLight: '#fff0f0',
        }}
        card={{}}
        btnG={{}}
        btnR={{}}
        isMobile={false}
        showLeadership
      />
    );

    expect(screen.getByText('Назначенные работы')).toBeInTheDocument();
    expect(screen.queryByRole('button', {name: 'Назначить'})).not.toBeInTheDocument();
    expect(screen.queryByText('Монтаж шкафа')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', {name: 'Показать строки (1)'}));

    expect(screen.getByText('Монтаж шкафа')).toBeInTheDocument();
    expect(screen.getByRole('button', {name: 'Скрыть строки'})).toBeInTheDocument();
  });
});
