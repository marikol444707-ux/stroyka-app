import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import CustomerCabinetPage from '../../components/CustomerCabinetPage';
import useProgressData from './useProgressData';

jest.mock('./useProgressData');
const props = {
  user: { id: 1, projectId: 3, companyId: 2, name: 'Customer' },
  projects: [{ id: 3, companyId: 2, name: 'Site', progress: 40 }],
  C: {}, card: {}, workJournal: [], projectStages: [], hiddenActs: [], unexpectedWorksList: [],
  prescriptionsList: [], contracts: [], computeNotifications: () => [],
};
test.each([{ loading: true }, { loading: false, error: 'Load failed' }])('unavailable data is never rendered as an empty project: %j', state => {
  useProgressData.mockReturnValue({ ...state, estimates: [], journal: [] });
  render(<CustomerCabinetPage {...props} />);
  expect(screen.queryByText('Смета подрядчиком ещё не загружена.')).toBeNull();
  expect(screen.queryByText('Подрядчик пока не загружал фото работ.')).toBeNull();
  expect(screen.queryByText('Записей нет')).toBeNull();
  expect(screen.queryByText('40%')).toBeNull();
});

test('customer decision sends only the displayed revision, not editable prices or an invented author', async () => {
  useProgressData.mockReturnValue({ loading: true, estimates: [], journal: [] });
  global.fetch = jest.fn(async () => ({ ok: true, json: async () => ({ ok: true }) }));
  jest.spyOn(window, 'confirm').mockReturnValue(true);
  const refreshData = jest.fn();
  render(<CustomerCabinetPage {...props} refreshData={refreshData} isApprovedEstimateChangeStatus={() => false}
    customerRecordsLoadState={{ extraWorks: { scope: '1:2:3:', status: 'ready' } }}
    unexpectedWorksList={[{ id: 5, companyId: 2, projectId: 3, projectName: 'Site',
      status: 'Ожидает согласования', description: 'Extra', price: 150, total: 300, revision: 'revision-1' }]} />);
  fireEvent.click(screen.getByRole('button', { name: 'Согласовать' }));
  await waitFor(() => expect(refreshData).toHaveBeenCalledTimes(1));
  expect(fetch.mock.calls[0][0]).toContain('/unexpected-works/5/customer-decision');
  expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({ decision: 'approve', revision: 'revision-1' });
  window.confirm.mockRestore();
});
