import React from 'react';
import {fireEvent, render, screen, waitFor} from '@testing-library/react';
import WorkSubmissionRecovery from './WorkSubmissionRecovery';
import {pendingWorkBatch, resumeWorkBatch, clearWorkBatch, abandonRejectedWorkTail} from './workCommands';

jest.mock('./workCommands', () => ({
  pendingWorkBatch: jest.fn(), resumeWorkBatch: jest.fn(), clearWorkBatch: jest.fn(),
  abandonRejectedWorkTail: jest.fn(), workBatchScope: (context, user) => ({companyId: context.selectedCompanyId, userId: user.id}),
}));
jest.mock('./materialSources', () => ({workMaterialAccountingEnabled: () => true}));
const props = {API: '', companyContext: {selectedCompanyId: 2}, user: {id: 11}, C: {}};
beforeEach(() => { jest.clearAllMocks(); pendingWorkBatch.mockReturnValue({next: 0, commands: [{}, {}]}); });

it('hides the previous company recovery when company selection is cleared', () => {
  const {rerender} = render(<WorkSubmissionRecovery {...props} />);
  expect(screen.getByRole('region', {name: 'Сохранённая отправка'})).not.toBeNull();
  rerender(<WorkSubmissionRecovery {...props} companyContext={{selectedCompanyId: null}} />);
  expect(screen.queryByRole('region', {name: 'Сохранённая отправка'})).toBeNull();
});

it('offers a clear retry action and retains saved sending when recovery fails', async () => {
  resumeWorkBatch.mockRejectedValueOnce(new Error('Связь потеряна'));
  render(<WorkSubmissionRecovery {...props} />);
  fireEvent.click(screen.getByRole('button', {name: 'Завершить отправку'}));
  await waitFor(() => expect(screen.getByRole('alert').textContent).toBe('Связь потеряна'));
  expect(clearWorkBatch).not.toHaveBeenCalled();
  expect(screen.queryByRole('button', {name: 'Вернуться к исправлению'})).toBeNull();
});

it('clears the saved sending only after refreshing confirmed work', async () => {
  const completed = {next: 2, commands: [{}, {}]};
  resumeWorkBatch.mockResolvedValueOnce(completed);
  const onRecovered = jest.fn(async () => { expect(clearWorkBatch).not.toHaveBeenCalled(); });
  render(<WorkSubmissionRecovery {...props} onRecovered={onRecovered} />);
  fireEvent.click(screen.getByRole('button', {name: 'Завершить отправку'}));
  await waitFor(() => expect(clearWorkBatch).toHaveBeenCalledWith({companyId: 2, userId: 11}));
  expect(onRecovered).toHaveBeenCalledWith(completed);
});

it('returns only a definitively rejected remainder to editing', async () => {
  const rejected = {next: 1, rejected: true, commands: [{}, {}]};
  pendingWorkBatch.mockReturnValue(rejected);
  const onRecovered = jest.fn().mockResolvedValue();
  render(<WorkSubmissionRecovery {...props} onRecovered={onRecovered} />);
  fireEvent.click(screen.getByRole('button', {name: 'Вернуться к исправлению'}));
  await waitFor(() => expect(abandonRejectedWorkTail).toHaveBeenCalledWith({companyId: 2, userId: 11}));
  expect(onRecovered).toHaveBeenCalledWith(rejected);
  expect(resumeWorkBatch).not.toHaveBeenCalled();
});

it('loads only the selected company and actor sending', () => {
  pendingWorkBatch.mockImplementation(scope => scope.companyId === 2 && scope.userId === 11 ? {next: 0, commands: [{}]} : null);
  const {rerender} = render(<WorkSubmissionRecovery {...props} />);
  rerender(<WorkSubmissionRecovery {...props} companyContext={{selectedCompanyId: 3}} />);
  expect(screen.queryByRole('region', {name: 'Сохранённая отправка'})).toBeNull();
  rerender(<WorkSubmissionRecovery {...props} user={{id: 12}} />);
  expect(screen.queryByRole('region', {name: 'Сохранённая отправка'})).toBeNull();
});
