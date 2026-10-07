import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
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

const duplicateContracts = [
  {id: 18, companyId: 1, projectId: 24, projectName: 'Лицей', workPackage: 'Основная', contractorId: 56, brigadeName: 'Мастер', status: 'Подписан'},
  {id: 20, companyId: 1, projectId: 24, projectName: 'Лицей', workPackage: 'Основная', contractorId: 56, brigadeName: 'Мастер', status: 'Подписан'},
];

function renderDuplicatePanel() {
  return render(<AccountingContractsPanel
    API="/api" C={{}} card={{}} inp={{}} btnO={{}} btnG={{}} btnB={{}} btnR={{}}
    isFinanceRole={() => true}
    brigadeContracts={duplicateContracts}
    allBrigadeItems={[{id: 101, contractId: 18}]}
  />);
}

afterEach(() => jest.restoreAllMocks());

it('offers archiving only for the empty signed duplicate and keeps the original', async () => {
  jest.spyOn(window, 'confirm').mockReturnValue(true);
  const request = jest.spyOn(global, 'fetch').mockResolvedValue({ok: true, json: async () => ({ok: true})});
  renderDuplicatePanel();

  expect(screen.queryByRole('button', {name: 'Убрать пустой дубль № БР-18'})).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', {name: 'Убрать пустой дубль № БР-20'}));

  await waitFor(() => expect(screen.getByText(/1 док\./)).toBeInTheDocument());
  expect(screen.getByText(/БР-18/)).toBeInTheDocument();
  expect(screen.queryByText(/БР-20/)).not.toBeInTheDocument();
  expect(request).toHaveBeenCalledWith('/api/brigade-contracts/20', {method: 'DELETE'});
});

it('keeps the duplicate visible when the server finds linked records', async () => {
  jest.spyOn(window, 'confirm').mockReturnValue(true);
  jest.spyOn(global, 'fetch').mockResolvedValue({ok: false, json: async () => ({detail: 'У договора есть работы или расчёты'})});
  renderDuplicatePanel();

  fireEvent.click(screen.getByRole('button', {name: 'Убрать пустой дубль № БР-20'}));

  await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('есть работы или расчёты'));
  expect(screen.getByText(/БР-20/)).toBeInTheDocument();
});
