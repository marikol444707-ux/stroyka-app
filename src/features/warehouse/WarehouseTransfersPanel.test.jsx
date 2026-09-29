import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import WarehouseTransfersPanel from './WarehouseTransfersPanel';

const transfer = { id: 30, companyId: 2, sourceAllocationId: 8, fromProjectId: 11, fromProjectName: 'Школа', toProjectId: 13, toProjectName: 'Сад', warehouseInvoiceId: 10, invoiceNumber: 'НК-10', lotId: 5, materialName: 'Кабель', unit: 'м', quantity: '10', receivedQuantity: '0', inTransitQuantity: '10', status: 'in_transit', receipts: [], reason: 'По заявке', createdAt: '2026-09-16', createdBy: 'Иван' };
const source = { id: 8, projectId: 11, projectName: 'Школа', materialName: 'Кабель', unit: 'м', netQuantity: '15' };
const props = { companyId: 2, editable: true, source, projects: [{ id: 11, companyId: 2, name: 'Школа' }, { id: 13, companyId: 2, name: 'Сад' }, { id: 14, companyId: 3, name: 'Чужой' }, { id: 15, companyId: 2, name: 'Закрытый', status: 'Закрыт' }], onClose: jest.fn(), onChanged: jest.fn(), onDenied: jest.fn() };
const response = data => ({ ok: true, json: async () => data });
const page = (items = [transfer], nextCursor = null) => response({ items, truncated: nextCursor !== null, nextCursor });
const oldFetch = global.fetch;
const oldCrypto = global.crypto;
const oldFlag = process.env.REACT_APP_WAREHOUSE_DISTRIBUTION_TRANSFERS_ENABLED;
beforeAll(() => Object.defineProperty(global, 'crypto', { configurable: true, value: require('crypto').webcrypto }));
beforeEach(() => {
  sessionStorage.clear(); jest.clearAllMocks();
  process.env.REACT_APP_WAREHOUSE_DISTRIBUTION_TRANSFERS_ENABLED = 'true';
  global.fetch = jest.fn(async (url, options) => options?.method === 'POST'
    ? response({ ok: true, requestId: JSON.parse(options.body).requestId, item: transfer }) : page());
});
afterEach(() => { global.fetch = oldFetch; });
afterAll(() => {
  Object.defineProperty(global, 'crypto', { configurable: true, value: oldCrypto });
  if (oldFlag === undefined) delete process.env.REACT_APP_WAREHOUSE_DISTRIBUTION_TRANSFERS_ENABLED;
  else process.env.REACT_APP_WAREHOUSE_DISTRIBUTION_TRANSFERS_ENABLED = oldFlag;
});
async function fillDispatch() {
  await screen.findByText('В пути: 10 м');
  fireEvent.change(screen.getByLabelText('Объект назначения'), { target: { value: '13' } });
  fireEvent.change(screen.getByLabelText('Количество отправки'), { target: { value: '10' } });
  fireEvent.change(screen.getByLabelText('Основание отправки'), { target: { value: 'По заявке' } });
}
test('disabled flag makes no requests', () => {
  delete process.env.REACT_APP_WAREHOUSE_DISTRIBUTION_TRANSFERS_ENABLED;
  const { container } = render(<WarehouseTransfersPanel {...props} />);
  expect(container).toBeEmptyDOMElement(); expect(global.fetch).not.toHaveBeenCalled();
});
test('dispatch uses the loaded allocation, filters destinations and locks rapid submission', async () => {
  render(<WarehouseTransfersPanel {...props} />);
  await fillDispatch();
  expect(screen.queryByRole('option', { name: /Школа|Чужой|Закрытый/ })).not.toBeInTheDocument();
  const send = screen.getByText('Подтвердить отправку'); fireEvent.click(send); fireEvent.click(send);
  await screen.findByText(/Перемещение сохранено/);
  const writes = global.fetch.mock.calls.filter(([, options]) => options?.method === 'POST');
  expect(writes).toHaveLength(1);
  expect(JSON.parse(writes[0][1].body)).toMatchObject({ companyId: 2, allocationId: 8, toProjectId: 13, quantity: '10', reason: 'По заявке' });
  expect(props.onChanged).toHaveBeenCalled();
  expect(global.fetch.mock.calls.every(([url]) => url.includes('/warehouse-distributions/transfers'))).toBe(true);
});
test.each(['3', '0'])('partial/short receipt quantity=%s requires physical confirmation and retains discrepancy in transit', async quantity => {
  const received = { ...transfer, receivedQuantity: quantity, inTransitQuantity: String(10 - Number(quantity)), status: 'discrepancy', receipts: [{ id: 1, quantity, expectedQuantity: '5', discrepancyQuantity: String(5 - Number(quantity)), allocationId: quantity === '0' ? null : 9, reason: 'Недостача', createdAt: '2026-09-16', createdBy: 'Иван' }] };
  let saved = false;
  global.fetch = jest.fn(async (url, options) => {
    if (options?.method === 'POST') { saved = true; return response({ ok: true, requestId: JSON.parse(options.body).requestId, item: received }); }
    return page([saved ? received : transfer]);
  });
  render(<WarehouseTransfersPanel {...props} source={null} />);
  fireEvent.click(await screen.findByText('Принять на объекте'));
  fireEvent.change(screen.getByLabelText('Ожидалось в этой приёмке'), { target: { value: '5' } });
  fireEvent.change(screen.getByLabelText('Фактически принято'), { target: { value: quantity } });
  fireEvent.change(screen.getByLabelText('Основание приёмки / расхождения'), { target: { value: 'Недостача' } });
  expect(screen.getByText('Подтвердить приёмку')).toBeDisabled();
  fireEvent.click(screen.getByLabelText(/Подтверждаю фактическую приёмку/));
  fireEvent.click(screen.getByText('Подтвердить приёмку'));
  await screen.findByText(`В пути: ${10 - Number(quantity)} м`);
  expect(screen.getByText(/не считается потерей/)).toBeInTheDocument();
  const [url, options] = global.fetch.mock.calls.find(([, options]) => options?.method === 'POST');
  expect(url).toMatch(/\/30\/receipts$/);
  expect(JSON.parse(options.body)).toMatchObject({ quantity, expectedQuantity: '5', reason: 'Недостача' });
});
test('uncertain dispatch persists independently and retries identical payload after remount', async () => {
  const read = global.fetch;
  global.fetch = jest.fn((url, options) => options?.method === 'POST' ? Promise.reject(new Error('Нет ответа')) : read(url, options));
  const view = render(<WarehouseTransfersPanel {...props} />); await fillDispatch();
  fireEvent.click(screen.getByText('Подтвердить отправку')); await screen.findByRole('alert');
  const firstBody = global.fetch.mock.calls.find(([, options]) => options?.method === 'POST')[1].body;
  expect(screen.getByText('Подтвердить отправку')).toBeDisabled();
  view.unmount(); global.fetch = read;
  render(<WarehouseTransfersPanel {...props} />);
  fireEvent.click(await screen.findByText('Повторить перемещение безопасно'));
  await screen.findByText(/Перемещение сохранено/);
  expect(global.fetch.mock.calls.find(([, options]) => options?.method === 'POST')[1].body).toBe(firstBody);
});
test.each([400, 409, 422])('new definite rejection %s clears pending, allowing correction', async status => {
  const read = global.fetch;
  global.fetch = jest.fn((url, options) => options?.method === 'POST' ? Promise.resolve({ ok: false, status, json: async () => ({ detail: 'Не выполнено' }) }) : read(url, options));
  render(<WarehouseTransfersPanel {...props} />); await fillDispatch();
  fireEvent.click(screen.getByText('Подтвердить отправку')); await screen.findByRole('alert');
  expect(screen.queryByText('Повторить перемещение безопасно')).not.toBeInTheDocument();
  expect(screen.getByText('Подтвердить отправку')).toBeEnabled();
});
test('wrong request receipt keeps pending rather than claiming success', async () => {
  const read = global.fetch;
  global.fetch = jest.fn((url, options) => options?.method === 'POST' ? Promise.resolve(response({ ok: true, requestId: 'wrong', item: transfer })) : read(url, options));
  render(<WarehouseTransfersPanel {...props} />); await fillDispatch();
  fireEvent.click(screen.getByText('Подтвердить отправку')); await screen.findByRole('alert');
  expect(screen.getByText('Повторить перемещение безопасно')).toBeEnabled();
  expect(screen.queryByText(/Перемещение сохранено/)).not.toBeInTheDocument();
});
test('wrong transfer ID in a valid receipt response remains uncertain', async () => {
  const read = global.fetch;
  global.fetch = jest.fn((url, options) => options?.method === 'POST'
    ? Promise.resolve(response({ ok: true, requestId: JSON.parse(options.body).requestId, item: { ...transfer, id: 31 } })) : read(url, options));
  render(<WarehouseTransfersPanel {...props} source={null} />);
  fireEvent.click(await screen.findByText('Принять на объекте'));
  fireEvent.change(screen.getByLabelText('Ожидалось в этой приёмке'), { target: { value: '1' } });
  fireEvent.change(screen.getByLabelText('Фактически принято'), { target: { value: '1' } });
  fireEvent.change(screen.getByLabelText('Основание приёмки / расхождения'), { target: { value: 'Принято' } });
  fireEvent.click(screen.getByLabelText(/Подтверждаю фактическую приёмку/));
  fireEvent.click(screen.getByText('Подтвердить приёмку'));
  await screen.findByRole('alert');
  expect(screen.getByText('Повторить перемещение безопасно')).toBeEnabled();
  expect(screen.queryByText(/Перемещение сохранено/)).not.toBeInTheDocument();
});
test('receipt bounds reject over-acceptance, zero expectation and values over in-transit', async () => {
  render(<WarehouseTransfersPanel {...props} source={null} />);
  fireEvent.click(await screen.findByText('Принять на объекте'));
  fireEvent.change(screen.getByLabelText('Основание приёмки / расхождения'), { target: { value: 'Приёмка' } });
  fireEvent.click(screen.getByLabelText(/Подтверждаю фактическую приёмку/));
  for (const [expected, actual] of [['0', '0'], ['11', '1'], ['1', '2'], ['2', '-1'], ['2', '0.0000001']]) {
    fireEvent.change(screen.getByLabelText('Ожидалось в этой приёмке'), { target: { value: expected } });
    fireEvent.change(screen.getByLabelText('Фактически принято'), { target: { value: actual } });
    expect(screen.getByText('Подтвердить приёмку')).toBeDisabled();
  }
});
test('successful pagination appends and preserves applied search, not the draft', async () => {
  global.fetch = jest.fn(async url => {
    const query = new URL(url, 'http://localhost').searchParams;
    return query.has('beforeId') ? page([{ ...transfer, id: 29, toProjectName: 'Второй' }]) : page([transfer], 30);
  });
  render(<WarehouseTransfersPanel {...props} source={null} />);
  await screen.findByText('В пути: 10 м');
  fireEvent.change(screen.getByLabelText('Поиск перемещений'), { target: { value: 'Кабель' } });
  fireEvent.click(screen.getByText('Найти перемещения'));
  await waitFor(() => expect(screen.getByText('Загрузить ещё перемещения')).toBeEnabled());
  fireEvent.change(screen.getByLabelText('Поиск перемещений'), { target: { value: 'черновик' } });
  fireEvent.click(screen.getByText('Загрузить ещё перемещения'));
  await screen.findByText('Школа → Второй · Кабель');
  expect(screen.getAllByText('В пути: 10 м')).toHaveLength(2);
  const query = new URL(global.fetch.mock.calls[2][0], 'http://localhost').searchParams;
  expect(Object.fromEntries(query)).toEqual({ limit: '100', q: 'Кабель', beforeId: '30' });
});
test('pending retry rejected as conflict is retained because its original outcome is uncertain', async () => {
  const read = global.fetch;
  let attempt = 0;
  global.fetch = jest.fn((url, options) => {
    if (options?.method !== 'POST') return read(url, options);
    attempt += 1;
    return attempt === 1 ? Promise.reject(new Error('Нет ответа')) : Promise.resolve({ ok: false, status: 409, json: async () => ({ detail: 'Сверьте историю' }) });
  });
  render(<WarehouseTransfersPanel {...props} />); await fillDispatch();
  fireEvent.click(screen.getByText('Подтвердить отправку')); await screen.findByRole('alert');
  fireEvent.click(screen.getByText('Повторить перемещение безопасно')); await screen.findByText('Сверьте историю');
  expect(screen.getByText('Повторить перемещение безопасно')).toBeEnabled();
  expect(screen.getByText('Подтвердить отправку')).toBeDisabled();
});
test('storage corruption introduced after mount fails closed before sending', async () => {
  render(<WarehouseTransfersPanel {...props} />); await fillDispatch();
  sessionStorage.setItem('warehouse-transfers.pending.v1.2', '{broken');
  fireEvent.click(screen.getByText('Подтвердить отправку'));
  await screen.findByRole('alert');
  expect(screen.getByText('Подтвердить отправку')).toBeDisabled();
  expect(global.fetch.mock.calls.some(([, options]) => options?.method === 'POST')).toBe(false);
});
test('no authorization survives a role change with a late response', async () => {
  let late;
  global.fetch = jest.fn(() => new Promise(resolve => { late = resolve; }));
  const view = render(<WarehouseTransfersPanel {...props} />);
  global.fetch = jest.fn(async () => page([]));
  view.rerender(<WarehouseTransfersPanel {...props} editable={false} />);
  await screen.findByText('Перемещений пока нет.');
  await act(async () => late(page()));
  expect(screen.queryByText('В пути: 10 м')).not.toBeInTheDocument();
  expect(screen.queryByText('Подтвердить отправку')).not.toBeInTheDocument();
});
test('read-only lists transfers without commands', async () => {
  render(<WarehouseTransfersPanel {...props} editable={false} />);
  await screen.findByText('В пути: 10 м');
  expect(screen.queryByText('Принять на объекте')).not.toBeInTheDocument();
  expect(screen.queryByText('Подтвердить отправку')).not.toBeInTheDocument();
});
test('server search and pagination ignore stale filter responses', async () => {
  global.fetch = jest.fn(async () => page([transfer], 30));
  render(<WarehouseTransfersPanel {...props} source={null} />);
  fireEvent.click(await screen.findByText('Загрузить ещё перемещения'));
  // An overlapping/non-descending page must fail closed.
  await screen.findByRole('alert'); expect(screen.queryByText('В пути: 10 м')).not.toBeInTheDocument();
  let old;
  global.fetch = jest.fn().mockImplementationOnce(() => new Promise(resolve => { old = resolve; })).mockResolvedValueOnce(page([]));
  fireEvent.change(screen.getByLabelText('Поиск перемещений'), { target: { value: 'старый' } }); fireEvent.click(screen.getByText('Найти перемещения'));
  fireEvent.change(screen.getByLabelText('Поиск перемещений'), { target: { value: 'новый' } }); fireEvent.click(screen.getByText('Найти перемещения'));
  await screen.findByText('По поиску перемещений не найдено.');
  await act(async () => old(page()));
  expect(screen.queryByText('В пути: 10 м')).not.toBeInTheDocument();
});
test('company switch and denial discard old data and commands', async () => {
  const view = render(<WarehouseTransfersPanel {...props} />); await fillDispatch();
  let late;
  global.fetch = jest.fn(() => new Promise(resolve => { late = resolve; }));
  fireEvent.click(screen.getByText('Обновить перемещения'));
  global.fetch = jest.fn(async () => ({ ok: false, status: 403, json: async () => ({ detail: 'Нет доступа' }) }));
  view.rerender(<WarehouseTransfersPanel {...props} companyId={3} source={null} />);
  await screen.findByText('Нет доступа');
  await act(async () => late(page()));
  expect(screen.queryByText('В пути: 10 м')).not.toBeInTheDocument();
  expect(props.onDenied).toHaveBeenCalled();
});
