import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import SupplierEmailAttempts from './SupplierEmailAttempts';
const row = { id: 3, requestId: 7, companyId: 2, emailRetryAttemptId: 9, emailAttempts: [{ id: 9, outcome: 'rejected', code: 'smtp_rejected', startedAt: '2026-09-20T12:00:00Z' }] };
afterEach(() => { jest.restoreAllMocks(); });
test('explicit retry carries tenant and observed attempt and suppresses double click', async () => {
  let resolve;
  global.fetch = jest.fn(() => new Promise(r => { resolve = r; }));
  const onRefresh = jest.fn();
  render(<SupplierEmailAttempts row={row} canRetry onRefresh={onRefresh} />);
  fireEvent.click(screen.getByRole('button')); fireEvent.click(screen.getByRole('button'));
  expect(fetch).toHaveBeenCalledTimes(1);
  const [url, options] = fetch.mock.calls[0];
  expect(url).toBe('/supply-requests/7/recipients/3/retry-email');
  expect(options.headers['X-Company-Id']).toBe('2');
  expect(JSON.parse(options.body)).toEqual({ expectedAttemptId: 9 });
  resolve({ ok: true, json: async () => ({ ok: true }) });
  await waitFor(() => expect(onRefresh).toHaveBeenCalledTimes(1));
});
test('unknown attempts have history without a retry button', () => {
  render(<SupplierEmailAttempts row={{ ...row, emailRetryAttemptId: null, emailAttempts: [{ ...row.emailAttempts[0], outcome: 'unconfirmed' }] }} canRetry />);
  expect(screen.queryByRole('button')).toBeNull();
  expect(screen.getByText(/Результат не подтверждён/)).toBeTruthy();
});
