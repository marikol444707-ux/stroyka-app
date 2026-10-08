import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import ProjectBrigadesList from './ProjectBrigadesList';

const contracts = [
  {id: 1, projectName: 'Лицей', brigadeName: 'Бригада Север', contractorType: 'ИП', status: 'Подписан'},
  {id: 2, projectName: 'Лицей', brigadeName: 'Бригада Север', contractorType: 'ИП', status: 'Аннулирован'},
  {id: 3, projectName: 'Лицей', brigadeName: 'Бригада Юг', contractorType: 'ГПХ', status: 'Черновик'},
];

const props = {
  projectName: 'Лицей', brigadeContracts: contracts, openBrigadeContract: jest.fn(),
  setBrigadeContracts: jest.fn(), C: {}, card: {}, btnR: {},
};

it('shows current contracts without historical duplicates and keeps history accessible', () => {
  render(<ProjectBrigadesList {...props} />);
  expect(screen.getAllByText('Бригада Север')).toHaveLength(1);
  expect(screen.queryByText('Бригада Юг')).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', {name: /История и черновики/}));
  expect(screen.getAllByText('Бригада Север')).toHaveLength(1);
  expect(screen.getByText('Бригада Юг')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', {name: 'Скрыть историю'}));
  expect(screen.queryByText('Бригада Юг')).not.toBeInTheDocument();
});

it('does not hide a draft when annulment fails on the server', async () => {
  const oldFetch = global.fetch;
  const oldConfirm = window.confirm;
  global.fetch = jest.fn().mockResolvedValue({ok: false, json: async () => ({detail: 'Нет прав'})});
  window.confirm = jest.fn(() => true);
  try {
    render(<ProjectBrigadesList {...props} />);
    fireEvent.click(screen.getByRole('button', {name: /История и черновики/}));
    fireEvent.click(screen.getByRole('button', {name: 'Аннулировать черновик Бригада Юг'}));
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Нет прав'));
    expect(props.setBrigadeContracts).not.toHaveBeenCalled();
  } finally {
    global.fetch = oldFetch;
    window.confirm = oldConfirm;
  }
});

it('keeps a way back when the last historical contract changes status', () => {
  const draft = {id: 4, projectName: 'Лицей', brigadeName: 'Новая бригада', contractorType: 'ИП', status: 'Черновик'};
  const {rerender} = render(<ProjectBrigadesList {...props} brigadeContracts={[draft]} />);
  fireEvent.click(screen.getByRole('button', {name: /История и черновики/}));
  rerender(<ProjectBrigadesList {...props} brigadeContracts={[{...draft, status: 'Подписан'}]} />);

  expect(screen.getByRole('button', {name: 'Скрыть историю'})).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', {name: 'Скрыть историю'}));
  expect(screen.getByText('Новая бригада')).toBeInTheDocument();
});
