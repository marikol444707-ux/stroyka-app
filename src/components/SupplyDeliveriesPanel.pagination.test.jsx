import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import SupplyDeliveriesPanel from './SupplyDeliveriesPanel';

const deliveries = count => Array.from({ length: count }, (_, index) => ({
  id: count - index, materialName: 'Материал-' + (count - index),
  shippedQuantity: 10, unit: 'шт', status: index < 8 ? 'Принято' : 'Отгружено',
}));
const props = rows => ({
  C: {}, badge: () => ({}), role: 'прораб', supplyDeliveries: rows,
  supplyClaims: [], invoices: [], deliveryAiResultById: {},
  setReceivingDeliveryId: jest.fn(), setReceiveForm: jest.fn(),
});

describe('delivery list pagination', () => {
  it('makes an older pending delivery reachable by keyboard after eight accepted deliveries', () => {
    const deps = props(deliveries(9));
    render(<SupplyDeliveriesPanel {...deps} />);

    expect(screen.queryByText('Материал-1')).not.toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent('Показано поставок: 8 из 9');
    const more = screen.getByRole('button', { name: /Показать ещё/ });
    userEvent.tab();
    expect(more).toHaveFocus();
    userEvent.keyboard('{Enter}');

    expect(screen.getByText('Материал-1')).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent('Показано поставок: 9 из 9');
    fireEvent.click(screen.getByRole('button', { name: 'Принять' }));
    expect(deps.setReceivingDeliveryId).toHaveBeenCalledWith(1);
    expect(deps.setReceiveForm).toHaveBeenCalledWith(expect.objectContaining({ receivedQuantity: '10' }));
    expect(screen.queryByRole('button', { name: /Показать ещё/ })).not.toBeInTheDocument();
  });

  it('reaches every delivery over multiple increments and retains the expanded list on rerender', () => {
    const deps = props(deliveries(17));
    const { rerender } = render(<SupplyDeliveriesPanel {...deps} />);

    fireEvent.click(screen.getByRole('button', { name: /Показать ещё/ }));
    expect(screen.getByRole('status')).toHaveTextContent('Показано поставок: 16 из 17');
    expect(screen.getByText('Материал-17')).toBeInTheDocument();
    expect(screen.getByText('Материал-2')).toBeInTheDocument();
    expect(screen.queryByText('Материал-1')).not.toBeInTheDocument();
    rerender(<SupplyDeliveriesPanel {...deps} supplyDeliveries={[...deps.supplyDeliveries]} />);
    expect(screen.getByText('Материал-2')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Показать ещё/ }));
    expect(screen.getAllByText(/^Материал-/)).toHaveLength(17);
    expect(screen.getByRole('status')).toHaveTextContent('Показано поставок: 17 из 17');
    expect(screen.queryByRole('button', { name: /Показать ещё/ })).not.toBeInTheDocument();
  });

  it('has no unnecessary show-more control for a short or empty list', () => {
    const { rerender } = render(<SupplyDeliveriesPanel {...props(deliveries(8))} />);
    expect(screen.getAllByText(/^Материал-/)).toHaveLength(8);
    expect(screen.queryByRole('button', { name: /Показать ещё/ })).not.toBeInTheDocument();

    rerender(<SupplyDeliveriesPanel {...props([])} />);
    expect(screen.getByText(/Поставок пока нет/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Показать ещё/ })).not.toBeInTheDocument();
  });
});
