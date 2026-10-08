import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import AccountingContractsPanel from './AccountingContractsPanel';

it('keeps cancelled brigade documents in history instead of repeating them in the active list', () => {
  render(<AccountingContractsPanel
    C={{}} card={{}} inp={{}} btnO={{}} btnG={{}} btnB={{}} btnR={{}}
    brigadeContracts={[
      {id: 1, projectName: 'Лицей', brigadeName: 'Бригада Север', contractorType: 'ГПХ', status: 'Подписан'},
      {id: 2, projectName: 'Лицей', brigadeName: 'Бригада Север', contractorType: 'ГПХ', status: 'Аннулирован'},
      {id: 3, projectName: 'Лицей', brigadeName: 'Бригада Юг', contractorType: 'ГПХ', status: 'Черновик'},
    ]}
  />);
  expect(screen.getAllByText(/1 док\./)).toHaveLength(1);
  expect(screen.getByText(/БР-1/)).toBeInTheDocument();
  expect(screen.queryByRole('button', {name: /Скрыть договоры/})).not.toBeInTheDocument();
  expect(screen.queryByText(/БР-2/)).not.toBeInTheDocument();
  expect(screen.queryByText(/БР-3/)).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', {name: /История и черновики/}));
  expect(screen.queryByText(/БР-1/)).not.toBeInTheDocument();
  expect(screen.getByText(/БР-2/)).toBeInTheDocument();
  expect(screen.getByText(/БР-3/)).toBeInTheDocument();
});

it('shows one compact performer card and expands documents on request', () => {
  render(<AccountingContractsPanel
    C={{}} card={{}} inp={{}} btnO={{}} btnG={{}} btnB={{}} btnR={{}}
    brigadeContracts={[
      {id: 3, projectId: 10, projectName: 'Лицей', brigadeName: 'Бригада Север', status: 'Подписан'},
      {id: 4, projectId: 11, projectName: 'Школа', brigadeName: 'Бригада Север', status: 'Подписан'},
    ]}
  />);

  const toggle = screen.getByRole('button', {name: /Показать договоры.*2/});
  expect(toggle).toHaveAttribute('aria-expanded', 'false');
  expect(screen.queryByText(/БР-3/)).not.toBeInTheDocument();
  fireEvent.click(toggle);
  expect(screen.getByRole('button', {name: /Скрыть договоры/})).toHaveAttribute('aria-expanded', 'true');
  expect(screen.getByText(/БР-3/)).toBeInTheDocument();
  expect(screen.getByText(/БР-4/)).toBeInTheDocument();
});

it('reveals matching documents during a search', () => {
  render(<AccountingContractsPanel
    C={{}} card={{}} inp={{}} btnO={{}} btnG={{}} btnB={{}} btnR={{}}
    listSearch="БР-4"
    brigadeContracts={[
      {id: 3, projectId: 10, projectName: 'Лицей', brigadeName: 'Бригада Север', status: 'Подписан'},
      {id: 4, projectId: 11, projectName: 'Школа', brigadeName: 'Бригада Север', status: 'Подписан'},
    ]}
  />);
  expect(screen.getByText(/БР-4/)).toBeInTheDocument();
  expect(screen.queryByText(/БР-3/)).not.toBeInTheDocument();
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

  expect(screen.getByText('Есть пустой дубль договора')).toBeInTheDocument();

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

it('uses actual act fine and net instead of automatic five percent retention', () => {
  render(<AccountingContractsPanel C={{}} card={{}} inp={{}} btnO={{}} btnG={{}} btnB={{}} btnR={{}}
    brigadeContracts={[{id: 30, brigadeName: 'Мастер по актам', projectName: 'Лицей', status: 'Подписан',
      settlementVersion: 2, doneAmount: 10000, paidAmount: 8000,
      settlementSummary: {grossAmount: 10000, fineAmount: 2000, netAmount: 8000, paidAmount: 8000, remainingAmount: 0}}]} />);
  expect(screen.getByText('Штрафы по актам').parentElement).toHaveTextContent('2 000 ₽');
  expect(screen.queryByText('Удержание 5%')).not.toBeInTheDocument();
  expect(screen.getByText('Остаток к выплате').parentElement).toHaveTextContent('0 ₽');
  expect(screen.queryByText(/к выплате:/)).not.toBeInTheDocument();
});

it('does not round a remaining act debt of 25 kopecks to closed', () => {
  render(<AccountingContractsPanel C={{}} card={{}} inp={{}} btnO={{}} btnG={{}} btnB={{}} btnR={{}}
    brigadeContracts={[{id: 30, brigadeName: 'Мастер по актам', status: 'Подписан', settlementVersion: 2,
      settlementSummary: {grossAmount: 10, fineAmount: 4, netAmount: 6, paidAmount: 5.75, remainingAmount: 0.25}}]} />);
  expect(screen.getByText('Остаток к выплате').parentElement).toHaveTextContent('0,25 ₽');
});

it('still requires an NPD receipt after paying a self-employed canonical act', () => {
  render(<AccountingContractsPanel C={{}} card={{}} inp={{}} btnO={{}} btnG={{}} btnB={{}} btnR={{}}
    brigadeContracts={[{id: 30, brigadeName: 'Самозанятый мастер', contractorType: 'Самозанятый',
      status: 'Подписан', settlementVersion: 2,
      settlementSummary: {grossAmount: 10, fineAmount: 0, netAmount: 10, paidAmount: 10, remainingAmount: 0}}]} />);
  expect(screen.getByText('⚠️ Не хватает: чек НПД')).toBeInTheDocument();
});
