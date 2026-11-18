// Return persistence is verified separately in WarehouseReturnPersistence.test.jsx.
jest.mock('./useWarehouseReturnDraft', () => () => ({ loading: false, saving: false, dirty: false, error: '', phase: 'ready', readyToSubmit: true, flush: async () => undefined, rejectConflict: () => {} }));
// These source/command regressions isolate draft transport; actual persistence is covered in WarehouseBatchPersistence.test.jsx.
jest.mock('./useWarehouseBatchDraft', () => () => ({ loading: false, saving: false, dirty: false, error: '', phase: 'ready', readyToSubmit: true, flush: async () => undefined, clear: () => {}, rejectConflict: () => {} }));
import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { DistributionWorkspace } from './WarehouseDistributionPanel';

const lot = { lotId: 5, warehouseInvoiceId: 10, invoiceNumber: 'НК-10', invoiceLineIndex: 0, materialName: 'Кабель', unit: 'м', availableQuantity: '10' };
const props = { companyContext: { mode: 'company', selectedCompanyId: 2, companies: [{ companyId: 2, role: 'директор' }, { companyId: 3, role: 'директор' }] }, projects: [{ id: 11, companyId: 2, name: 'Школа' }, { id: 13, companyId: 2, name: 'Сад' }] };
const ok = data => ({ ok: true, json: async () => data });
const page = (items, nextCursor = null) => ok({ items, truncated: nextCursor !== null, nextCursor });
const oldFetch = global.fetch;
const oldCrypto = global.crypto;
beforeAll(() => Object.defineProperty(global, 'crypto', { configurable: true, value: require('crypto').webcrypto }));
beforeEach(() => { sessionStorage.clear(); global.fetch = jest.fn(async url => page(url.includes('/sources') ? [lot] : [])); });
afterEach(() => { global.fetch = oldFetch; });
afterAll(() => Object.defineProperty(global, 'crypto', { configurable: true, value: oldCrypto }));
async function fillBatch() {
  await screen.findByRole('option', { name: /НК-10/ });
  await waitFor(() => expect(screen.getByRole('button', { name: 'Обновить', exact: true })).toBeEnabled());
  fireEvent.change(screen.getByLabelText('Партия 1'), { target: { value: '5' } });
  fireEvent.change(screen.getByLabelText('Объект 1'), { target: { value: '11' } });
  fireEvent.change(screen.getByLabelText('Количество 1'), { target: { value: '5' } });
  fireEvent.change(screen.getByLabelText('Основание распределения'), { target: { value: 'По заявке' } });
  expect(screen.getByText('Распределить одним пакетом')).toBeEnabled();
}
function expectDraft() {
  expect(screen.getByLabelText('Партия 1')).toHaveValue('5');
  expect(screen.getByRole('option', { name: /НК-10/ })).toBeInTheDocument();
  expect(screen.getByLabelText('Объект 1')).toHaveValue('11');
  expect(screen.getByLabelText('Количество 1')).toHaveValue('5');
  expect(screen.getByLabelText('Основание распределения')).toHaveValue('По заявке');
}
function search(value) {
  fireEvent.change(screen.getByLabelText('Поиск партий'), { target: { value } });
  fireEvent.click(screen.getByText('Найти партии'));
}
const refresh = () => fireEvent.click(screen.getByRole('button', { name: 'Обновить', exact: true }));
test('a cached selection never restores a larger old balance after another search', async () => {
  render(<DistributionWorkspace {...props} />); await fillBatch();
  global.fetch = jest.fn(async url => page(url.includes('q=') && !decodeURIComponent(url).includes('Кабель') ? [] : [{ ...lot, availableQuantity: '2' }]));
  search('Кабель');
  await screen.findByText(/Доступно 2 м/);
  expect(screen.getByText('Распределить одним пакетом')).toBeDisabled();
  search('Другой материал');
  await screen.findByText('По заданному поиску партий не найдено.');
  expectDraft();
  expect(screen.getByText(/Доступно 2 м/)).toBeInTheDocument();
  expect(screen.getByText('Распределить одним пакетом')).toBeDisabled();
});
test('a full refresh under a filter retains selected lot identity but requires its balance to be reloaded', async () => {
  render(<DistributionWorkspace {...props} />); await fillBatch();
  global.fetch = jest.fn(async () => page([]));
  search('Другой материал');
  await screen.findByText('По заданному поиску партий не найдено.');
  refresh();
  await waitFor(() => expect(screen.getByRole('button', { name: 'Обновить', exact: true })).toBeEnabled());
  expectDraft();
  expect(screen.getByText('Распределить одним пакетом')).toBeDisabled();
  expect(screen.getByRole('option', { name: /НК-10.*остаток не подтверждён/ })).toBeInTheDocument();
  global.fetch = jest.fn(async url => page(url.includes('/sources') ? [lot] : []));
  search('');
  await waitFor(() => expect(screen.getByText('Распределить одним пакетом')).toBeEnabled());
  expectDraft();
});
test('source read failure preserves selected rows without allowing a new issue', async () => {
  render(<DistributionWorkspace {...props} />); await fillBatch();
  global.fetch = jest.fn(async () => ({ ok: false, status: 503, json: async () => ({ detail: 'Партии недоступны' }) }));
  search('Кабель'); await screen.findByText('Партии недоступны');
  expectDraft();
  expect(screen.getByText('Распределить одним пакетом')).toBeDisabled();
  expect(screen.getByLabelText('Количество 1')).toBeEnabled();
});
test('a lot absent from a refreshed unfiltered list cannot use its cached positive quantity', async () => {
  render(<DistributionWorkspace {...props} />); await fillBatch();
  global.fetch = jest.fn(async () => page([]));
  search('');
  await screen.findByText(/Нет доступных партий общего склада/);
  expectDraft();
  expect(screen.getByText('Распределить одним пакетом')).toBeDisabled();
  expect(screen.queryByText(/Доступно 10 м/)).not.toBeInTheDocument();
});
test('safe retry of a return must not clear an unrelated batch draft', async () => {
  const allocation = { id: 8, projectId: 11, projectName: 'Школа', materialName: 'Кабель', unit: 'м', quantity: '5', returnedQuantity: '0', netQuantity: '5', returns: [] };
  global.fetch = jest.fn(async url => page(url.includes('/sources') ? [lot] : [allocation]));
  render(<DistributionWorkspace {...props} />); await fillBatch();
  fireEvent.click(screen.getByText('Оформить возврат'));
  fireEvent.change(screen.getByLabelText('Количество возврата'), { target: { value: '1' } });
  fireEvent.change(screen.getByLabelText('Основание возврата'), { target: { value: 'Вернуть лишнее' } });
  fireEvent.click(screen.getByLabelText(/Подтверждаю фактический возврат/));
  const read = global.fetch;
  global.fetch = jest.fn((url, options) => options?.method === 'POST' ? Promise.reject(new Error('Ответ потерян')) : read(url, options));
  fireEvent.click(screen.getByText('Подтвердить возврат'));
  await screen.findByText(/Ответ потерян/);
  const firstBody = global.fetch.mock.calls.find(([, options]) => options?.method === 'POST')[1].body;
  global.fetch = jest.fn((url, options) => options?.method === 'POST'
    ? Promise.resolve(ok({ ok: true, requestId: JSON.parse(options.body).requestId, item: allocation })) : read(url, options));
  fireEvent.click(screen.getByText('Повторить неподтверждённую операцию'));
  await screen.findByText(/Операция сохранена/);
  await waitFor(() => expect(screen.getByRole('button', { name: 'Обновить', exact: true })).toBeEnabled());
  expectDraft();
  expect(screen.queryByLabelText('Количество возврата')).not.toBeInTheDocument();
  expect(global.fetch.mock.calls.find(([, options]) => options?.method === 'POST')[1].body).toBe(firstBody);
});
test('an older source response cannot restore the cached balance after a newer search', async () => {
  render(<DistributionWorkspace {...props} />); await fillBatch();
  let finish;
  global.fetch = jest.fn().mockImplementationOnce(() => new Promise(resolve => { finish = resolve; }))
    .mockResolvedValueOnce(page([{ ...lot, availableQuantity: '2' }]));
  search('Старый'); search('Новый');
  await screen.findByText(/Доступно 2 м/);
  await act(async () => finish(page([lot])));
  global.fetch = jest.fn(async () => page([])); search('Другой');
  await screen.findByText('По заданному поиску партий не найдено.');
  expectDraft();
  expect(screen.getByText(/Доступно 2 м/)).toBeInTheDocument();
  expect(screen.getByText('Распределить одним пакетом')).toBeDisabled();
});
test.each([401, 403])('source denial %s removes cached identity and disables new issues', async status => {
  render(<DistributionWorkspace {...props} />); await fillBatch();
  global.fetch = jest.fn(async () => ({ ok: false, status, json: async () => ({ detail: 'Нет доступа' }) }));
  search('Кабель'); await screen.findByText('Нет доступа');
  expect(screen.queryByRole('option', { name: /НК-10/ })).not.toBeInTheDocument();
  expect(screen.getByLabelText('Партия 1')).toHaveValue('');
  expect(screen.getByText('Распределить одним пакетом')).toBeDisabled();
});
test('a selected lot from a later page survives refresh and is revalidated by loading that page', async () => {
  global.fetch = jest.fn(async url => !url.includes('/sources') ? page([])
    : url.includes('beforeId=') ? page([lot]) : page([{ ...lot, lotId: 6, invoiceNumber: 'НК-11' }], 6));
  render(<DistributionWorkspace {...props} />);
  fireEvent.click(await screen.findByText('Загрузить ещё партии'));
  await fillBatch();
  refresh();
  await waitFor(() => expect(screen.getByRole('button', { name: 'Обновить', exact: true })).toBeEnabled());
  expectDraft();
  expect(screen.getByText('Распределить одним пакетом')).toBeDisabled();
  fireEvent.click(screen.getByText('Загрузить ещё партии'));
  await waitFor(() => expect(screen.getByText('Распределить одним пакетом')).toBeEnabled());
  expectDraft();
});
test('form submission during a source search cannot send a cached snapshot', async () => {
  render(<DistributionWorkspace {...props} />); await fillBatch();
  let finish;
  global.fetch = jest.fn(() => new Promise(resolve => { finish = resolve; }));
  search('Другой');
  fireEvent.submit(screen.getByText('Распределить одним пакетом').closest('form'));
  expect(global.fetch.mock.calls.some(([, options]) => options?.method === 'POST')).toBe(false);
  await act(async () => finish(page([])));
});
test.each([false, true])('successful batch retry=%s clears only the completed draft and its cached options', async retry => {
  render(<DistributionWorkspace {...props} />); await fillBatch();
  const writes = [];
  global.fetch = jest.fn(async (_url, options) => {
    if (options?.method !== 'POST') return page([]);
    writes.push(options.body);
    if (retry && writes.length === 1) throw Error('Ответ потерян');
    return ok({ ok: true, requestId: JSON.parse(options.body).requestId, items: [{ id: 8 }] });
  });
  fireEvent.click(screen.getByText('Распределить одним пакетом'));
  if (retry) {
    await screen.findByText(/Ответ потерян/);
    refresh();
    await waitFor(() => expect(screen.getByRole('button', { name: 'Обновить', exact: true })).toBeEnabled());
    expectDraft();
    fireEvent.click(screen.getByText('Повторить неподтверждённую операцию'));
  }
  await screen.findByText(/Операция сохранена/);
  await waitFor(() => expect(screen.getByRole('button', { name: 'Обновить', exact: true })).toBeEnabled());
  expect(screen.getByLabelText('Партия 1')).toHaveValue('');
  expect(screen.getByLabelText('Количество 1')).toHaveValue('');
  expect(screen.getByLabelText('Основание распределения')).toHaveValue('');
  expect(screen.queryByRole('option', { name: /НК-10/ })).not.toBeInTheDocument();
  expect(writes).toHaveLength(retry ? 2 : 1);
  if (retry) expect(writes[1]).toBe(writes[0]);
  expect(JSON.parse(writes[0])).toMatchObject({ companyId: 2, reason: 'По заявке', rows: [{ lotId: 5, projectId: 11, quantity: '5' }] });
});
