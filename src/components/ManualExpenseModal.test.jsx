import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

import ManualExpenseModal from './ManualExpenseModal';
import { createManualExpenseForm } from '../features/payments/paymentInitialForms';


function Harness() {
  const [form, setForm] = React.useState(createManualExpenseForm());
  return (
    <ManualExpenseModal
      addExpenseProject="Объект"
      setAddExpenseProject={jest.fn()}
      C={{text: '#111', textSec: '#666', textMuted: '#888', border: '#ddd', bg: '#fff', accent: '#f60'}}
      card={{}}
      inp={{}}
      btnO={{}}
      btnG={{}}
      newManualExpense={form}
      setNewManualExpense={setForm}
      isFinanceRole
      expenseCategories={[{id: 'materials', label: 'Материалы'}]}
      projects={[{id: 41, name: 'Объект'}]}
      visibleActiveProjects={items => items}
      API=""
      user={{id: 91, name: 'Клиентская подмена'}}
      loadAll={jest.fn()}
    />
  );
}


describe('ManualExpenseModal ownership payload', () => {
  beforeEach(() => {
    global.fetch = jest.fn().mockResolvedValue({ok: true});
    window.alert = jest.fn();
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('submits the exact project ID and omits client-authored ownership names', async () => {
    render(<Harness />);
    fireEvent.change(screen.getByPlaceholderText('Сумма (₽) *'), {
      target: {value: '750'},
    });
    fireEvent.click(screen.getByRole('button', {name: /Добавить/}));

    await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(1));
    const [, request] = global.fetch.mock.calls[0];
    const body = JSON.parse(request.body);
    expect(body).toEqual(expect.objectContaining({
      projectId: 41,
      amount: 750,
    }));
    expect(body).not.toHaveProperty('project');
    expect(body).not.toHaveProperty('addedBy');
    expect(request.body).not.toContain('Клиентская подмена');
  });
});
