// Return persistence is verified separately in WarehouseReturnPersistence.test.jsx.
jest.mock('./useWarehouseReturnDraft', () => () => ({ loading: false, saving: false, dirty: false, error: '', phase: 'ready', readyToSubmit: true, flush: async () => undefined, rejectConflict: () => {} }));
// These source/command regressions isolate draft transport; actual persistence is covered in WarehouseBatchPersistence.test.jsx.
jest.mock('./useWarehouseBatchDraft', () => () => ({ loading: false, saving: false, dirty: false, error: '', phase: 'ready', readyToSubmit: true, flush: async () => undefined, clear: () => {}, rejectConflict: () => {} }));
import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { DistributionWorkspace } from './WarehouseDistributionPanel';

const allocation = { id: 8, lotId: 5, warehouseInvoiceId: 10, projectId: 11, projectName: 'Школа', materialName: 'Кабель', unit: 'м', quantity: '20', returnedQuantity: '5', netQuantity: '15', returns: [] };
const transfer = { id: 30, companyId: 2, sourceAllocationId: 8, fromProjectId: 11, fromProjectName: 'Школа', toProjectId: 13, toProjectName: 'Сад', warehouseInvoiceId: 10, lotId: 5, materialName: 'Кабель', unit: 'м', quantity: '10', receivedQuantity: '0', inTransitQuantity: '10', status: 'in_transit', receipts: [], reason: 'По заявке' };
const props = {
  companyContext: { mode: 'company', selectedCompanyId: 2, companies: [{ companyId: 2, role: 'директор' }, { companyId: 3, role: 'директор' }] },
  projects: [{ id: 11, companyId: 2, name: 'Школа' }, { id: 13, companyId: 2, name: 'Сад' }],
};
const ok = data => ({ ok: true, json: async () => data });
const page = items => ok({ items, truncated: false, nextCursor: null });
const originalFetch = global.fetch;
const originalCrypto = global.crypto;
const originalFlag = process.env.REACT_APP_WAREHOUSE_DISTRIBUTION_TRANSFERS_ENABLED;
beforeAll(() => Object.defineProperty(global, 'crypto', { configurable: true, value: require('crypto').webcrypto }));
beforeEach(() => {
  sessionStorage.clear();
  process.env.REACT_APP_WAREHOUSE_DISTRIBUTION_TRANSFERS_ENABLED = 'true';
  global.fetch = jest.fn(async url => url.includes('/transfers') ? page([transfer])
    : url.includes('/sources') ? page([]) : page([allocation, { ...allocation, id: 7, materialName: 'Краска' }]));
});
afterEach(() => { global.fetch = originalFetch; });
afterAll(() => {
  Object.defineProperty(global, 'crypto', { configurable: true, value: originalCrypto });
  if (originalFlag === undefined) delete process.env.REACT_APP_WAREHOUSE_DISTRIBUTION_TRANSFERS_ENABLED;
  else process.env.REACT_APP_WAREHOUSE_DISTRIBUTION_TRANSFERS_ENABLED = originalFlag;
});
async function fillDispatch() {
  const buttons = await screen.findAllByText('Отправить на другой объект');
  await waitFor(() => expect(buttons[0]).toBeEnabled());
  fireEvent.click(buttons[0]);
  fireEvent.change(screen.getByLabelText('Объект назначения'), { target: { value: '13' } });
  fireEvent.change(screen.getByLabelText('Количество отправки'), { target: { value: '10' } });
  fireEvent.change(screen.getByLabelText('Основание отправки'), { target: { value: 'По заявке' } });
  await waitFor(() => expect(screen.getByText('Подтвердить отправку')).toBeEnabled());
}
function expectDraft() {
  expect(screen.getByLabelText('Объект назначения')).toHaveValue('13');
  expect(screen.getByLabelText('Количество отправки')).toHaveValue('10');
  expect(screen.getByLabelText('Основание отправки')).toHaveValue('По заявке');
}
const refresh = () => fireEvent.click(screen.getByRole('button', { name: 'Обновить', exact: true }));

test('dispatch survives parent refresh and validates against the fresh allocation balance', async () => {
  render(<DistributionWorkspace {...props} />);
  await fillDispatch();
  const read = global.fetch;
  let finish;
  global.fetch = jest.fn((url, options) => url.includes('/sources') || url.includes('/transfers')
    ? read(url, options) : new Promise(resolve => { finish = resolve; }));
  refresh();
  expectDraft();
  expect(screen.getByText('Подтвердить отправку')).toBeDisabled();
  await act(async () => finish(page([{ ...allocation, netQuantity: '2', transferredQuantity: '13' }])));
  expectDraft();
  expect(screen.getByText(/Распределение #8. Максимум: 2 м/)).toBeInTheDocument();
  expect(screen.getByText('Подтвердить отправку')).toBeDisabled();
});
test('empty allocation search preserves dispatch but prevents a new POST until reloaded', async () => {
  render(<DistributionWorkspace {...props} />);
  await fillDispatch();
  const read = global.fetch;
  global.fetch = jest.fn((url, options) => url.includes('q=') ? Promise.resolve(page([])) : read(url, options));
  fireEvent.change(screen.getByLabelText('Найти по объекту, материалу или накладной'), { target: { value: 'Нет совпадений' } });
  fireEvent.click(screen.getByText('Применить фильтры'));
  await screen.findByText('По заданным фильтрам распределений не найдено.');
  expectDraft();
  expect(screen.getByText('Подтвердить отправку')).toBeDisabled();
  fireEvent.change(screen.getByLabelText('Найти по объекту, материалу или накладной'), { target: { value: '' } });
  fireEvent.click(screen.getByText('Применить фильтры'));
  await waitFor(() => expect(screen.getByText('Подтвердить отправку')).toBeEnabled());
  expectDraft();
  expect(global.fetch.mock.calls.some(([, options]) => options?.method === 'POST')).toBe(false);
});
test('failed allocation refresh keeps editable dispatch and allows explicit cancellation', async () => {
  render(<DistributionWorkspace {...props} />);
  await fillDispatch();
  const read = global.fetch;
  global.fetch = jest.fn((url, options) => url.includes('/sources') || url.includes('/transfers') ? read(url, options)
    : Promise.resolve({ ok: false, status: 503, json: async () => ({ detail: 'Не удалось загрузить остаток' }) }));
  refresh();
  await screen.findByText('Не удалось загрузить остаток');
  expectDraft();
  expect(screen.getByText('Подтвердить отправку')).toBeDisabled();
  expect(screen.getByLabelText('Количество отправки')).toBeEnabled();
  fireEvent.click(screen.getByText('Отменить отправку'));
  expect(screen.queryByLabelText('Количество отправки')).not.toBeInTheDocument();
});
test('another allocation cannot silently replace a dispatch draft', async () => {
  render(<DistributionWorkspace {...props} />);
  await fillDispatch();
  const buttons = screen.getAllByText('Отправить на другой объект');
  fireEvent.click(buttons[1]);
  expectDraft();
  expect(screen.getByText('Отправка: Школа · Кабель')).toBeInTheDocument();
  expect(buttons[1]).toBeDisabled();
  fireEvent.click(screen.getByText('Отменить отправку'));
  fireEvent.click(screen.getAllByText('Отправить на другой объект')[1]);
  expect(screen.getByText('Отправка: Школа · Краска')).toBeInTheDocument();
  expect(screen.getByLabelText('Количество отправки')).toHaveValue('');
});
test('receiving an existing transfer cannot erase an unfinished dispatch', async () => {
  render(<DistributionWorkspace {...props} />);
  await fillDispatch();
  fireEvent.click(screen.getByText('Принять на объекте'));
  expectDraft();
  expect(screen.queryByLabelText('Фактически принято')).not.toBeInTheDocument();
  expect(screen.getByText('Принять на объекте')).toBeDisabled();
  fireEvent.click(screen.getByText('Отменить отправку'));
  fireEvent.click(screen.getByText('Принять на объекте'));
  expect(screen.getByLabelText('Фактически принято')).toBeInTheDocument();
});
test('refreshed draft submits once with the original allocation and destination', async () => {
  render(<DistributionWorkspace {...props} />);
  await fillDispatch();
  refresh();
  await waitFor(() => expect(screen.getByText('Подтвердить отправку')).toBeEnabled());
  const read = global.fetch;
  global.fetch = jest.fn((url, options) => options?.method === 'POST'
    ? Promise.resolve(ok({ ok: true, requestId: JSON.parse(options.body).requestId, item: transfer })) : read(url, options));
  fireEvent.click(screen.getByText('Подтвердить отправку'));
  await screen.findByText(/Перемещение сохранено/);
  await waitFor(() => expect(screen.getByRole('button', { name: 'Обновить', exact: true })).toBeEnabled());
  expect(screen.queryByLabelText('Количество отправки')).not.toBeInTheDocument();
  const writes = global.fetch.mock.calls.filter(([, options]) => options?.method === 'POST');
  expect(writes).toHaveLength(1);
  expect(writes[0][0]).toMatch(/\/warehouse-distributions\/transfers$/);
  expect(JSON.parse(writes[0][1].body)).toMatchObject({ companyId: 2, allocationId: 8, toProjectId: 13, quantity: '10', reason: 'По заявке' });
});
test('a rejected dispatch keeps its draft and is not retried automatically', async () => {
  render(<DistributionWorkspace {...props} />);
  await fillDispatch();
  global.fetch = jest.fn(async () => ({ ok: false, status: 409, json: async () => ({ detail: 'Остаток изменился' }) }));
  fireEvent.click(screen.getByText('Подтвердить отправку'));
  await screen.findByText('Остаток изменился');
  expectDraft();
  expect(screen.queryByText(/Перемещение сохранено/)).not.toBeInTheDocument();
  expect(global.fetch).toHaveBeenCalledTimes(1);
  expect(screen.getByText('Подтвердить отправку')).toBeEnabled();
});
test('lost response can be retried with the exact command even when refreshed allocation is absent', async () => {
  render(<DistributionWorkspace {...props} />);
  await fillDispatch();
  const read = global.fetch;
  global.fetch = jest.fn((url, options) => options?.method === 'POST' ? Promise.reject(new Error('Ответ потерян')) : read(url, options));
  fireEvent.click(screen.getByText('Подтвердить отправку'));
  await screen.findByText('Ответ потерян');
  const originalBody = global.fetch.mock.calls.find(([, options]) => options?.method === 'POST')[1].body;
  global.fetch = jest.fn(async url => url.includes('/transfers') ? page([transfer]) : page([]));
  refresh();
  await screen.findByText('Распределений в выбранной компании пока нет.');
  expectDraft();
  expect(screen.getByText('Подтвердить отправку')).toBeDisabled();
  global.fetch = jest.fn((url, options) => options?.method === 'POST'
    ? Promise.resolve(ok({ ok: true, requestId: JSON.parse(options.body).requestId, item: transfer })) : read(url, options));
  fireEvent.click(screen.getByText('Повторить перемещение безопасно'));
  await screen.findByText(/Перемещение сохранено/);
  await waitFor(() => expect(screen.getByRole('button', { name: 'Обновить', exact: true })).toBeEnabled());
  const writes = global.fetch.mock.calls.filter(([, options]) => options?.method === 'POST');
  expect(writes).toHaveLength(1);
  expect(writes[0][1].body).toBe(originalBody);
});
test.each([401, 403])('allocation read denial %s removes the old draft and disables writes', async status => {
  render(<DistributionWorkspace {...props} />);
  await fillDispatch();
  global.fetch = jest.fn(async () => ({ ok: false, status, json: async () => ({ detail: 'Нет доступа к компании' }) }));
  refresh();
  await screen.findByText('Нет доступа к компании');
  expect(screen.queryByLabelText('Количество отправки')).not.toBeInTheDocument();
  expect(screen.queryByText('Отправка: Школа · Кабель')).not.toBeInTheDocument();
  expect(global.fetch.mock.calls.some(([, options]) => options?.method === 'POST')).toBe(false);
});
test.each(['company', 'role'])('late history cannot restore a dispatch draft after changing %s', async change => {
  const view = render(<DistributionWorkspace {...props} />);
  await fillDispatch();
  const read = global.fetch;
  let finish;
  global.fetch = jest.fn((url, options) => url.includes('/sources') || url.includes('/transfers') ? read(url, options)
    : new Promise(resolve => { finish = resolve; }));
  refresh();
  global.fetch = jest.fn(async () => page([]));
  view.rerender(<DistributionWorkspace {...props} readOnly={change === 'role'} companyContext={{ ...props.companyContext, selectedCompanyId: change === 'company' ? 3 : 2 }} />);
  await screen.findByText('Распределений в выбранной компании пока нет.');
  await act(async () => finish(page([allocation])));
  expect(screen.queryByLabelText('Количество отправки')).not.toBeInTheDocument();
  expect(screen.queryByText('Школа · Кабель')).not.toBeInTheDocument();
});
test('late previous history cannot authorize a dispatch excluded by the current filter', async () => {
  render(<DistributionWorkspace {...props} />);
  await fillDispatch();
  let finish;
  const read = global.fetch;
  global.fetch = jest.fn((url, options) => url.includes('/sources') || url.includes('/transfers') ? read(url, options)
    : new Promise(resolve => { finish = resolve; }));
  refresh();
  global.fetch = jest.fn(async () => page([]));
  fireEvent.change(screen.getByLabelText('Найти по объекту, материалу или накладной'), { target: { value: 'Нет совпадений' } });
  fireEvent.click(screen.getByText('Применить фильтры'));
  await screen.findByText('По заданным фильтрам распределений не найдено.');
  await act(async () => finish(page([allocation])));
  expectDraft();
  expect(screen.getByText('Подтвердить отправку')).toBeDisabled();
});
