import React from 'react';
import { render, screen } from '@testing-library/react';
import CommercialComparison from './CommercialComparison';

test('shows full total, excluded quotes and honest model fallback', () => {
  render(<CommercialComparison C={{}} compareResult={{ bestSupplier: 'Вист', ranking: [{ offerId: 1, supplier: 'Вист', totalPrice: 1010, pricePerUnit: 10, deliveryDays: 2, score: 80, vatIncluded: true }], excludedOffers: [{ offerId: 2, supplier: 'Другой', reason: 'Срок действия КП истёк' }] }} />);
  expect(screen.getByText('Сумма КП')).toBeInTheDocument();
  expect(screen.getByText(/^1 010 ₽$/)).toBeInTheDocument();
  expect(screen.getByText(/Пояснение ИИ сейчас недоступно/)).toBeInTheDocument();
  expect(screen.getByText(/Другой: Срок действия/)).toBeInTheDocument();
});

test('no eligible quotes still explains exclusions without announcing a winner', () => {
  render(<CommercialComparison C={{}} compareResult={{ error: 'Нет подходящих КП', excludedOffers: [{ offerId: 2, supplier: 'Другой', reason: 'Проверьте состав' }] }} />);
  expect(screen.getByRole('alert')).toHaveTextContent('Нет подходящих КП');
  expect(screen.getByText(/Другой: Проверьте состав/)).toBeInTheDocument();
  expect(screen.queryByText(/ЛУЧШЕЕ ПРЕДЛОЖЕНИЕ/)).not.toBeInTheDocument();
});

 test('explains the next step without approving the recommended offer', () => {
  render(<CommercialComparison C={{}} compareResult={{bestOfferId: 2, bestSupplier: 'Вист', aiText: 'Полная заявка дешевле', ranking: [{offerId: 2, supplier: 'Вист', totalPrice: 1200, deliveryDays: 1}]}} />);
  expect(screen.getByText(/Почему этот вариант/)).toHaveTextContent('Полная заявка дешевле');
  expect(screen.getByText(/нажмите «Выбрать»/)).toBeInTheDocument();
  expect(screen.getByText('Это рекомендация. Поставщик пока не выбран.')).toBeInTheDocument();
  expect(screen.queryByRole('button', {name: 'Выбрать'})).not.toBeInTheDocument();
});

test('does not claim an approved supplier is unselected', () => {
 render(<CommercialComparison C={{}} hasSelectedOffer compareResult={{bestSupplier: 'Вист', ranking: []}} />);
 expect(screen.getByText('Поставщик уже выбран. Сравнение не меняет ваш выбор.')).toBeInTheDocument();
 expect(screen.queryByText('Это рекомендация. Поставщик пока не выбран.')).not.toBeInTheDocument();
});
