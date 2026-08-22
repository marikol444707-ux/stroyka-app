import { fireEvent, render, screen, waitFor } from '@testing-library/react';

import AccountableExpenseReportModal from './AccountableExpenseReportModal';


describe('AccountableExpenseReportModal ownership payload', () => {
  beforeEach(() => {
    global.fetch = jest.fn().mockResolvedValue({ok: true});
    global.alert = jest.fn();
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('inherits the parent project and does not submit client-authored ownership', async () => {
    render(
      <AccountableExpenseReportModal
        reportingPayment={{id: 4, projectId: 19, projectName: 'Лицей', amount: 1000, spentAmount: 0}}
        setReportingPayment={jest.fn()}
        C={{text: '#111', textSec: '#666', border: '#ddd', bg: '#fff', accent: '#f60', textMuted: '#999'}}
        card={{}}
        inp={{}}
        btnO={{}}
        btnG={{}}
        projects={[{id: 99, name: 'Чужой объект'}]}
        expenseCategories={[{id: 'accountable', label: 'Подотчёт'}]}
        newExpense={{description: 'Бензин', amount: '300', photoUrl: '', projectName: 'Чужой объект'}}
        setNewExpense={jest.fn()}
        appendPhotos={jest.fn()}
        fileSrc={value => value}
        expenseSubmitting={false}
        setExpenseSubmitting={jest.fn()}
        API=""
        user={{name: 'Клиентская подмена'}}
        loadAll={jest.fn()}
      />,
    );

    expect(screen.getByText('Объект: Лицей')).toBeInTheDocument();
    expect(screen.queryByRole('option', {name: 'Чужой объект'})).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', {name: /Отправить/}));

    await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(1));
    const [, request] = global.fetch.mock.calls[0];
    const body = JSON.parse(request.body);
    expect(body).toEqual(expect.objectContaining({
      paymentId: 4,
      description: 'Бензин',
      amount: 300,
    }));
    expect(body).not.toHaveProperty('projectName');
    expect(body).not.toHaveProperty('projectId');
    expect(body).not.toHaveProperty('addedBy');
  });
});
