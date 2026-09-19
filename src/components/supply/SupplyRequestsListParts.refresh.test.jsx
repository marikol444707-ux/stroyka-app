import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { OffersBlock } from './SupplyRequestsListParts';

const offer = { id: 7, requestId: 1, supplierId: 3, status: 'Получено', pricePerUnit: 10, totalPrice: 20 };
const props = { API: '/api', C: {}, badge: () => ({}), request: { id: 1, companyId: 2 },
  user: { id: 8 }, companyContext: { selectedCompanyId: 2 }, supplierOffers: [offer],
  compareResultByReq: {}, suppliers: [{ id: 3, name: 'Поставщик' }], parseOfferItems: () => [], canApprove: true };
const originalFetch = global.fetch;
afterEach(() => { global.fetch = originalFetch; });
it('refreshes the displayed quote together with recipient evidence', async () => {
  global.fetch = jest.fn(async url => ({ ok: true, json: async () => url.endsWith('/recipients')
    ? [{ id: 4, actualMaxQueueStatus: 'failed' }] : [{ ...offer, pricePerUnit: 30, totalPrice: 60, supplierMessage: 'Новые условия' }] }));
  render(<OffersBlock {...props} />);
  fireEvent.click(screen.getByRole('button', { name: 'Обновить КП и уведомления' }));
  await screen.findByText('💬 «Новые условия»');
  expect(screen.getByText('MAX: Ошибка отправки в MAX')).toBeInTheDocument();
  expect(global.fetch).toHaveBeenCalledTimes(2);
});
it('rejects malformed successful JSON and hides stale selection actions', async () => {
  global.fetch = jest.fn(async () => ({ ok: true, json: async () => ({}) }));
  render(<OffersBlock {...props} />);
  fireEvent.click(screen.getByRole('button', { name: 'Обновить КП и уведомления' }));
  await screen.findByRole('alert');
  expect(screen.queryByRole('button', { name: 'Выбрать' })).not.toBeInTheDocument();
  expect(screen.queryByText('Получатели КП не зафиксированы.')).not.toBeInTheDocument();
});
it('discards an old company response after switching context', async () => {
  const finishes = [];
  global.fetch = jest.fn(() => new Promise(resolve => { finishes.push(resolve); }));
  const { rerender } = render(<OffersBlock {...props} />);
  fireEvent.click(screen.getByRole('button', { name: 'Обновить КП и уведомления' }));
  rerender(<OffersBlock {...props} request={{ id: 2, companyId: 9 }} companyContext={{ selectedCompanyId: 9 }} supplierOffers={[]} />);
  await act(async () => { finishes.forEach(finish => finish({ ok: true, json: async () => [{ ...offer, supplierMessage: 'Чужие данные' }] })); });
  await waitFor(() => expect(screen.queryByText(/Чужие данные/)).not.toBeInTheDocument());
});
