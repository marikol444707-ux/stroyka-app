import React from 'react';
import { render, screen } from '@testing-library/react';
import { PublicProjectPaymentSchedule } from './PublicProjectPaymentSchedule';

test('shows the payment stages and a non-contractual notice', () => {
  render(
    <PublicProjectPaymentSchedule
      packageLabel="Тёплый контур"
      stages={[
        { id: 'start', title: 'Подготовка', percent: 10, min: 700000, max: 900000 },
        { id: 'acceptance', title: 'Приёмка', percent: 90, min: 6300000, max: 8100000 },
      ]}
    />
  );

  expect(screen.getByRole('region', { name: 'Примерный график этапов и платежей' })).toHaveTextContent('Тёплый контур');
  expect(screen.getByText('10%')).toBeInTheDocument();
  expect(screen.getByText('700 тыс. ₽ - 900 тыс. ₽')).toBeInTheDocument();
  expect(screen.getByText(/не является договорным графиком/i)).toBeInTheDocument();
});
