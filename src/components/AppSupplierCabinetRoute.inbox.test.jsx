import React from 'react';
import { act, render, screen, waitFor } from '@testing-library/react';
import AppSupplierCabinetRoute from './AppSupplierCabinetRoute';
jest.mock('../features/supply/SupplierCabinetPage', () => props => <div>
  <span>{props.inboxState?.status}</span><span>{props.inboxState?.error}</span>
  <span>{(props.supplierOffers || []).map(row => row.supplierName).join(',')}</span>
  <button onClick={props.refreshData}>Обновить</button>
</div>);
const originalFetch = global.fetch;
const ok = value => ({ ok: true, json: async () => value });
afterEach(() => { global.fetch = originalFetch; });
function route(id = 1) { return <AppSupplierCabinetRoute ui={{ API: '/api' }} data={{ user: { id, role: 'поставщик' }, supplierOffers: [], supplyRequests: [] }} />; }
it('loads addressed offers on ordinary supplier entry without visiting an internal page', async () => {
  global.fetch = jest.fn(async url => ok(url.endsWith('/supplier-offers') ? [{ id: 2, requestId: 3, supplierName: 'Мой запрос' }] : [{ id: 3 }]));
  render(route());
  await screen.findByText('Мой запрос');
  expect(global.fetch).toHaveBeenCalledWith('/api/supplier-offers', expect.any(Object));
});
it('shows an error instead of an empty success when either request fails', async () => {
  global.fetch = jest.fn(async () => ({ ok: false, status: 503, json: async () => ({ detail: 'Сервис недоступен' }) }));
  render(route()); await screen.findByText('error');
  expect(screen.getByText(/Сервис недоступен/)).toBeInTheDocument();
});
it('ignores old account responses after the supplier changes', async () => {
  const old = [];
  global.fetch = jest.fn(url => new Promise(resolve => old.push({ url, resolve })));
  const { rerender } = render(route(1));
  await waitFor(() => expect(old).toHaveLength(4));
  global.fetch = jest.fn(async () => ok([]));
  rerender(route(2)); await screen.findByText('ready');
  await act(async () => { old.forEach(({ url, resolve }) => resolve(ok(url.endsWith('/supplier-offers') ? [{ id: 2, requestId: 3, supplierName: 'Чужой запрос' }] : [{ id: 3 }]))); });
  expect(screen.queryByText('Чужой запрос')).not.toBeInTheDocument();
});
it('recovers explicitly after a failed read and distinguishes a confirmed empty inbox', async () => {
  global.fetch = jest.fn(async () => ({ ok: false, status: 502, json: async () => { throw Error(); } }));
  render(route()); await screen.findByText('error');
  global.fetch = jest.fn(async () => ok([]));
  await act(async () => { screen.getByRole('button', { name: 'Обновить' }).click(); });
  await screen.findByText('ready');
  expect(screen.queryByText(/502/)).not.toBeInTheDocument();
});
it('never shows a half-loaded inbox if an offer is missing its request', async () => {
  global.fetch = jest.fn(async url => ok(url.endsWith('/supplier-offers') ? [{ id: 2, requestId: 3, supplierName: 'Неполный запрос' }] : []));
  render(route()); await screen.findByText('error');
  expect(screen.queryByText('Неполный запрос')).not.toBeInTheDocument();
});
it('finishes a stalled load with a visible timeout rather than an endless spinner', async () => {
  jest.useFakeTimers();
  try {
    global.fetch = jest.fn((_, options) => new Promise((resolve, reject) => {
      options.signal.addEventListener('abort', () => reject(Object.assign(new Error('aborted'), { name: 'AbortError' })));
    }));
    render(route());
    await act(async () => { jest.advanceTimersByTime(20000); });
    expect(screen.getByText('error')).toBeInTheDocument();
    expect(screen.getByText(/20 секунд/)).toBeInTheDocument();
  } finally { jest.useRealTimers(); }
});
