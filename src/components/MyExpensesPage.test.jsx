import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import MyExpensesPage from './MyExpensesPage';

test('reimbursed purchase remains visible when staff id differs from user id and name changed', () => {
  render(<MyExpensesPage C={{}} card={{}} btnO={{}} EXPENSE_CATEGORIES={[]} accountablePayments={[]}
    user={{ id: 42, name: 'Новое имя', role: 'субподрядчик' }}
    ownExpenses={[{ id: 1, employeeUserId: 42, employeeId: 23, employeeName: 'Старое имя',
      description: 'Покупка кабеля', status: 'Возмещено', amount: 1500, approvedBy: 'Бухгалтер' }]} />);
  expect(screen.getByText('✅ Возмещено')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: /Старое имя/ }));
  expect(screen.getByText('Покупка кабеля')).toBeInTheDocument();
  expect(screen.getByText('Утв. Бухгалтер')).toBeInTheDocument();
});
