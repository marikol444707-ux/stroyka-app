import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import Panel from './SupplierOpeningPanel';
import { previewOpening, readOpeningPending, submitOpening } from './openingClient';
jest.mock('./openingClient');
const props = { API: '/api', userId: 7, companyId: 2, invoiceId: 12, onSuccess: jest.fn(), onBlocked: jest.fn() };
const preview = { companyId: 2, invoiceId: 12, amount: '200.00', openingPaid: '50.00', remainingAmount: '150.00', newCashAmount: '0.00', reviewedHash: 'a'.repeat(64) };
const originalFlag = process.env.REACT_APP_SUPPLIER_OPENING_CONFIRMATIONS_ENABLED;
beforeEach(() => {
  jest.clearAllMocks(); process.env.REACT_APP_SUPPLIER_OPENING_CONFIRMATIONS_ENABLED = 'true';
  readOpeningPending.mockReturnValue(null); previewOpening.mockResolvedValue(preview);
  submitOpening.mockResolvedValue({ openingPaid: '50.00' });
});
afterAll(() => { if (originalFlag === undefined) delete process.env.REACT_APP_SUPPLIER_OPENING_CONFIRMATIONS_ENABLED;
  else process.env.REACT_APP_SUPPLIER_OPENING_CONFIRMATIONS_ENABLED = originalFlag; });
test('requires preview, reason and explicit confirmation', async () => {
  render(<Panel {...props} />);
  expect(previewOpening).not.toHaveBeenCalled();
  fireEvent.click(screen.getByText('Сверить прежнюю оплату'));
  const button = await screen.findByText('Подтвердить начальный остаток');
  expect(button).toBeDisabled();
  fireEvent.change(screen.getByLabelText('Основание сверки'), { target: { value: 'Выписка №42' } });
  fireEvent.click(screen.getByLabelText('Суммы сверены с документами'));
  fireEvent.click(button);
  expect(await screen.findByText(/Начальный остаток подтверждён/)).toBeInTheDocument();
  expect(submitOpening).toHaveBeenCalledTimes(1);
  expect(submitOpening.mock.calls[0][0].reason).toBe('Выписка №42');
  expect(props.onSuccess).toHaveBeenCalledTimes(1);
});
test('restores pending even after the invoice is registered', async () => {
  const saved = { preview, body: { reason: 'Прежняя сверка' } };
  readOpeningPending.mockReturnValue(saved);
  render(<Panel {...props} registered />);
  fireEvent.click(await screen.findByText('Повторить подтверждение'));
  await waitFor(() => expect(submitOpening).toHaveBeenCalledWith(expect.objectContaining({ expectedPending: saved })));
  expect(previewOpening).not.toHaveBeenCalled();
});
test('late preview from previous company is not displayed', async () => {
  let resolve;
  previewOpening.mockImplementation(() => new Promise(done => { resolve = done; }));
  const view = render(<Panel {...props} />);
  fireEvent.click(screen.getByText('Сверить прежнюю оплату'));
  view.rerender(<Panel {...props} companyId={3} />);
  resolve(preview);
  await waitFor(() => expect(screen.queryByText('Подтвердить начальный остаток')).not.toBeInTheDocument());
});
test('default off and registered without pending hide the form', () => {
  const view = render(<Panel {...props} registered />);
  expect(screen.queryByText('Сверить прежнюю оплату')).not.toBeInTheDocument();
  delete process.env.REACT_APP_SUPPLIER_OPENING_CONFIRMATIONS_ENABLED;
  view.rerender(<Panel {...props} />);
  expect(view.container).toBeEmptyDOMElement();
});

test('stale review is discarded and requires a fresh preview and confirmation', async () => {
  submitOpening.mockRejectedValueOnce(Object.assign(new Error('Счёт изменился'), { status: 409 }));
  render(<Panel {...props} />);
  fireEvent.click(screen.getByText('Сверить прежнюю оплату'));
  await screen.findByText('Подтвердить начальный остаток');
  fireEvent.change(screen.getByLabelText('Основание сверки'), { target: { value: 'Выписка' } });
  fireEvent.click(screen.getByLabelText('Суммы сверены с документами'));
  fireEvent.click(screen.getByText('Подтвердить начальный остаток'));
  expect(await screen.findByText('Счёт изменился')).toBeInTheDocument();
  expect(screen.queryByText('Подтвердить начальный остаток')).not.toBeInTheDocument();
  fireEvent.click(screen.getByText('Обновить сверку'));
  expect(await screen.findByText('Подтвердить начальный остаток')).toBeDisabled();
  expect(screen.getByLabelText('Суммы сверены с документами')).not.toBeChecked();
});
