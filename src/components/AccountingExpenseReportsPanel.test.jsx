import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

import AccountingExpenseReportsPanel from './AccountingExpenseReportsPanel';
import { createExpenseReportForm } from '../features/payments/paymentInitialForms';


function Harness() {
  const [form, setForm] = React.useState(createExpenseReportForm());
  return (
    <AccountingExpenseReportsPanel
      C={{text: '#111', textSec: '#666', textMuted: '#999', bg: '#fff'}}
      card={{}}
      inp={{}}
      btnO={{}}
      btnG={{}}
      btnR={{}}
      staff={[{id: 100, name: 'Точный сотрудник'}]}
      projects={[{id: 19, name: 'Точный объект'}]}
      newExpenseReport={form}
      setNewExpenseReport={setForm}
      refreshData={jest.fn()}
      expenseReports={[]}
      user={{name: 'Клиентская подмена'}}
      badge={jest.fn(() => ({}))}
    />
  );
}


describe('AccountingExpenseReportsPanel ownership payload', () => {
  beforeEach(() => {
    global.fetch = jest.fn().mockResolvedValue({ok: true});
    global.alert = jest.fn();
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('submits stored project and staff IDs without client-owned names', async () => {
    render(<Harness />);
    const selects = screen.getAllByRole('combobox');
    fireEvent.change(selects[1], {target: {value: '100'}});
    fireEvent.change(selects[2], {target: {value: '19'}});
    fireEvent.change(screen.getByPlaceholderText('Назначение *'), {
      target: {value: 'Материалы'},
    });
    fireEvent.change(screen.getByPlaceholderText('Выдано (₽) *'), {
      target: {value: '1000'},
    });
    fireEvent.change(screen.getByPlaceholderText('Потрачено (₽)'), {
      target: {value: '300'},
    });
    fireEvent.click(screen.getByRole('button', {name: /Сохранить/}));

    await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(1));
    const [, request] = global.fetch.mock.calls[0];
    const body = JSON.parse(request.body);
    expect(body).toEqual(expect.objectContaining({
      projectId: 19,
      employeeId: 100,
      issuedAmount: 1000,
      spentAmount: 300,
    }));
    expect(body).not.toHaveProperty('projectName');
    expect(body).not.toHaveProperty('employeeName');
    expect(body).not.toHaveProperty('approvedBy');
    expect(request.body).not.toContain('Клиентская подмена');
  });
});
