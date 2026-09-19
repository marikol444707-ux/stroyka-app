import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import SupplierCabinetPage from './SupplierCabinetPage';

const requestItems = [
  { materialName: 'Труба', quantity: 10, unit: 'шт', workPackage: 'Основная' },
  { materialName: 'Крепёж', quantity: 20, unit: 'шт', workPackage: 'Основная' },
];

function Cabinet({ deps, multi = false, respondedAt = null }) {
  const items = multi ? requestItems : requestItems.slice(0, 1);
  const [respondingOfferId, setRespondingOfferId] = React.useState(42);
  const [newKpResponse, setNewKpResponse] = React.useState({
    expectedRespondedAt: null, pricePerUnit: '100', deliveryDays: '2', paymentTerms: 'Постоплата',
    vatIncluded: true, validUntil: '', supplierMessage: 'Доставим утром', pdfUrl: '',
    itemsKp: items.map(item => ({ ...item, pricePerUnit: '100' })),
  });
  return <SupplierCabinetPage
    {...deps} API="/api" C={{}} badge={() => ({})}
    user={{ id: 7, role: 'поставщик', name: 'Поставщик' }}
    supplierTab="requests" suppliers={[]} supplierRequisites={{}}
    supplierOffers={[{ id: 42, requestId: 31, status: 'Ожидает ответа', respondedAt }]}
    supplyRequests={[{ id: 31, project: 'Лицей', quantity: 10, unit: 'шт', items }]}
    parseSupplyItems={request => request.items}
    respondingOfferId={respondingOfferId} setRespondingOfferId={setRespondingOfferId}
    newKpResponse={newKpResponse} setNewKpResponse={setNewKpResponse}
  />;
}

describe('supplier offer submission', () => {
  const originalFetch = global.fetch;
  beforeEach(() => {
    window.history.replaceState({}, '', '/app?supplyRequestId=31');
    global.fetch = jest.fn();
    Object.defineProperty(window, 'crypto', { configurable: true, value: { randomUUID: () => '12345678-1234-4234-8234-123456789012' } });
    jest.spyOn(window, 'alert').mockImplementation(() => {});
  });
  afterEach(() => {
    window.history.replaceState({}, '', '/app');
    global.fetch = originalFetch;
    jest.restoreAllMocks();
  });

  it('hides the draft when returning to the list and restores it on reopening', () => {
    render(<Cabinet deps={{notify:jest.fn(),refreshData:jest.fn()}} />);
    expect(screen.getByDisplayValue('Доставим утром')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', {name:'← К списку заявок'}));
    expect(window.location.search).toBe('');
    expect(screen.queryByDisplayValue('Доставим утром')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', {name:'Отправить КП',exact:true})).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', {name:'Открыть заявку №31'}));
    expect(screen.getByDisplayValue('Доставим утром')).toBeInTheDocument();
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

  it('keeps the original draft version when a refreshed offer has changed', async () => {
    global.fetch.mockResolvedValue({ ok: false, status: 409, json: async () => ({ detail: 'КП уже изменено' }) });
    const deps = { notify: jest.fn(), refreshData: jest.fn() };
    const { rerender } = render(<Cabinet deps={deps} />);
    rerender(<Cabinet deps={deps} respondedAt="2026-09-19T12:00:00" />);
    fireEvent.click(screen.getByRole('button', { name: 'Отправить КП' }));
    await screen.findByRole('alert');
    expect(JSON.parse(global.fetch.mock.calls[0][1].body).expectedRespondedAt).toBeNull();
    expect(screen.getByDisplayValue('Доставим утром')).toBeInTheDocument();
  });

  it('keeps the draft after a network failure and allows a safe retry', async () => {
    global.fetch.mockRejectedValueOnce(new TypeError('Failed to fetch'));
    const deps = { notify: jest.fn(), refreshData: jest.fn() };
    render(<Cabinet deps={deps} />);
    fireEvent.click(screen.getByRole('button', { name: 'Отправить КП' }));
    await screen.findByRole('alert');
    expect(screen.getByDisplayValue('Доставим утром')).toBeInTheDocument();
    expect(deps.notify).not.toHaveBeenCalled();
    global.fetch.mockResolvedValueOnce({ ok: true, json: async () => ({ id: 42, status: 'Получено' }) });
    fireEvent.click(screen.getByRole('button', { name: 'Отправить КП' }));
    await waitFor(() => expect(deps.notify).toHaveBeenCalledTimes(1));
    const first = JSON.parse(global.fetch.mock.calls[0][1].body);
    const retry = JSON.parse(global.fetch.mock.calls[1][1].body);
    expect(first.requestId).toMatch(/^[0-9a-f-]{36}$/i);
    expect(retry.requestId).toBe(first.requestId);
  });

  it('does not accept a successful HTTP response without the saved offer', async () => {
    global.fetch.mockResolvedValue({ ok: true, json: async () => ({}) });
    const deps = { notify: jest.fn(), refreshData: jest.fn() };
    render(<Cabinet deps={deps} />);
    fireEvent.click(screen.getByRole('button', { name: 'Отправить КП' }));
    await screen.findByRole('alert');
    expect(screen.getByDisplayValue('Доставим утром')).toBeInTheDocument();
    expect(deps.notify).not.toHaveBeenCalled();
  });

  it('locks sending and editing until the pending submission is confirmed', async () => {
    let resolve;
    global.fetch.mockReturnValue(new Promise(done => { resolve = done; }));
    const deps = { notify: jest.fn(), refreshData: jest.fn() };
    render(<Cabinet deps={deps} />);
    const send = screen.getByRole('button', { name: 'Отправить КП' });
    fireEvent.click(send);
    fireEvent.click(send);
    expect(global.fetch).toHaveBeenCalledTimes(1);
    expect(screen.getByDisplayValue('Доставим утром')).toBeDisabled();
    resolve({ ok: true, json: async () => ({ id: 42, status: 'Получено' }) });
    await waitFor(() => expect(deps.notify).toHaveBeenCalledTimes(1));
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
