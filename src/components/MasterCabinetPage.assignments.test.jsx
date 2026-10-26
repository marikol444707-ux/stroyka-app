import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import MasterCabinetPage from './MasterCabinetPage';

jest.mock('./MasterWorkJournalPhotoField', () => () => null);

function props(overrides = {}) {
  const values = { API: '/api', C: {}, ROLE_LABELS: {}, activePage: 'works', user: { id: 42, name: 'Мастер', role: 'субподрядчик' },
    projects: [{ id: 11, name: 'Лицей', pricelistId: 9 }], masterProjectId: '11',
    selectedWorks: {}, estimateWorkParams: {}, estimateWorkMaterials: {}, estimateDoneDrafts: {},
    estimatesList: [{ id: 72, projectName: 'Лицей', status: 'Активная', workPackage: 'Основная', sections: [
      { name: 'Монтаж', items: [{ estimateItemKey: '72:1:7', name: 'Монтаж розетки', unit: 'шт', quantity: 10 }] },
    ] }],
    brigadeContractItems: [{ id: 100, contractId: 23, projectName: 'Лицей', workPackage: '',
      estimateItemKey: '72:1:7', name: 'Монтаж розетки', unit: 'шт', quantity: 5, priceBrigade: 300 }],
    estimateWorkKey: (id, section, item) => `${id}:${section}:${item}`,
    loadPricelistItems: jest.fn(async () => ({ items: [], error: '' })),
    setMasterProjectId: jest.fn(), setSelectedWorks: jest.fn(), setActivePage: jest.fn(), refreshData: jest.fn(),
  };
  for (const key of ['piecework', 'workJournal', 'materialTransfers', 'pricelistItems', 'contracts', 'brigadeContracts',
    'interimActs', 'rooms', 'tools', 'ownExpenses', 'supplyRequests', 'SURFACES', 'UNITS', 'EXPENSE_CATEGORIES']) values[key] = [];
  return { ...values, ...overrides };
}

test('shows an assigned contract row after server filtering changes indexes, including legacy blank package', () => {
  render(<MasterCabinetPage {...props()} />);
  expect(screen.getByText('Монтаж розетки')).toBeInTheDocument();
  expect(screen.getByText(/план 5 шт/)).toBeInTheDocument();
  expect(screen.queryByText('Работы по смете еще не назначены')).not.toBeInTheDocument();
});

test('selecting an estimated project clears the pricelist without requesting its forbidden items', async () => {
  const values = props();
  render(<MasterCabinetPage {...values} />);
  fireEvent.click(screen.getByRole('button', { name: /Лицей.*⌄/ }));
  fireEvent.click(screen.getByRole('button', { name: 'Лицей', exact: true }));
  await waitFor(() => expect(values.loadPricelistItems).toHaveBeenCalledWith(null));
  expect(screen.getByText('Монтаж розетки')).toBeInTheDocument();
});

test('an unmatched contract is reported as a mismatch instead of an absent assignment', () => {
  render(<MasterCabinetPage {...props({ brigadeContractItems: [{ id: 100, projectName: 'Лицей',
    workPackage: 'Основная', estimateItemKey: 'another-row', name: 'Монтаж розетки', unit: 'шт' }] })} />);
  expect(screen.getByText('Работы есть в договоре, но не сопоставлены со сметой')).toBeInTheDocument();
  expect(screen.queryByText('Работы по смете еще не назначены')).not.toBeInTheDocument();
});

test('expense history stays accessible when the summary has no rows', () => {
  const values = props();
  render(<MasterCabinetPage {...values} />);
  fireEvent.click(screen.getByRole('button', { name: 'Все траты', exact: true }));
  expect(values.setActivePage).toHaveBeenCalledWith('myexpenses');
  expect(values.refreshData).toHaveBeenCalledWith('myexpenses');
});
