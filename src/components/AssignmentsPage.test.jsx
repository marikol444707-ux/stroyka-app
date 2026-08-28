import React from 'react';
import { render, screen } from '@testing-library/react';
import AssignmentsPage from './AssignmentsPage';

jest.mock('../features/assignment-daily-drafts/AssignmentDailyDraftPreviewPanel', () => () => (
  <div>Дублирующий черновик назначений</div>
));

test('keeps brigade work assignment out of the general поручения page', () => {
  render(
    <AssignmentsPage
      C={{
        accent: '#f60', accentLight: '#321', border: '#456', bg: '#012', bgWhite: '#123',
        text: '#fff', textSec: '#ccd', textMuted: '#99a', info: '#39f', infoLight: '#123',
        infoBorder: '#369', success: '#3c9', successLight: '#132', successBorder: '#396',
        warning: '#fc3', warningLight: '#321', warningBorder: '#963', danger: '#f66',
        dangerLight: '#311', dangerBorder: '#933',
      }}
      aiTasks={[]}
      projects={[]}
      users={[]}
      user={{role: 'директор', name: 'Директор'}}
      btnB={{}}
      btnG={{}}
      btnO={{}}
      btnR={{}}
      card={{}}
      inp={{}}
    />,
  );

  expect(screen.getByRole('heading', {name: 'Поручения'})).toBeInTheDocument();
  expect(screen.queryByText('Дублирующий черновик назначений')).not.toBeInTheDocument();
});
