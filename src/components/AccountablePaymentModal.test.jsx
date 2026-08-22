import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

import AccountablePaymentModal from './AccountablePaymentModal';
import { createAccountablePaymentForm } from '../features/payments/paymentInitialForms';


function Harness() {
  const [form, setForm] = React.useState(createAccountablePaymentForm());
  return (
    <AccountablePaymentModal
      showAccountableForm
      setShowAccountableForm={jest.fn()}
      C={{text: '#111', textSec: '#666'}}
      card={{}}
      inp={{}}
      btnO={{}}
      btnG={{}}
      projects={[{id: 19, name: 'Лицей'}]}
      users={[{id: 999, name: 'Устаревший пользователь', role: 'мастер'}]}
      staff={[{id: 23, name: 'Точный сотрудник', role: 'мастер'}]}
      newAccountable={form}
      setNewAccountable={setForm}
      API=""
      user={{id: 8, name: 'Клиентская подмена'}}
      loadAll={jest.fn()}
    />
  );
}


describe('AccountablePaymentModal ownership payload', () => {
  beforeEach(() => {
    global.fetch = jest.fn().mockResolvedValue({ok: true});
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('submits exact project and staff IDs instead of client-authored names', async () => {
    render(<Harness />);
    const selects = screen.getAllByRole('combobox');
    fireEvent.change(selects[0], {target: {value: '19'}});
    fireEvent.change(selects[1], {target: {value: '23'}});
    fireEvent.change(screen.getByPlaceholderText('Сумма *'), {target: {value: '5000'}});
    fireEvent.click(screen.getByRole('button', {name: /Выдать/}));

    await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(1));
    const [, request] = global.fetch.mock.calls[0];
    expect(JSON.parse(request.body)).toEqual(expect.objectContaining({
      projectId: 19,
      givenToId: 23,
      amount: 5000,
    }));
    expect(request.body).not.toContain('Устаревший пользователь');
    expect(request.body).not.toContain('Клиентская подмена');
  });
});
