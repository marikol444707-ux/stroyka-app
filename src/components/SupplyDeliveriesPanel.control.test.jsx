import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import SupplyDeliveriesPanel from './SupplyDeliveriesPanel';

const delivery = (id, changes = {}) => ({ id, materialName: `Материал ${id}`, unit: 'шт',
  shippedQuantity: 2, plannedQuantity: 2, status: 'В пути', ...changes });
const props = changes => ({ C: {}, badge: () => ({}), role: 'прораб',
  supplyDeliveries: [], supplyClaims: [], invoices: [], deliveryAiResultById: {},
  setReceivingDeliveryId: jest.fn(), setReceiveForm: jest.fn(), ...changes });

test('problem and timestamped receipts cannot be accepted again and stale receipt form is hidden', () => {
  render(<SupplyDeliveriesPanel {...props({ receivingDeliveryId: 1,
    supplyDeliveries: [delivery(1, { status: 'Проблема', receivedQuantity: 0, shortageQuantity: 2 }),
      delivery(2, { receivedAt: '2026-09-19T10:00:00', receivedQuantity: 1 })],
    receiveForm: { receivedQuantity: '2', qualityStatus: 'Принято' },
  })} />);
  expect(screen.queryByRole('button', { name: 'Принять' })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Сохранить приёмку' })).not.toBeInTheDocument();
  expect(screen.getByText('Принято: 0 шт · Недостача: 2 шт')).toBeInTheDocument();
});

test('working claims remain unresolved and resolved claims do not remove historical delivery problems', () => {
  render(<SupplyDeliveriesPanel {...props({ supplyDeliveries: [
    delivery(1, { status: 'Проблема' }), delivery(2, { status: 'Проблема' }), delivery(3),
  ], supplyClaims: [ { id: 1, deliveryId: 1, status: 'В работе' }, { id: 2, deliveryId: 2, status: 'Решена' } ] })} />);
  expect(screen.getByText('⚠️ Претензий: 1')).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('Показать поставки'), { target: { value: 'claims' } });
  expect(screen.getByText('Материал 1')).toBeInTheDocument();
  expect(screen.queryByText('Материал 2')).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('Показать поставки'), { target: { value: 'problem' } });
  expect(screen.getByText('Материал 2')).toBeInTheDocument();
  expect(screen.queryByText('Материал 3')).not.toBeInTheDocument();
});

test('pending filter reaches an older delivery immediately and paginates within the selected filter', () => {
  const rows = Array.from({ length: 9 }, (_, i) => delivery(i + 1, { status: 'Принято' }));
  rows.push(delivery(10));
  render(<SupplyDeliveriesPanel {...props({ supplyDeliveries: rows })} />);
  expect(screen.queryByText('Материал 10')).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('Показать поставки'), { target: { value: 'pending' } });
  expect(screen.getByText('Материал 10')).toBeInTheDocument();
  expect(screen.getByRole('status')).toHaveTextContent('Показано поставок: 1 из 1');
  expect(screen.queryByRole('button', { name: /Показать ещё/ })).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('Показать поставки'), { target: { value: 'claims' } });
  expect(screen.getByText('По этому фильтру поставок нет.')).toBeInTheDocument();
});

test('receipt form remains available for a pending delivery to an authorized role', () => {
  const p = props({ supplyDeliveries: [delivery(1)] });
  const view = render(<SupplyDeliveriesPanel {...p} />);
  fireEvent.click(screen.getByRole('button', { name: 'Принять' }));
  expect(p.setReceivingDeliveryId).toHaveBeenCalledWith(1);
  expect(p.setReceiveForm).toHaveBeenCalledWith(expect.objectContaining({ receivedQuantity: '2' }));
  view.rerender(<SupplyDeliveriesPanel {...p} role="бухгалтер" receivingDeliveryId={1} />);
  expect(screen.queryByRole('button', { name: 'Принять' })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Сохранить приёмку' })).not.toBeInTheDocument();
});
