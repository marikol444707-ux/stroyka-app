import React from 'react';
import { render, screen } from '@testing-library/react';
import CommercialComparison from './CommercialComparison';

test('shows full total, excluded quotes and honest model fallback', () => {
  render(<CommercialComparison C={{}} compareResult={{ bestSupplier: 'Вист', ranking: [{ offerId: 1, supplier: 'Вист', totalPrice: 1010, pricePerUnit: 10, deliveryDays: 2, score: 80, vatIncluded: true }], excludedOffers: [{ offerId: 2, supplier: 'Другой', reason: 'Срок действия КП истёк' }] }} />);
  expect(screen.getByText('Сумма КП')).toBeInTheDocument();
  expect(screen.getByText(/1 010 ₽/)).toBeInTheDocument();
  expect(screen.getByText(/Пояснение ИИ недоступно/)).toBeInTheDocument();
  expect(screen.getByText(/Другой: Срок действия/)).toBeInTheDocument();
});

test('no eligible quotes still explains exclusions without announcing a winner', () => {
  render(<CommercialComparison C={{}} compareResult={{ error: 'Нет подходящих КП', excludedOffers: [{ offerId: 2, supplier: 'Другой', reason: 'Проверьте состав' }] }} />);
  expect(screen.getByRole('alert')).toHaveTextContent('Нет подходящих КП');
  expect(screen.getByText(/Другой: Проверьте состав/)).toBeInTheDocument();
  expect(screen.queryByText(/Лучшее по условиям/)).not.toBeInTheDocument();
});
