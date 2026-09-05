import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

import OwnExpenseFormModal from './OwnExpenseFormModal';
import { createOwnExpenseForm } from '../features/payments/paymentInitialForms';


function Harness({setShowOwnExpenseForm = jest.fn(), loadAll = jest.fn(), notify = jest.fn()}) {
  const [form, setForm] = React.useState(createOwnExpenseForm());
  return (
    <OwnExpenseFormModal
      showOwnExpenseForm
      setShowOwnExpenseForm={setShowOwnExpenseForm}
      C={{text: '#111', textSec: '#666', textMuted: '#888', border: '#ddd', bg: '#fff', accent: '#f60'}}
      card={{}}
      inp={{}}
      btnO={{}}
      btnG={{}}
      projectOptions={[{id: 41, name: 'Объект'}]}
      expenseCategories={[{id: 'other', label: 'Прочее'}]}
      newOwnExpense={form}
      setNewOwnExpense={setForm}
      API=""
      user={{id: 999, name: 'Клиентская подмена'}}
      loadAll={loadAll}
      notify={notify}
    />
  );
}


describe('OwnExpenseFormModal ownership payload', () => {
  beforeEach(() => {
    global.fetch = jest.fn().mockResolvedValue({ok: true});
    window.alert = jest.fn();
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('submits an exact project ID and no client-authored employee identity', async () => {
    render(<Harness />);
    fireEvent.change(screen.getAllByRole('combobox')[0], {target: {value: '41'}});
    fireEvent.change(screen.getByPlaceholderText('За что потрачено *'), {
      target: {value: 'Бензин'},
    });
    fireEvent.change(screen.getByPlaceholderText('Сумма (₽) *'), {
      target: {value: '500'},
    });
    fireEvent.click(screen.getByRole('button', {name: /Отправить/}));

    await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(1));
    const [, request] = global.fetch.mock.calls[0];
    const body = JSON.parse(request.body);
    expect(body).toEqual(expect.objectContaining({projectId: 41, amount: 500}));
    expect(body).not.toHaveProperty('projectName');
    expect(body).not.toHaveProperty('employeeId');
    expect(body).not.toHaveProperty('employeeName');
    expect(request.body).not.toContain('Клиентская подмена');
  });

  it('keeps the form open and shows the backend detail when creation is rejected', async () => {
    const setShowOwnExpenseForm = jest.fn();
    const loadAll = jest.fn();
    const notify = jest.fn();
    global.fetch.mockResolvedValue({
      ok: false,
      status: 409,
      json: jest.fn().mockResolvedValue({
        detail: 'Аккаунт не связан с карточкой сотрудника',
      }),
    });

    render(
      <Harness
        setShowOwnExpenseForm={setShowOwnExpenseForm}
        loadAll={loadAll}
        notify={notify}
      />
    );
    fireEvent.change(screen.getByPlaceholderText('За что потрачено *'), {
      target: {value: 'Бензин'},
    });
    fireEvent.change(screen.getByPlaceholderText('Сумма (₽) *'), {
      target: {value: '500'},
    });
    fireEvent.click(screen.getByRole('button', {name: /Отправить/}));

    await waitFor(() => expect(window.alert).toHaveBeenCalledWith(
      'Аккаунт не связан с карточкой сотрудника'
    ));
    expect(setShowOwnExpenseForm).not.toHaveBeenCalled();
    expect(loadAll).not.toHaveBeenCalled();
    expect(notify).not.toHaveBeenCalled();
    expect(screen.getByPlaceholderText('За что потрачено *')).toHaveValue('Бензин');
  });
});
