import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import SupplierCabinetPage from './SupplierCabinetPage';

const requestItems = [
  { materialName: 'Труба', quantity: 10, unit: 'шт', workPackage: 'Основная' },
  { materialName: 'Крепёж', quantity: 20, unit: 'шт', workPackage: 'Основная' },
];

function Cabinet({ deps, multi = false }) {
  const items = multi ? requestItems : requestItems.slice(0, 1);
  const [respondingOfferId, setRespondingOfferId] = React.useState(42);
  const [newKpResponse, setNewKpResponse] = React.useState({
    pricePerUnit: '100', deliveryDays: '2', paymentTerms: 'Постоплата',
    vatIncluded: true, validUntil: '', supplierMessage: 'Доставим утром', pdfUrl: '',
    itemsKp: items.map(item => ({ ...item, pricePerUnit: '100' })),
  });
  return <SupplierCabinetPage
    {...deps} API="/api" C={{}} badge={() => ({})}
    user={{ id: 7, role: 'поставщик', name: 'Поставщик' }}
    supplierTab="requests" suppliers={[]} supplierRequisites={{}}
    supplierOffers={[{ id: 42, requestId: 31, status: 'Ожидает ответа' }]}
    supplyRequests={[{ id: 31, project: 'Лицей', quantity: 10, unit: 'шт', items }]}
    parseSupplyItems={request => request.items}
    respondingOfferId={respondingOfferId} setRespondingOfferId={setRespondingOfferId}
    newKpResponse={newKpResponse} setNewKpResponse={setNewKpResponse}
  />;
}

describe('supplier offer submission', () => {
  const originalFetch = global.fetch;
  beforeEach(() => {
    global.fetch = jest.fn();
    jest.spyOn(window, 'alert').mockImplementation(() => {});
  });
  afterEach(() => {
    global.fetch = originalFetch;
    jest.restoreAllMocks();
  });

  it.each([false, true])('preserves the filled form after HTTP failure (multi=%s)', async multi => {
    global.fetch.mockResolvedValue({ ok: false, status: 403, json: async () => ({ detail: 'Нет доступа к КП' }) });
    const deps = { notify: jest.fn(), refreshData: jest.fn() };
    render(<Cabinet deps={deps} multi={multi} />);

    fireEvent.click(screen.getByRole('button', { name: 'Отправить КП' }));

    await waitFor(() => expect(window.alert).toHaveBeenCalledWith(expect.stringContaining('Нет доступа к КП')));
    expect(screen.getByDisplayValue('Доставим утром')).toBeInTheDocument();
    expect(screen.getAllByDisplayValue('100')).toHaveLength(multi ? 2 : 1);
    expect(screen.getByRole('button', { name: 'Отмена' })).toBeInTheDocument();
    expect(deps.notify).not.toHaveBeenCalled();
    expect(deps.refreshData).not.toHaveBeenCalled();
  });

  it('preserves the form when an HTTP failure has a non-JSON body', async () => {
    global.fetch.mockResolvedValue({ ok: false, status: 502, json: async () => { throw new SyntaxError('HTML'); } });
    const deps = { notify: jest.fn(), refreshData: jest.fn() };
    render(<Cabinet deps={deps} />);

    fireEvent.click(screen.getByRole('button', { name: 'Отправить КП' }));

    await waitFor(() => expect(window.alert).toHaveBeenCalledWith(expect.stringContaining('502')));
    expect(screen.getByDisplayValue('Доставим утром')).toBeInTheDocument();
    expect(deps.notify).not.toHaveBeenCalled();
  });

  it.each([false, true])('closes the form only after successful submission (multi=%s)', async multi => {
    global.fetch.mockResolvedValue({ ok: true, status: 200, json: async () => ({ id: 42, status: 'Получено' }) });
    const deps = { notify: jest.fn(), refreshData: jest.fn() };
    render(<Cabinet deps={deps} multi={multi} />);

    fireEvent.click(screen.getByRole('button', { name: 'Отправить КП' }));

    await waitFor(() => expect(deps.notify).toHaveBeenCalledWith('КП отправлено директору', 'supply'));
    expect(screen.queryByRole('button', { name: 'Отмена' })).not.toBeInTheDocument();
    expect(deps.refreshData).toHaveBeenCalledTimes(1);
    const body = JSON.parse(global.fetch.mock.calls[0][1].body);
    expect(body.action).toBe('respond');
    const expected = multi
      ? { itemsKp: requestItems.map(item => ({ ...item, pricePerUnit: 100 })) }
      : { quantity: 10, pricePerUnit: 100, totalPrice: 1000 };
    expect(body).toMatchObject(expected);
  });
});
