import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import AccountingContractsPanel from './AccountingContractsPanel';

it('keeps cancelled brigade documents in history instead of repeating them in the active list', () => {
  render(<AccountingContractsPanel
    C={{}} card={{}} inp={{}} btnO={{}} btnG={{}} btnB={{}} btnR={{}}
    brigadeContracts={[
      {id: 1, projectName: 'Лицей', brigadeName: 'Бригада Север', contractorType: 'ГПХ', status: 'Подписан'},
      {id: 2, projectName: 'Лицей', brigadeName: 'Бригада Север', contractorType: 'ГПХ', status: 'Аннулирован'},
    ]}
  />);
  expect(screen.getByText(/1 док\./)).toBeInTheDocument();
  expect(screen.queryByText(/БР-2/)).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', {name: /История и черновики/}));
  expect(screen.getByText(/2 док\./)).toBeInTheDocument();
  expect(screen.getByText(/БР-2/)).toBeInTheDocument();
});
