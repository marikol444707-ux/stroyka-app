import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import SupplierPaymentDialog from './SupplierPaymentDialog';
import useSupplierPaymentDialog from './useSupplierPaymentDialog';

jest.mock('./useSupplierPaymentDialog');
const props = { API: '/api', userId: 4, companyId: 2, documentKind: 'warehouse', documentId: 7, onClose: jest.fn() };
let state;
const originalFlag = process.env.REACT_APP_SUPPLIER_PAYMENTS_ENABLED;
beforeEach(() => {
  jest.clearAllMocks(); process.env.REACT_APP_SUPPLIER_PAYMENTS_ENABLED = 'true';
  state = { loading: false, busy: false, error: '', storageError: '', pending: null, success: null,
    snapshot: { canonicalTarget: { documentKind: 'invoice', documentId: 9 }, remainingAmount: '200.00',
      scope: { projectName: 'Объект', workPackage: 'Основная', supplierId: 3 } },
    history: { items: [], hasMore: false }, draft: { amount: '', paidAt: '', reason: '' },
    submit: jest.fn(), retry: jest.fn(), reload: jest.fn(), updateDraft: jest.fn(), startNext: jest.fn() };
  useSupplierPaymentDialog.mockImplementation(() => state);
});
afterAll(() => { if (originalFlag === undefined) delete process.env.REACT_APP_SUPPLIER_PAYMENTS_ENABLED;
  else process.env.REACT_APP_SUPPLIER_PAYMENTS_ENABLED = originalFlag; });

test('default-off does not render or start the hook', () => {
  delete process.env.REACT_APP_SUPPLIER_PAYMENTS_ENABLED;
  const { container } = render(<SupplierPaymentDialog {...props} />);
  expect(container).toBeEmptyDOMElement(); expect(useSupplierPaymentDialog).not.toHaveBeenCalled();
});
test('canonical scope, labelled exact-money fields, and keyboard close', () => {
  render(<SupplierPaymentDialog {...props} />);
  expect(screen.getByText(/счёт #9/)).toBeInTheDocument();
  expect(screen.getByText(/накладная #7/)).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('Сумма, ₽'), { target: { value: '10,01' } });
  expect(state.updateDraft).toHaveBeenCalledWith({ amount: '10,01' });
  expect(screen.getByLabelText('Дата оплаты')).toHaveAttribute('type', 'date');
  expect(screen.getByLabelText('Основание платежа')).toBeInTheDocument();
  fireEvent.submit(screen.getByRole('form', { name: 'Запись платежа' }));
  expect(state.submit).toHaveBeenCalledTimes(1);
  fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' }); expect(props.onClose).toHaveBeenCalledTimes(1);
});
test('failed read still displays exact saved command and retry, without discard', () => {
  state.snapshot = null; state.history = null; state.error = 'not_found';
  state.pending = { userId: 4, companyId: 2, version: 1, body: { requestId: 'stored-uuid', kind: 'payment',
    documentKind: 'invoice', documentId: 15, amount: '17.01', paidAt: '2026-09-18', reason: 'Точный текст' } };
  render(<SupplierPaymentDialog {...props} />);
  expect(screen.getByText('not_found')).toBeInTheDocument();
  const command = screen.getByLabelText('Сохранённая команда');
  expect(JSON.parse(command.textContent)).toEqual(state.pending);
  fireEvent.click(screen.getByRole('button', { name: 'Повторить сохранённый запрос' }));
  expect(state.retry).toHaveBeenCalledTimes(1);
  expect(screen.queryByRole('button', { name: /удалить/i })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Записать платёж' })).not.toBeInTheDocument();
});
test('busy disables inputs; success requires explicit new intent', () => {
  state.busy = true;
  const { rerender } = render(<SupplierPaymentDialog {...props} />);
  expect(screen.getByLabelText('Сумма, ₽')).toBeDisabled();
  expect(screen.getByRole('button', { name: 'Запись…' })).toBeDisabled();
  state = { ...state, busy: false, success: { operationId: 31 } }; rerender(<SupplierPaymentDialog {...props} />);
  expect(screen.queryByRole('button', { name: 'Записать платёж' })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Новый платёж' })); expect(state.startNext).toHaveBeenCalledTimes(1);
});
test('history distinguishes reversal and does not claim first page complete', () => {
  state.history = { hasMore: true, items: [{ operationId: 31, kind: 'reversal', amount: '10.00',
    paidAt: '2026-09-18', reason: 'Ошибка суммы', reversesId: 30 }] };
  render(<SupplierPaymentDialog {...props} />);
  expect(screen.getByText(/Сторно платежа #30/)).toBeInTheDocument();
  expect(screen.getByText('Ошибка суммы')).toBeInTheDocument();
  expect(screen.getByText(/Показаны только последние/)).toBeInTheDocument();
});
test('focus is trapped and restored on close', () => {
  const opener = document.createElement('button'); document.body.appendChild(opener); opener.focus();
  const { unmount } = render(<SupplierPaymentDialog {...props} />);
  const close = screen.getByRole('button', { name: 'Закрыть' }); expect(close).toHaveFocus();
  fireEvent.keyDown(close, { key: 'Tab', shiftKey: true });
  expect(screen.getByRole('button', { name: 'Записать платёж' })).toHaveFocus();
  unmount(); expect(opener).toHaveFocus(); opener.remove();
});

test('eligible history offers reversal; form shows original amount/date and explicit confirmation', () => {
  const operation = { operationId: 51, companyId: 2, documentKind: 'warehouse', documentId: 7,
    kind: 'payment', amount: '10.01', paidAt: '2026-09-17', reversedById: null };
  state.history.items = [operation, { ...operation, operationId: 52, reversedById: 53 }];
  state.beginReversal = jest.fn(); state.updateReversal = jest.fn(); state.submitReversal = jest.fn(); state.cancelReversal = jest.fn();
  const { rerender } = render(<SupplierPaymentDialog {...props} />);
  expect(screen.getAllByRole('button', { name: /Сторнировать платёж/ })).toHaveLength(1);
  fireEvent.click(screen.getByRole('button', { name: 'Сторнировать платёж #51' }));
  expect(state.beginReversal).toHaveBeenCalledWith(51);
  state = { ...state, reversal: { operation, paidAt: '', reason: '', confirmed: false } }; rerender(<SupplierPaymentDialog {...props} />);
  expect(screen.getByText(/Исходный платёж #51.*10,01.*2026-09-17/)).toBeInTheDocument();
  expect(screen.queryByLabelText('Сумма, ₽')).not.toBeInTheDocument();
  expect(screen.getByLabelText('Дата сторно')).toHaveAttribute('type', 'date');
  expect(screen.getByLabelText('Причина сторно')).toBeRequired();
  fireEvent.click(screen.getByRole('checkbox', { name: 'Подтверждаю сторно выбранного платежа' }));
  expect(state.updateReversal).toHaveBeenCalledWith({ confirmed: true });
  fireEvent.submit(screen.getByRole('form', { name: 'Сторно платежа' })); expect(state.submitReversal).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByRole('button', { name: 'Отменить черновик сторно' })); expect(state.cancelReversal).toHaveBeenCalledTimes(1);
});

test('reversal success is not labelled as a new payment', () => {
  state.success = { kind: 'reversal', operationId: 61 };
  render(<SupplierPaymentDialog {...props} />);
  expect(screen.getByText('Сторно подтверждено. Операция #61.')).toBeInTheDocument();
  expect(screen.queryByText(/Платёж подтверждён/)).not.toBeInTheDocument();
});

test('cancellation warns explicitly; marked request exposes only cancellation retry', () => {
  state.pending = { body: { kind: 'payment', requestId: 'saved' } };
  state.confirmCancellation = jest.fn(); state.cancelPending = jest.fn();
  const { rerender } = render(<SupplierPaymentDialog {...props} />);
  expect(screen.getByText('Если операция уже проведена, получим подтверждение; сторно автоматически не выполняется')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Отменить попытку' })).toBeDisabled();
  fireEvent.click(screen.getByRole('checkbox', { name: 'Подтверждаю отмену сохранённой попытки' }));
  expect(state.confirmCancellation).toHaveBeenCalledWith(true);
  state = { ...state, pending: { ...state.pending, cancelRequested: true } }; rerender(<SupplierPaymentDialog {...props} />);
  expect(screen.queryByRole('button', { name: 'Повторить сохранённый запрос' })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Повторить отмену попытки' })); expect(state.cancelPending).toHaveBeenCalledTimes(1);
});

test('cancelled attempt is distinct from confirmed money operation', () => {
  state.success = { status: 'cancelled', cancelledAt: '2026-09-18T12:00:00Z' };
  render(<SupplierPaymentDialog {...props} />);
  expect(screen.getByText('Попытка отменена. Денежная операция не проведена.')).toBeInTheDocument();
  expect(screen.queryByText(/Платёж подтверждён|Сторно подтверждено/)).not.toBeInTheDocument();
});
