import React from 'react';
import { render, screen } from '@testing-library/react';
import SupplierPaymentDeadline from './SupplierPaymentDeadline';

const value = { schemaVersion: 1, asOf: '2026-09-18', invoiceId: 11, status: 'active',
  stages: [{ title: 'Остаток', amount: '100.00', daysAfter: 30, dueDate: '2026-09-25', remainingDays: 7 }] };

test('shows shipment deferral and a week remaining without asserting unpaid stage', () => {
  render(<SupplierPaymentDeadline value={value} />);
  expect(screen.getByText(/Осталось 7 дн/)).toBeInTheDocument();
  expect(screen.getByText(/30 календарных дней после приёмки/)).toBeInTheDocument();
  expect(screen.getByText(/25.09.2026/)).toBeInTheDocument();
  expect(screen.getByText(/счёту #11/)).toBeInTheDocument();
});
test.each([[0, /Срок сегодня/], [-3, /Срок прошёл 3 дн/]])('shows deadline %s', (days, label) => {
  render(<SupplierPaymentDeadline value={{ ...value, stages: [{ ...value.stages[0], remainingDays: days }] }} />);
  expect(screen.getByText(label)).toBeInTheDocument();
});
test.each([['paid', /Счёт полностью оплачен/], ['cancelled', /Счёт аннулирован/],
  ['review_required', /Срок оплаты требует проверки/], ['waiting_acceptance', /Ожидается приёмка/]])('shows %s', (status, label) => {
  render(<SupplierPaymentDeadline value={{ ...value, status }} />);
  expect(screen.getByText(label)).toBeInTheDocument();
  expect(screen.queryByText(/Осталось 7/)).not.toBeInTheDocument();
});
test('hides legacy and fails closed on malformed projection', () => {
  const { container, rerender } = render(<SupplierPaymentDeadline />);
  expect(container).toBeEmptyDOMElement();
  rerender(<SupplierPaymentDeadline value={{ ...value, stages: [{}] }} />);
  expect(screen.getByRole('alert')).toHaveTextContent('требует проверки');
});
