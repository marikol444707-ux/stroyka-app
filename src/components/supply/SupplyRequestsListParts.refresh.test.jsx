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
it('keeps comparison discoverable and explains the missing response', () => {
  render(<OffersBlock {...props} />);
  expect(screen.getByRole('button', { name: 'Сравнить предложения' })).toBeDisabled();
  expect(screen.getByText(/Получено: 1 из 2/)).toBeInTheDocument();
});
it('compares the current request when two suppliers have replied', () => {
  const compare = jest.fn();
  render(<OffersBlock {...props} runCompareKp={compare} supplierOffers={[offer, {...offer, id: 9, supplierId: 4}]} />);
  fireEvent.click(screen.getByRole('button', { name: 'Сравнить предложения' }));
  expect(compare).toHaveBeenCalledWith(1);
});
it('marks only the current comparison winner and ignores old AI flags', () => {
  render(<OffersBlock {...props} supplierOffers={[{...offer, aiRecommended: true}, {...offer, id: 9, supplierId: 4}]} compareResultByReq={{1: {bestOfferId: 9, bestSupplier: 'Другой', ranking: []}}} />);
  expect(screen.getAllByText('Лучшее по сравнению')).toHaveLength(1);
  expect(screen.queryByText('🤖 AI рек.')).not.toBeInTheDocument();
});
it('does not label a quote recommended when comparison fails', () => {
  render(<OffersBlock {...props} compareResultByReq={{1: {bestOfferId: 7, error: 'Сравнение недоступно'}}} />);
  expect(screen.queryByText('Лучшее по сравнению')).not.toBeInTheDocument();
});
it('opens and focuses the recommended card without selecting the supplier', () => {
  const originalScroll = HTMLElement.prototype.scrollIntoView;
  const scroll = jest.fn();
  HTMLElement.prototype.scrollIntoView = scroll;
  const select = jest.fn();
  try {
    render(<OffersBlock {...props} selectSupplierOffer={select} compareResultByReq={{1: {bestOfferId: 7, bestSupplier: 'Поставщик', ranking: []}}} />);
    fireEvent.click(screen.getByRole('button', { name: 'Открыть предложение' }));
    expect(document.activeElement).toBe(document.getElementById('request-1-offer-7'));
    expect(scroll).toHaveBeenCalledWith({block: 'center'});
    expect(select).not.toHaveBeenCalled();
  } finally {
    HTMLElement.prototype.scrollIntoView = originalScroll;
  }
});
