import { projectPaymentSignedAmountValue as signed, projectPaymentIncomingAmount as incoming,
  projectPaymentOutgoingAmount as outgoing } from './projectPaymentUtils';

test.each(['Аванс', 'Оплата бригаде', 'Оплата счёта'])('ledger ignores arbitrary reason %s', note => {
  const payment = { sourceKind: 'supplier_payment_ledger', operationKind: 'payment', amount: 100, note };
  const reversal = { ...payment, operationKind: 'reversal', amount: -100 };
  expect(signed(payment)).toBe(-100);
  expect(signed(reversal)).toBe(100);
  expect(incoming(payment)).toBe(0);
  expect(incoming(reversal)).toBe(0);
  expect(outgoing(payment) + outgoing(reversal)).toBe(0);
});

test.each([['Оплата бригаде', 100, -100], ['Выплата исполнителю по акту', 20, -20],
  ['Оплата счёта', 30, -30], ['От заказчика', 50, 50], ['Сторно платежа', -10, -10]])(
  'legacy %s preserves existing interpretation', (note, amount, expected) => {
    expect(signed({ note, amount })).toBe(expected);
  });
