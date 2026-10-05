import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import ProjectBrigadeCalculationTable from './ProjectBrigadeCalculationTable';

const item = {id: 42, name: 'Штукатурка', unit: 'м2', quantity: 10, doneQuantity: 0, priceSmeta: 500, priceBrigade: 300};

function renderTable(setItems) {
  return render(<ProjectBrigadeCalculationTable
    brigadeContractItems={[item]}
    setBrigadeContractItems={setItems}
    showLeadership
    C={{text: '#fff', warning: '#fa0', success: '#0a0', bg: '#111', textMuted: '#888', accent: '#f80', danger: '#f00'}}
  />);
}

afterEach(() => jest.restoreAllMocks());

test('keeps a started assignment visible when the server blocks removal', async () => {
  jest.spyOn(global, 'fetch').mockResolvedValue({ok: false, json: async () => ({detail: 'По этой позиции уже начаты работы'})});
  const setItems = jest.fn();
  renderTable(setItems);

  fireEvent.click(screen.getByRole('button', {name: 'Удалить Штукатурка'}));

  await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('уже начаты работы'));
  expect(screen.getByText('Штукатурка')).toBeInTheDocument();
  expect(setItems).not.toHaveBeenCalled();
});

test('removes an assignment only after the server confirms deletion', async () => {
  jest.spyOn(global, 'fetch').mockResolvedValue({ok: true, json: async () => ({ok: true})});
  const setItems = jest.fn();
  renderTable(setItems);

  fireEvent.click(screen.getByRole('button', {name: 'Удалить Штукатурка'}));

  await waitFor(() => expect(setItems).toHaveBeenCalledTimes(1));
  expect(setItems.mock.calls[0][0]([item])).toEqual([]);
});
