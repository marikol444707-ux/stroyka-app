import { fireEvent, render, screen } from '@testing-library/react';

import SubscriptionExpiryNotice from './SubscriptionExpiryNotice';


const expiringCompany = {
  companyName: 'СтройТест',
  plan: 'business',
  planExpiresAt: '2026-09-09',
  billingState: {
    status: 'payment_expiring',
    daysLeft: 7,
  },
};

test('shows a seven-day renewal warning to the company director', () => {
  const onOpenChat = jest.fn();

  render(
    <SubscriptionExpiryNotice
      company={expiringCompany}
      role="директор"
      onOpenChat={onOpenChat}
    />,
  );

  expect(screen.getByText('Подписка закончится через 7 дней')).toBeInTheDocument();
  expect(screen.getByText(/Продлите тариф до 9 сентября 2026/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Открыть чат' }));
  expect(onOpenChat).toHaveBeenCalledTimes(1);
});

test('does not show the billing warning to a non-director', () => {
  const { container } = render(
    <SubscriptionExpiryNotice company={expiringCompany} role="прораб" />,
  );

  expect(container).toBeEmptyDOMElement();
});

test('keeps an expired subscription visible until it is renewed', () => {
  render(
    <SubscriptionExpiryNotice
      company={{
        ...expiringCompany,
        billingState: { status: 'payment_expired', daysLeft: -2 },
      }}
      role="директор"
    />,
  );

  expect(screen.getByText('Подписка закончилась')).toBeInTheDocument();
  expect(screen.getByText(/Компания работает в режиме «только просмотр»/)).toBeInTheDocument();
});

test('shows the read-only notice for a softly frozen company', () => {
  render(
    <SubscriptionExpiryNotice
      company={{
        ...expiringCompany,
        billingState: { status: 'soft_frozen' },
      }}
      role="директор"
    />,
  );

  expect(screen.getByText('Подписка закончилась')).toBeInTheDocument();
  expect(screen.getByText(/создание и изменения заблокированы/)).toBeInTheDocument();
});
