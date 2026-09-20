import React from 'react';
import { render, screen } from '@testing-library/react';
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
