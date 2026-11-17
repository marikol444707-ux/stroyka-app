// Return persistence is verified separately in WarehouseReturnPersistence.test.jsx.
jest.mock('./useWarehouseReturnDraft', () => () => ({ loading: false, saving: false, dirty: false, error: '', phase: 'ready', readyToSubmit: true, flush: async () => undefined, rejectConflict: () => {} }));
// These source/command regressions isolate draft transport; actual persistence is covered in WarehouseBatchPersistence.test.jsx.
jest.mock('./useWarehouseBatchDraft', () => () => ({ loading: false, saving: false, dirty: false, error: '', phase: 'ready', readyToSubmit: true, flush: async () => undefined, clear: () => {}, rejectConflict: () => {} }));
import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { DistributionWorkspace } from './WarehouseDistributionPanel';

const allocation = { id: 8, lotId: 5, warehouseInvoiceId: 10, projectId: 11, projectName: 'Школа', materialName: 'Кабель', unit: 'м', quantity: '20', returnedQuantity: '5', netQuantity: '15', returns: [] };
const props = { companyContext: { mode: 'company', selectedCompanyId: 2, companies: [{ companyId: 2, role: 'директор' }, { companyId: 3, role: 'директор' }] }, projects: [{ id: 11, companyId: 2, name: 'Школа' }, { id: 13, companyId: 2, name: 'Сад' }] };
const ok = data => ({ ok: true, json: async () => data });
const page = items => ok({ items, truncated: false, nextCursor: null });
const originalFetch = global.fetch;
const originalCrypto = global.crypto;
const originalFlag = process.env.REACT_APP_WAREHOUSE_DISTRIBUTION_TRANSFERS_ENABLED;
beforeAll(() => Object.defineProperty(global, 'crypto', { configurable: true, value: require('crypto').webcrypto }));
beforeEach(() => {
  sessionStorage.clear();
  process.env.REACT_APP_WAREHOUSE_DISTRIBUTION_TRANSFERS_ENABLED = 'true';
  global.fetch = jest.fn(async url => url.includes('/sources') || url.includes('/transfers') ? page([])
    : page([allocation, { ...allocation, id: 7, materialName: 'Краска' }]));
});
afterEach(() => { global.fetch = originalFetch; });
afterAll(() => {
  Object.defineProperty(global, 'crypto', { configurable: true, value: originalCrypto });
  if (originalFlag === undefined) delete process.env.REACT_APP_WAREHOUSE_DISTRIBUTION_TRANSFERS_ENABLED;
  else process.env.REACT_APP_WAREHOUSE_DISTRIBUTION_TRANSFERS_ENABLED = originalFlag;
});
async function fillReturn() {
  const buttons = await screen.findAllByText('Оформить возврат');
  await waitFor(() => expect(screen.getByRole('button', { name: 'Обновить', exact: true })).toBeEnabled());
  fireEvent.click(buttons[0]);
  fireEvent.change(screen.getByLabelText('Количество возврата'), { target: { value: '10' } });
  fireEvent.change(screen.getByLabelText('Основание возврата'), { target: { value: 'Материал не потребовался' } });
  fireEvent.click(screen.getByLabelText(/Подтверждаю фактический возврат/));
  expect(screen.getByText('Подтвердить возврат')).toBeEnabled();
}
function expectDraft() {
  expect(screen.getByLabelText('Количество возврата')).toHaveValue('10');
  expect(screen.getByLabelText('Основание возврата')).toHaveValue('Материал не потребовался');
  expect(screen.getByLabelText(/Подтверждаю фактический возврат/)).toBeChecked();
}
const refresh = () => fireEvent.click(screen.getByRole('button', { name: 'Обновить', exact: true }));
test('return draft survives refresh and a smaller fresh entitlement blocks submission', async () => {
  render(<DistributionWorkspace {...props} />);
  await fillReturn();
  const read = global.fetch;
  let finish;
  global.fetch = jest.fn((url, options) => url.includes('/sources') || url.includes('/transfers') ? read(url, options)
    : new Promise(resolve => { finish = resolve; }));
  refresh();
  expectDraft();
  expect(screen.getByText('Подтвердить возврат')).toBeDisabled();
  await act(async () => finish(page([{ ...allocation, netQuantity: '2', returnedQuantity: '18' }])));
  expectDraft();
  expect(screen.getByText(/Максимум по распределению: 2 м/)).toBeInTheDocument();
  expect(screen.getByText('Подтвердить возврат')).toBeDisabled();
});
test('an empty history filter keeps the return draft but disables sending until the source returns', async () => {
  render(<DistributionWorkspace {...props} />);
  await fillReturn();
  const read = global.fetch;
  global.fetch = jest.fn((url, options) => url.includes('q=') ? Promise.resolve(page([])) : read(url, options));
  fireEvent.change(screen.getByLabelText('Найти по объекту, материалу или накладной'), { target: { value: 'Нет совпадений' } });
  fireEvent.click(screen.getByText('Применить фильтры'));
  await screen.findByText('По заданным фильтрам распределений не найдено.');
  expectDraft();
  expect(screen.getByText('Подтвердить возврат')).toBeDisabled();
  fireEvent.change(screen.getByLabelText('Найти по объекту, материалу или накладной'), { target: { value: '' } });
  fireEvent.click(screen.getByText('Применить фильтры'));
  await waitFor(() => expect(screen.getByText('Подтвердить возврат')).toBeEnabled());
  expectDraft();
});
test('failed history refresh preserves an editable return and permits cancellation', async () => {
  render(<DistributionWorkspace {...props} />);
  await fillReturn();
  const read = global.fetch;
  global.fetch = jest.fn((url, options) => url.includes('/sources') || url.includes('/transfers') ? read(url, options)
    : Promise.resolve({ ok: false, status: 503, json: async () => ({ detail: 'Ошибка загрузки истории' }) }));
  refresh();
  await screen.findByText('Ошибка загрузки истории');
  expectDraft();
  expect(screen.getByLabelText('Количество возврата')).toBeEnabled();
  expect(screen.getByText('Подтвердить возврат')).toBeDisabled();
  fireEvent.click(screen.getByRole('button', { name: 'Отмена', exact: true }));
  expect(screen.queryByLabelText('Количество возврата')).not.toBeInTheDocument();
});
test('another return cannot replace the filled draft before explicit cancellation', async () => {
  render(<DistributionWorkspace {...props} />);
  await fillReturn();
  fireEvent.click(screen.getAllByText('Оформить возврат')[1]);
  expectDraft();
  expect(screen.getByText('Возврат: Школа · Кабель')).toBeInTheDocument();
  expect(screen.getAllByText('Оформить возврат')[1]).toBeDisabled();
  fireEvent.click(screen.getByRole('button', { name: 'Отмена', exact: true }));
  fireEvent.click(screen.getAllByText('Оформить возврат')[1]);
  expect(screen.getByText('Возврат: Школа · Краска')).toBeInTheDocument();
  expect(screen.getByLabelText('Количество возврата')).toHaveValue('');
  expect(screen.getByLabelText(/Подтверждаю фактический возврат/)).not.toBeChecked();
});
test('dispatch cannot close an unfinished return', async () => {
  render(<DistributionWorkspace {...props} />);
  await fillReturn();
  fireEvent.click(screen.getAllByText('Отправить на другой объект')[0]);
  expectDraft();
  expect(screen.queryByLabelText('Количество отправки')).not.toBeInTheDocument();
  expect(screen.getAllByText('Отправить на другой объект')[0]).toBeDisabled();
});
test('after refresh a return posts once to the original allocation and closes only on success', async () => {
  render(<DistributionWorkspace {...props} />);
  await fillReturn(); refresh();
  await waitFor(() => expect(screen.getByText('Подтвердить возврат')).toBeEnabled());
  const read = global.fetch;
  global.fetch = jest.fn((url, options) => options?.method === 'POST'
    ? Promise.resolve(ok({ ok: true, requestId: JSON.parse(options.body).requestId, item: { ...allocation, returnedQuantity: '15', netQuantity: '5' } })) : read(url, options));
  fireEvent.click(screen.getByText('Подтвердить возврат'));
  await screen.findByText(/Операция сохранена/);
  await waitFor(() => expect(screen.getByRole('button', { name: 'Обновить', exact: true })).toBeEnabled());
  expect(screen.queryByLabelText('Количество возврата')).not.toBeInTheDocument();
  const writes = global.fetch.mock.calls.filter(([, options]) => options?.method === 'POST');
  expect(writes).toHaveLength(1);
  expect(writes[0][0]).toMatch(/\/warehouse-distributions\/8\/returns$/);
  expect(JSON.parse(writes[0][1].body)).toMatchObject({ companyId: 2, quantity: '10', reason: 'Материал не потребовался' });
});
test('a rejected return keeps local edits and does not claim success or retry automatically', async () => {
  render(<DistributionWorkspace {...props} />);
  await fillReturn();
  global.fetch = jest.fn(async () => ({ ok: false, status: 409, json: async () => ({ detail: 'Остаток изменился' }) }));
  fireEvent.click(screen.getByText('Подтвердить возврат'));
  await screen.findByText(/Остаток изменился/);
  expectDraft();
  expect(screen.queryByText(/Операция сохранена/)).not.toBeInTheDocument();
  expect(global.fetch).toHaveBeenCalledTimes(1);
});
test('lost return response survives an empty refresh and repeats exactly the original command', async () => {
  render(<DistributionWorkspace {...props} />);
  await fillReturn();
  const read = global.fetch;
  global.fetch = jest.fn((url, options) => options?.method === 'POST' ? Promise.reject(new Error('Ответ потерян')) : read(url, options));
  fireEvent.click(screen.getByText('Подтвердить возврат'));
  await screen.findByText(/Ответ потерян/);
  const first = global.fetch.mock.calls.find(([, options]) => options?.method === 'POST')[1].body;
  global.fetch = jest.fn(async () => page([]));
  refresh();
  await screen.findByText('Распределений в выбранной компании пока нет.');
  expectDraft();
  expect(screen.getByText('Подтвердить возврат')).toBeDisabled();
  global.fetch = jest.fn((url, options) => options?.method === 'POST'
    ? Promise.resolve(ok({ ok: true, requestId: JSON.parse(options.body).requestId, item: allocation })) : read(url, options));
  fireEvent.click(screen.getByText('Повторить неподтверждённую операцию'));
  await screen.findByText(/Операция сохранена/);
  await waitFor(() => expect(screen.getByRole('button', { name: 'Обновить', exact: true })).toBeEnabled());
  const writes = global.fetch.mock.calls.filter(([, options]) => options?.method === 'POST');
  expect(writes).toHaveLength(1);
  expect(writes[0][1].body).toBe(first);
});
test.each([401, 403])('read denial %s hides the return and prevents writes', async status => {
  render(<DistributionWorkspace {...props} />);
  await fillReturn();
  global.fetch = jest.fn(async () => ({ ok: false, status, json: async () => ({ detail: 'Нет доступа' }) }));
  refresh(); await screen.findByText('Нет доступа');
  expect(screen.queryByLabelText('Количество возврата')).not.toBeInTheDocument();
  expect(global.fetch.mock.calls.some(([, options]) => options?.method === 'POST')).toBe(false);
});
test.each(['company', 'role'])('late read cannot restore the return after a change of %s', async change => {
  const view = render(<DistributionWorkspace {...props} />);
  await fillReturn();
  const read = global.fetch; let finish;
  global.fetch = jest.fn((url, options) => url.includes('/sources') || url.includes('/transfers') ? read(url, options)
    : new Promise(resolve => { finish = resolve; }));
  refresh();
  global.fetch = jest.fn(async () => page([]));
  view.rerender(<DistributionWorkspace {...props} readOnly={change === 'role'} companyContext={{ ...props.companyContext, selectedCompanyId: change === 'company' ? 3 : 2 }} />);
  await screen.findByText('Распределений в выбранной компании пока нет.');
  await act(async () => finish(page([allocation])));
  expect(screen.queryByLabelText('Количество возврата')).not.toBeInTheDocument();
  expect(screen.queryByText('Школа · Кабель')).not.toBeInTheDocument();
});
test('late unfiltered history cannot enable a return absent from the current search', async () => {
  render(<DistributionWorkspace {...props} />);
  await fillReturn();
  const read = global.fetch; let finish;
  global.fetch = jest.fn((url, options) => url.includes('/sources') || url.includes('/transfers') ? read(url, options)
    : new Promise(resolve => { finish = resolve; }));
  refresh();
  global.fetch = jest.fn(async () => page([]));
  fireEvent.change(screen.getByLabelText('Найти по объекту, материалу или накладной'), { target: { value: 'Нет совпадений' } });
  fireEvent.click(screen.getByText('Применить фильтры'));
  await screen.findByText('По заданным фильтрам распределений не найдено.');
  await act(async () => finish(page([allocation])));
  expectDraft();
  expect(screen.getByText('Подтвердить возврат')).toBeDisabled();
});
