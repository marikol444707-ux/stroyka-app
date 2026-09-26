import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import AccountingIncomingPaymentForm from './AccountingIncomingPaymentForm';

const companies = [
  { companyId: 2, companyName: 'Строй А', role: 'бухгалтер' },
  { companyId: 3, companyName: 'Строй Б', role: 'директор' },
  { companyId: 4, companyName: 'Только просмотр', role: 'прораб' },
];
const projects = [{ id: 10, companyId: 2, name: 'Жилой комплекс' },
  { id: 20, companyId: 3, name: 'Жилой комплекс' }];
const defaults = { C: {}, card: {}, inp: {}, btnO: {}, btnG: {}, projects,
  companyContext: { mode: 'company', selectedCompanyId: 2, companies, setSelectedCompanyId: jest.fn() },
  user: { name: 'Бухгалтер' }, onClose: jest.fn(), refreshData: jest.fn() };
const originalFetch = global.fetch;
beforeEach(() => { global.fetch = jest.fn().mockResolvedValue({ ok: true, json: async () => ({ ok: true }) }); jest.clearAllMocks(); });
afterEach(() => { global.fetch = originalFetch; });
const submit = () => {
  fireEvent.change(screen.getByLabelText('Объект поступления'), { target: { value: '10' } });
  fireEvent.change(screen.getByLabelText('Сумма, ₽'), { target: { value: '1200' } });
  fireEvent.click(screen.getByRole('button', { name: 'Сохранить поступление' }));
};

test('same-name foreign project is excluded; submission uses selected company', async () => {
  render(<AccountingIncomingPaymentForm {...defaults} />);
  expect(screen.getAllByRole('option', { name: /Жилой комплекс/ })).toHaveLength(1);
  expect(screen.queryByRole('option', { name: /Только просмотр/ })).not.toBeInTheDocument();
  submit();
  await waitFor(() => expect(defaults.onClose).toHaveBeenCalled());
  expect(JSON.parse(global.fetch.mock.calls[0][1].body)).toMatchObject({ companyId: 2, projectName: 'Жилой комплекс', amount: 1200 });
  expect(defaults.refreshData).toHaveBeenCalled();
});

test('all-company view requires switching the real company context before saving', () => {
  render(<AccountingIncomingPaymentForm {...defaults} companyContext={{ ...defaults.companyContext, mode: 'all_companies', selectedCompanyId: null }} />);
  expect(screen.getByRole('button', { name: 'Сохранить поступление' })).toBeDisabled();
  fireEvent.change(screen.getByLabelText('Компания поступления'), { target: { value: '3' } });
  expect(defaults.companyContext.setSelectedCompanyId).toHaveBeenCalledWith('3');
  expect(global.fetch).not.toHaveBeenCalled();
});

test('duplicate names within one company cannot be selected', () => {
  render(<AccountingIncomingPaymentForm {...defaults} projects={[...projects, { id: 11, companyId: 2, name: 'Жилой комплекс' }]} />);
  for (const option of screen.getAllByRole('option', { name: /Жилой комплекс/ })) expect(option).toBeDisabled();
  expect(screen.getByText(/одинаковыми названиями/)).toBeInTheDocument();
  submit();
  expect(global.fetch).not.toHaveBeenCalled();
});

test('revoked company or stale catalog cannot submit previously selected project', () => {
  const view = render(<AccountingIncomingPaymentForm {...defaults} />);
  fireEvent.change(screen.getByLabelText('Объект поступления'), { target: { value: '10' } });
  fireEvent.change(screen.getByLabelText('Сумма, ₽'), { target: { value: '1200' } });
  view.rerender(<AccountingIncomingPaymentForm {...defaults} projects={[projects[1]]} />);
  fireEvent.click(screen.getByRole('button', { name: 'Сохранить поступление' }));
  expect(global.fetch).not.toHaveBeenCalled();
  view.rerender(<AccountingIncomingPaymentForm {...defaults} companyContext={{ ...defaults.companyContext, companies: [] }} />);
  expect(screen.getByRole('button', { name: 'Сохранить поступление' })).toBeDisabled();
});

test('server rejection keeps form open and preserves entered amount', async () => {
  global.fetch.mockResolvedValue({ ok: false, json: async () => ({ detail: 'Компания недоступна' }) });
  render(<AccountingIncomingPaymentForm {...defaults} />);
  submit();
  expect(await screen.findByRole('alert')).toHaveTextContent('Компания недоступна');
  expect(screen.getByLabelText('Сумма, ₽')).toHaveValue(1200);
  expect(defaults.onClose).not.toHaveBeenCalled();
});

test('read-only or inactive finance memberships are not writable choices', () => {
  render(<AccountingIncomingPaymentForm {...defaults} companyContext={{ ...defaults.companyContext,
    companies: [{ ...companies[0], readOnly: true }, { ...companies[1], active: false }] }} />);
  expect(screen.queryByRole('option', { name: 'Строй А' })).not.toBeInTheDocument();
  expect(screen.queryByRole('option', { name: 'Строй Б' })).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Сохранить поступление' })).toBeDisabled();
});

test('pending save disables editing and prevents a second request', async () => {
  let complete;
  global.fetch.mockReturnValue(new Promise(resolve => { complete = resolve; }));
  render(<AccountingIncomingPaymentForm {...defaults} />);
  submit();
  expect(screen.getByLabelText('Компания поступления')).toBeDisabled();
  expect(screen.getByLabelText('Сумма, ₽')).toBeDisabled();
  fireEvent.submit(screen.getByRole('form', { name: 'Поступление от заказчика' }));
  expect(global.fetch).toHaveBeenCalledTimes(1);
  complete({ ok: true, json: async () => ({ ok: true }) });
  await waitFor(() => expect(defaults.onClose).toHaveBeenCalled());
});

test('switching company resets form and exposes only the new company project', async () => {
  function Switchable() {
    const [selected, setSelected] = React.useState(2);
    return <AccountingIncomingPaymentForm {...defaults} key={selected} companyContext={{
      ...defaults.companyContext, selectedCompanyId: selected, setSelectedCompanyId: setSelected }} />;
  }
  render(<Switchable />);
  fireEvent.change(screen.getByLabelText('Сумма, ₽'), { target: { value: '777' } });
  fireEvent.change(screen.getByLabelText('Компания поступления'), { target: { value: '3' } });
  expect(screen.getByLabelText('Сумма, ₽')).toHaveValue(null);
  expect(screen.queryByRole('option', { name: /#10/ })).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('Объект поступления'), { target: { value: '20' } });
  fireEvent.change(screen.getByLabelText('Сумма, ₽'), { target: { value: '500' } });
  fireEvent.click(screen.getByRole('button', { name: 'Сохранить поступление' }));
  await waitFor(() => expect(defaults.onClose).toHaveBeenCalled());
  expect(JSON.parse(global.fetch.mock.calls[0][1].body)).toMatchObject({ companyId: 3, amount: 500 });
});
