import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import WarehouseDistributionPanel, { DistributionWorkspace } from './WarehouseDistributionPanel';

const companyContext = { mode: 'company', selectedCompanyId: 2, companies: [{ companyId: 2, role: 'директор' }] };
const sources = [{ lotId: 5, warehouseInvoiceId: 10, invoiceNumber: 'НК-10', invoiceLineIndex: 0, materialName: 'Кабель', unit: 'м', availableQuantity: '100' }];
const records = [{ id: 8, lotId: 5, warehouseInvoiceId: 10, invoiceNumber: 'НК-10', projectId: 11, projectName: 'Школа', materialName: 'Кабель', unit: 'м', quantity: '20', returnedQuantity: '5', netQuantity: '15', returns: [] }];
const props = { companyContext, projects: [{ id: 11, companyId: 2, name: 'Школа' }, { id: 12, companyId: 3, name: 'Школа' }], C: {}, refreshData: jest.fn() };
const oldFetch = global.fetch;
const oldCrypto = global.crypto;
beforeAll(() => { Object.defineProperty(global, 'crypto', { configurable: true, value: require('crypto').webcrypto }); });
afterAll(() => { Object.defineProperty(global, 'crypto', { configurable: true, value: oldCrypto }); });
beforeEach(() => { sessionStorage.clear(); global.fetch = jest.fn(async (url, options) => ({ ok: true, json: async () => options?.method === 'POST' ? { ok: true, requestId: JSON.parse(options.body).requestId, items: JSON.parse(options.body).rows?.map((row, i) => ({ ...records[0], id: 8 + i })) || records, item: records[0] } : { items: url.includes('/sources') ? sources : records } })); });
afterEach(() => { global.fetch = oldFetch; });

test('feature is invisible and does not fetch when flag is disabled', () => {
  const previous = process.env.REACT_APP_WAREHOUSE_DISTRIBUTION_ENABLED;
  delete process.env.REACT_APP_WAREHOUSE_DISTRIBUTION_ENABLED;
  try {
    const { container } = render(<WarehouseDistributionPanel {...props} />);
    expect(container).toBeEmptyDOMElement();
    expect(global.fetch).not.toHaveBeenCalled();
  } finally {
    if (previous === undefined) delete process.env.REACT_APP_WAREHOUSE_DISTRIBUTION_ENABLED;
    else process.env.REACT_APP_WAREHOUSE_DISTRIBUTION_ENABLED = previous;
  }
});

test('company-scoped sources and records show net issued, not supplier debt', async () => {
  render(<DistributionWorkspace {...props} />);
  expect(await screen.findByText(/Осталось по распределению: 15 м/)).toBeInTheDocument();
  expect(screen.getByText(/не новый долг/)).toBeInTheDocument();
  expect(screen.getByText(/Осталось по распределению — выданное минус возвраты и отправки на другие объекты, а не фактический остаток на объекте/)).toBeInTheDocument();
  expect(screen.queryByText(/Не возвращено/)).not.toBeInTheDocument();
  expect(screen.getAllByRole('option', { name: /Школа/ })).toHaveLength(2);
});

test('batch sends all rows in one command with explicit source/project IDs', async () => {
  render(<DistributionWorkspace {...props} />);
  await screen.findByText(/Осталось по распределению: 15 м/);
  fireEvent.change(screen.getByLabelText('Партия 1'), { target: { value: '5' } });
  fireEvent.change(screen.getByLabelText('Объект 1'), { target: { value: '11' } });
  fireEvent.change(screen.getByLabelText('Количество 1'), { target: { value: '10' } });
  fireEvent.change(screen.getByLabelText('Основание распределения'), { target: { value: 'По заявке' } });
  fireEvent.click(screen.getByRole('button', { name: 'Распределить одним пакетом' }));
  await waitFor(() => expect(global.fetch.mock.calls.some(call => call[1]?.method === 'POST')).toBe(true));
  const [, options] = global.fetch.mock.calls.find(call => call[1]?.method === 'POST');
  expect(JSON.parse(options.body)).toMatchObject({ companyId: 2, reason: 'По заявке', rows: [{ lotId: 5, projectId: 11, quantity: '10' }] });
});

test('accounting read view has no allocation or return commands', async () => {
  render(<DistributionWorkspace {...props} readOnly />);
  await screen.findByText(/Осталось по распределению: 15 м/);
  expect(screen.queryByRole('button', { name: 'Оформить возврат' })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Распределить одним пакетом' })).not.toBeInTheDocument();
});

test('all-company mode does not query or write', () => {
  render(<DistributionWorkspace {...props} companyContext={{ ...companyContext, mode: 'all_companies' }} />);
  expect(screen.getByText(/Выберите одну компанию/)).toBeInTheDocument();
  expect(global.fetch).not.toHaveBeenCalled();
});

test('return requires physical confirmation and carries exact allocation ID', async () => {
  render(<DistributionWorkspace {...props} />);
  await screen.findByText(/Осталось по распределению: 15 м/);
  fireEvent.click(screen.getByRole('button', { name: 'Оформить возврат' }));
  fireEvent.change(screen.getByLabelText('Количество возврата'), { target: { value: '3' } });
  fireEvent.change(screen.getByLabelText('Основание возврата'), { target: { value: 'Не потребовалось' } });
  expect(screen.getByRole('button', { name: 'Подтвердить возврат' })).toBeDisabled();
  fireEvent.click(screen.getByLabelText(/Подтверждаю фактический возврат/));
  fireEvent.click(screen.getByRole('button', { name: 'Подтвердить возврат' }));
  await waitFor(() => expect(global.fetch.mock.calls.some(call => call[0].endsWith('/8/returns'))).toBe(true));
});

async function fillBatch() {
  await screen.findByText(/Осталось по распределению: 15 м/);
  fireEvent.change(screen.getByLabelText('Партия 1'), { target: { value: '5' } });
  fireEvent.change(screen.getByLabelText('Объект 1'), { target: { value: '11' } });
  fireEvent.change(screen.getByLabelText('Количество 1'), { target: { value: '10' } });
  fireEvent.change(screen.getByLabelText('Основание распределения'), { target: { value: 'По заявке' } });
}

test('two rows are sent atomically and rapid double click does not duplicate command', async () => {
  render(<DistributionWorkspace {...props} />);
  await fillBatch();
  fireEvent.click(screen.getByText('Добавить строку'));
  fireEvent.change(screen.getByLabelText('Партия 2'), { target: { value: '5' } });
  fireEvent.change(screen.getByLabelText('Объект 2'), { target: { value: '11' } });
  fireEvent.change(screen.getByLabelText('Количество 2'), { target: { value: '2.5' } });
  const button = screen.getByText('Распределить одним пакетом');
  fireEvent.click(button); fireEvent.click(button);
  await screen.findByText(/Операция сохранена/);
  const commands = global.fetch.mock.calls.filter(c => c[1]?.method === 'POST');
  expect(commands).toHaveLength(1);
  expect(JSON.parse(commands[0][1].body).rows).toHaveLength(2);
});

test('network retry reuses the same UUID and body', async () => {
  const fetchRead = global.fetch;
  let failed = false;
  global.fetch = jest.fn((url, options) => {
    if (options?.method === 'POST' && !failed) { failed = true; return Promise.reject(new Error('Связь прервана')); }
    return fetchRead(url, options);
  });
  render(<DistributionWorkspace {...props} />);
  await fillBatch();
  fireEvent.click(screen.getByText('Распределить одним пакетом'));
  await screen.findByRole('alert');
  fireEvent.click(screen.getByText('Повторить неподтверждённую операцию'));
  await screen.findByText(/Операция сохранена/);
  const commands = global.fetch.mock.calls.filter(c => c[1]?.method === 'POST');
  expect(commands).toHaveLength(2);
  expect(commands[0][1].body).toBe(commands[1][1].body);
  expect(JSON.parse(commands[0][1].body).requestId).toMatch(/^[a-f0-9-]{36}$/);
});

test('company switch discards old records and draft', async () => {
  const { rerender } = render(<DistributionWorkspace {...props} />);
  await fillBatch();
  global.fetch = jest.fn(async () => ({ ok: true, json: async () => ({ items: [] }) }));
  rerender(<DistributionWorkspace {...props} companyContext={{ mode: 'company', selectedCompanyId: 3, companies: [{ companyId: 3, role: 'директор' }] }} />);
  expect(await screen.findByText(/Распределений в выбранной компании пока нет/)).toBeInTheDocument();
  expect(screen.queryByText(/Осталось по распределению: 15 м/)).not.toBeInTheDocument();
  expect(screen.getByLabelText('Основание распределения')).toHaveValue('');
  expect(global.fetch.mock.calls[0][1].headers['X-Company-Id']).toBe('3');
});

test('non-finance membership cannot fetch history', () => {
  render(<DistributionWorkspace {...props} companyContext={{ ...companyContext, companies: [{ companyId: 2, role: 'прораб' }] }} />);
  expect(global.fetch).not.toHaveBeenCalled();
});

test('accountant can read but cannot write even without readOnly prop', async () => {
  render(<DistributionWorkspace {...props} companyContext={{ ...companyContext, companies: [{ companyId: 2, role: 'бухгалтер' }] }} />);
  await screen.findByText(/Осталось по распределению: 15 м/);
  expect(screen.queryByText('Распределить одним пакетом')).not.toBeInTheDocument();
  expect(global.fetch.mock.calls).toHaveLength(1);
});

test('history search applies server filters only on submit', async () => {
  render(<DistributionWorkspace {...props} readOnly />);
  await screen.findByText(/Осталось по распределению: 15 м/);
  const search = screen.getByLabelText('Найти по объекту, материалу или накладной');
  fireEvent.change(search, { target: { value: 'Другой объект' } });
  expect(screen.getByText(/Осталось по распределению: 15 м/)).toBeInTheDocument();
  expect(global.fetch.mock.calls).toHaveLength(1);
  fireEvent.change(screen.getByLabelText('История: объект'), { target: { value: '11' } });
  fireEvent.change(screen.getByLabelText('Дата с'), { target: { value: '2026-09-01' } });
  fireEvent.change(screen.getByLabelText('Дата по'), { target: { value: '2026-09-16' } });
  fireEvent.click(screen.getByText('Применить фильтры'));
  await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(2));
  const query = new URL(global.fetch.mock.calls[1][0], 'http://localhost').searchParams;
  expect(Object.fromEntries(query)).toEqual({ limit: '100', q: 'Другой объект', projectId: '11', dateFrom: '2026-09-01', dateTo: '2026-09-16' });
});

test.each(['кладовщик', 'снабженец'])('%s can allocate and return', async role => {
  render(<DistributionWorkspace {...props} companyContext={{ ...companyContext, companies: [{ companyId: 2, role }] }} />);
  await fillBatch();
  expect(screen.getByText('Распределить одним пакетом')).toBeEnabled();
  expect(screen.getByText('Оформить возврат')).toBeEnabled();
});

test('history and sources load more, preserving selected source across server searches', async () => {
  global.fetch = jest.fn(async url => {
    const query = new URL(url, 'http://localhost').searchParams;
    const source = url.includes('/sources');
    const more = query.has('beforeId');
    return { ok: true, json: async () => source
      ? { items: query.has('q') ? [{ ...sources[0], lotId: 3, materialName: 'Труба' }] : more ? [{ ...sources[0], lotId: 4 }] : sources, truncated: !more && !query.has('q'), nextCursor: more || query.has('q') ? null : 5 }
      : { items: more ? [{ ...records[0], id: 7, projectName: 'Склад' }] : records, truncated: !more, nextCursor: more ? null : 8 } };
  });
  render(<DistributionWorkspace {...props} />);
  await fillBatch();
  fireEvent.click(screen.getByText('Загрузить ещё распределения'));
  await screen.findByText('Склад · Кабель');
  expect(screen.queryByText('Загрузить ещё распределения')).not.toBeInTheDocument();
  fireEvent.click(screen.getByText('Загрузить ещё партии'));
  await waitFor(() => expect(screen.getByLabelText('Партия 1').options).toHaveLength(3));
  fireEvent.change(screen.getByLabelText('Поиск партий'), { target: { value: 'Труба' } });
  fireEvent.click(screen.getByText('Найти партии'));
  await screen.findByRole('option', { name: /Труба/ });
  expect(screen.getByLabelText('Партия 1')).toHaveValue('5');
  expect(screen.getByText('Распределить одним пакетом')).toBeEnabled();
  expect(global.fetch.mock.calls.some(([url]) => url.includes('beforeId=8'))).toBe(true);
  expect(global.fetch.mock.calls.some(([url]) => url.includes('beforeId=5'))).toBe(true);
});

test('unanswered command survives a remount with its original UUID', async () => {
  const readFetch = global.fetch;
  let first = true;
  global.fetch = jest.fn((url, options) => {
    if (options?.method === 'POST' && first) { first = false; return Promise.reject(new Error('Ответ потерян')); }
    return readFetch(url, options);
  });
  const view = render(<DistributionWorkspace {...props} />);
  await fillBatch(); fireEvent.click(screen.getByText('Распределить одним пакетом'));
  await screen.findByRole('alert'); view.unmount();
  render(<DistributionWorkspace {...props} />);
  fireEvent.click(await screen.findByText('Повторить неподтверждённую операцию'));
  await screen.findByText(/Операция сохранена/);
  const writes = global.fetch.mock.calls.filter(c => c[1]?.method === 'POST');
  expect(writes).toHaveLength(2); expect(writes[0][1].body).toBe(writes[1][1].body);
});

test('unknown success payload retains pending command instead of claiming success', async () => {
  const readFetch = global.fetch;
  global.fetch = jest.fn((url, options) => options?.method === 'POST' ? Promise.resolve({ ok: true, json: async () => ({ ok: false }) }) : readFetch(url, options));
  render(<DistributionWorkspace {...props} />);
  await fillBatch(); fireEvent.click(screen.getByText('Распределить одним пакетом'));
  expect(await screen.findByRole('alert')).toHaveTextContent('Результат операции не подтверждён');
  expect(screen.queryByText(/Операция сохранена/)).not.toBeInTheDocument();
  expect(screen.getByText('Распределить одним пакетом')).toBeDisabled();
  expect(screen.getByText('Повторить неподтверждённую операцию')).toBeEnabled();
});

test('malformed GET cannot crash rendering', async () => {
  global.fetch = jest.fn(async () => ({ ok: true, json: async () => ({ items: {} }) }));
  render(<DistributionWorkspace {...props} />);
  expect((await screen.findAllByRole('alert')).every(element => element.textContent.includes('неизвестный формат'))).toBe(true);
});

const response = data => ({ ok: true, json: async () => ({ ...('nextCursor' in data ? { truncated: data.nextCursor !== null } : {}), ...data }) });

test.each([
  ['Найти по объекту, материалу или накладной', 'нет совпадений'],
  ['История: объект', '11'],
  ['Дата с', '2026-09-01'],
  ['Дата по', '2026-09-16'],
])('empty history reflects applied filter %s, not an unsent draft', async (label, value) => {
  global.fetch = jest.fn(async () => response({ items: [], nextCursor: null }));
  render(<DistributionWorkspace {...props} readOnly />);
  await screen.findByText('Распределений в выбранной компании пока нет.');
  fireEvent.change(screen.getByLabelText(label), { target: { value } });
  expect(screen.queryByText('По заданным фильтрам распределений не найдено.')).not.toBeInTheDocument();
  fireEvent.click(screen.getByText('Применить фильтры'));
  await screen.findByText('По заданным фильтрам распределений не найдено.');
  expect(screen.queryByText('Распределений в выбранной компании пока нет.')).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText(label), { target: { value: '' } });
  expect(screen.getByText('По заданным фильтрам распределений не найдено.')).toBeInTheDocument();
  fireEvent.click(screen.getByText('Применить фильтры'));
  await screen.findByText('Распределений в выбранной компании пока нет.');
});

test('empty source search preserves selected option and distinguishes no matches from no lots', async () => {
  render(<DistributionWorkspace {...props} />);
  await fillBatch();
  global.fetch = jest.fn(async () => response({ items: [], nextCursor: null }));
  fireEvent.change(screen.getByLabelText('Поиск партий'), { target: { value: 'Неизвестный материал' } });
  fireEvent.click(screen.getByText('Найти партии'));
  await screen.findByText('По заданному поиску партий не найдено.');
  expect(screen.queryByText(/Нет доступных партий общего склада/)).not.toBeInTheDocument();
  expect(screen.getByLabelText('Партия 1')).toHaveValue('5');
  expect(screen.getByText('Распределить одним пакетом')).toBeEnabled();
  fireEvent.change(screen.getByLabelText('Поиск партий'), { target: { value: '' } });
  expect(screen.getByText('По заданному поиску партий не найдено.')).toBeInTheDocument();
  fireEvent.click(screen.getByText('Найти партии'));
  await screen.findByText(/Нет доступных партий общего склада/);
  expect(screen.queryByText('По заданному поиску партий не найдено.')).not.toBeInTheDocument();
});
test('late filter response cannot overwrite a newer server search', async () => {
  render(<DistributionWorkspace {...props} readOnly />);
  await screen.findByText(/Осталось по распределению: 15 м/);
  let resolveOld;
  global.fetch = jest.fn().mockImplementationOnce(() => new Promise(resolve => { resolveOld = resolve; }))
    .mockResolvedValueOnce(response({ items: [{ ...records[0], projectName: 'Новый' }], nextCursor: null }));
  fireEvent.change(screen.getByLabelText('Найти по объекту, материалу или накладной'), { target: { value: 'Старый' } });
  fireEvent.click(screen.getByText('Применить фильтры'));
  fireEvent.change(screen.getByLabelText('Найти по объекту, материалу или накладной'), { target: { value: 'Новый' } });
  fireEvent.click(screen.getByText('Применить фильтры'));
  await screen.findByText('Новый · Кабель');
  await act(async () => resolveOld(response({ items: [{ ...records[0], projectName: 'Старый' }], nextCursor: 8 })));
  expect(screen.queryByText('Старый · Кабель')).not.toBeInTheDocument();
  expect(screen.queryByText('Загрузить ещё распределения')).not.toBeInTheDocument();
});

test('late company responses cannot repopulate the new company', async () => {
  const resolvers = [];
  global.fetch = jest.fn(() => new Promise(resolve => resolvers.push(resolve)));
  const view = render(<DistributionWorkspace {...props} />);
  global.fetch = jest.fn(async () => response({ items: [], nextCursor: null }));
  view.rerender(<DistributionWorkspace {...props} companyContext={{ mode: 'company', selectedCompanyId: 3, companies: [{ companyId: 3, role: 'кладовщик' }] }} />);
  await screen.findByText(/Распределений в выбранной компании пока нет/);
  await act(async () => { resolvers[0](response({ items: records, nextCursor: 8 })); resolvers[1](response({ items: sources, nextCursor: 5 })); });
  expect(screen.queryByText(/Осталось по распределению: 15 м/)).not.toBeInTheDocument();
  expect(screen.getByLabelText('Партия 1').options).toHaveLength(1);
});

test('late source search cannot restore older results or lose the selected lot', async () => {
  render(<DistributionWorkspace {...props} />);
  await fillBatch();
  let resolveOld;
  global.fetch = jest.fn().mockImplementationOnce(() => new Promise(resolve => { resolveOld = resolve; }))
    .mockResolvedValueOnce(response({ items: [{ ...sources[0], lotId: 3, materialName: 'Новый' }], nextCursor: null }));
  fireEvent.change(screen.getByLabelText('Поиск партий'), { target: { value: 'Старый' } });
  fireEvent.click(screen.getByText('Найти партии'));
  fireEvent.change(screen.getByLabelText('Поиск партий'), { target: { value: 'Новый' } });
  fireEvent.click(screen.getByText('Найти партии'));
  await screen.findByRole('option', { name: /Новый/ });
  await act(async () => resolveOld(response({ items: [{ ...sources[0], lotId: 4, materialName: 'Старый' }], nextCursor: 4 })));
  expect(screen.queryByRole('option', { name: /Старый/ })).not.toBeInTheDocument();
  expect(screen.getByLabelText('Партия 1')).toHaveValue('5');
});

test.each(['кладовщик', 'снабженец'])('%s remains read only in accounting', async role => {
  render(<DistributionWorkspace {...props} readOnly companyContext={{ ...companyContext, companies: [{ companyId: 2, role }] }} />);
  await screen.findByText(/Осталось по распределению: 15 м/);
  expect(screen.queryByText('Распределить одним пакетом')).not.toBeInTheDocument();
  expect(screen.queryByText('Оформить возврат')).not.toBeInTheDocument();
  expect(global.fetch).toHaveBeenCalledTimes(1);
});

test('denial invalidates concurrent responses and clears selected sources', async () => {
  render(<DistributionWorkspace {...props} />);
  await fillBatch();
  let resolveSources;
  global.fetch = jest.fn(url => url.includes('/sources') ? new Promise(resolve => { resolveSources = resolve; })
    : Promise.resolve({ ok: false, status: 403, json: async () => ({ detail: 'Запрещено' }) }));
  fireEvent.click(screen.getByText('Обновить'));
  await screen.findByText('Запрещено');
  await act(async () => resolveSources(response({ items: sources, nextCursor: 5 })));
  expect(screen.getByLabelText('Партия 1').options).toHaveLength(1);
  expect(screen.queryByText('Загрузить ещё партии')).not.toBeInTheDocument();
  expect(screen.getByText('Распределить одним пакетом')).toBeDisabled();
});

test('legacy truncated lists never invent a continuation', async () => {
  global.fetch = jest.fn(async () => response({ items: records, truncated: true }));
  render(<DistributionWorkspace {...props} readOnly />);
  await screen.findByText(/без продолжения/);
  expect(screen.queryByText('Загрузить ещё распределения')).not.toBeInTheDocument();
});

test('source selection can reach beyond the first 200 lots', async () => {
  global.fetch = jest.fn(async url => response(url.includes('/sources')
    ? new URL(url, 'http://localhost').searchParams.has('beforeId')
      ? { items: [{ ...sources[0], lotId: 1 }], nextCursor: null }
      : { items: Array.from({ length: 200 }, (_, i) => ({ ...sources[0], lotId: 201 - i })), nextCursor: 2 }
    : { items: records, nextCursor: null }));
  render(<DistributionWorkspace {...props} />);
  await screen.findByText(/Осталось по распределению: 15 м/);
  fireEvent.click(screen.getByText('Загрузить ещё партии'));
  await waitFor(() => expect(screen.getByLabelText('Партия 1').options).toHaveLength(202));
  fireEvent.change(screen.getByLabelText('Партия 1'), { target: { value: '1' } });
  expect(screen.getByLabelText('Партия 1')).toHaveValue('1');
});

test('malformed next page clears history and closes an open return', async () => {
  global.fetch = jest.fn(async url => response(url.includes('/sources') ? { items: sources } : { items: records, nextCursor: 8 }));
  render(<DistributionWorkspace {...props} />);
  fireEvent.click(await screen.findByText('Оформить возврат'));
  global.fetch = jest.fn(async () => response({ items: records, nextCursor: 8 }));
  fireEvent.click(screen.getByText('Загрузить ещё распределения'));
  await screen.findByRole('alert');
  expect(screen.queryByText(/Осталось по распределению: 15 м/)).not.toBeInTheDocument();
  expect(screen.queryByLabelText('Количество возврата')).not.toBeInTheDocument();
});

test('access denial on refresh clears previous data and disables writes', async () => {
  render(<DistributionWorkspace {...props} />);
  await fillBatch();
  global.fetch = jest.fn(async () => ({ ok: false, status: 403, json: async () => ({ detail: 'Доступ отозван' }) }));
  fireEvent.click(screen.getByText('Обновить'));
  await screen.findByText('Доступ отозван');
  expect(screen.queryByText(/Осталось по распределению: 15 м/)).not.toBeInTheDocument();
  expect(screen.getByText('Распределить одним пакетом')).toBeDisabled();
});

describe('two-stage transfer integration', () => {
  const oldFlag = process.env.REACT_APP_WAREHOUSE_DISTRIBUTION_TRANSFERS_ENABLED;
  beforeEach(() => { process.env.REACT_APP_WAREHOUSE_DISTRIBUTION_TRANSFERS_ENABLED = 'true'; });
  afterEach(() => {
    if (oldFlag === undefined) delete process.env.REACT_APP_WAREHOUSE_DISTRIBUTION_TRANSFERS_ENABLED;
    else process.env.REACT_APP_WAREHOUSE_DISTRIBUTION_TRANSFERS_ENABLED = oldFlag;
  });
  test('dispatch action uses loaded allocation and displays quantity already dispatched', async () => {
    const read = global.fetch;
    global.fetch = jest.fn((url, options) => url.includes('/transfers') ? Promise.resolve(response({ items: [], nextCursor: null }))
      : url.includes('/sources') ? read(url, options) : Promise.resolve(response({ items: [{ ...records[0], transferredQuantity: '3', netQuantity: '12' }] })));
    render(<DistributionWorkspace {...props} projects={[...props.projects, { id: 13, companyId: 2, name: 'Сад' }]} />);
    fireEvent.click(await screen.findByText('Отправить на другой объект'));
    expect(screen.getByText(/Отправлено на другие объекты: 3 м/)).toBeInTheDocument();
    expect(screen.getByText(/выданное минус возвраты и отправки/)).toBeInTheDocument();
    expect(screen.getByText(/Распределение #8. Максимум: 12 м/)).toBeInTheDocument();
    expect(global.fetch).toHaveBeenCalledTimes(3);
    expect(screen.getByText('Оформить возврат')).toBeDisabled();
  });
  test('accounting gets transfer history without sending or receiving buttons', async () => {
    const read = global.fetch;
    global.fetch = jest.fn((url, options) => url.includes('/transfers') ? Promise.resolve(response({ items: [], nextCursor: null })) : read(url, options));
    render(<DistributionWorkspace {...props} readOnly />);
    await screen.findByText('Перемещений пока нет.');
    expect(screen.queryByText('Отправить на другой объект')).not.toBeInTheDocument();
    expect(screen.queryByText('Подтвердить отправку')).not.toBeInTheDocument();
    expect(global.fetch).toHaveBeenCalledTimes(2);
  });
  test('transfer denial clears allocation history and disables all warehouse commands', async () => {
    const read = global.fetch;
    let denyTransfer;
    global.fetch = jest.fn((url, options) => url.includes('/transfers') ? new Promise(resolve => { denyTransfer = resolve; }) : read(url, options));
    render(<DistributionWorkspace {...props} />);
    await fillBatch();
    await act(async () => denyTransfer({ ok: false, status: 403, json: async () => ({ detail: 'Нет доступа к перемещениям' }) }));
    expect(screen.queryByText(/Осталось по распределению: 15 м/)).not.toBeInTheDocument();
    expect(screen.getByText('Распределить одним пакетом')).toBeDisabled();
    expect(screen.getByRole('alert')).toHaveTextContent(/Доступ/);
  });
  test('pending transfer blocks ordinary allocation while its safe retry remains available', async () => {
    const read = global.fetch;
    global.fetch = jest.fn((url, options) => url.includes('/transfers')
      ? options?.method === 'POST' ? Promise.reject(new Error('Ответ потерян')) : Promise.resolve(response({ items: [], nextCursor: null })) : read(url, options));
    render(<DistributionWorkspace {...props} projects={[...props.projects, { id: 13, companyId: 2, name: 'Сад' }]} />);
    await fillBatch();
    fireEvent.click(screen.getByText('Отправить на другой объект'));
    fireEvent.change(screen.getByLabelText('Объект назначения'), { target: { value: '13' } });
    fireEvent.change(screen.getByLabelText('Количество отправки'), { target: { value: '2' } });
    fireEvent.change(screen.getByLabelText('Основание отправки'), { target: { value: 'Передача' } });
    fireEvent.click(screen.getByText('Подтвердить отправку'));
    await screen.findByText('Ответ потерян');
    expect(screen.getByText('Распределить одним пакетом')).toBeDisabled();
    expect(screen.getByText('Оформить возврат')).toBeDisabled();
    expect(screen.getByText('Повторить перемещение безопасно')).toBeEnabled();
  });
  test('pending ordinary allocation blocks new transfer actions', async () => {
    const read = global.fetch;
    global.fetch = jest.fn((url, options) => url.includes('/transfers') ? Promise.resolve(response({ items: [], nextCursor: null }))
      : options?.method === 'POST' ? Promise.reject(new Error('Ответ потерян')) : read(url, options));
    render(<DistributionWorkspace {...props} />);
    await fillBatch(); fireEvent.click(screen.getByText('Распределить одним пакетом'));
    await screen.findByRole('alert');
    expect(screen.getByText('Отправить на другой объект')).toBeDisabled();
  });
  test('confirmed transfer remains mounted while parent refreshes allocations', async () => {
    const item = { id: 30, companyId: 2, sourceAllocationId: 8, fromProjectId: 11, fromProjectName: 'Школа', toProjectId: 13, toProjectName: 'Сад', warehouseInvoiceId: 10, invoiceNumber: 'НК-10', lotId: 5, materialName: 'Кабель', unit: 'м', quantity: '2', receivedQuantity: '0', inTransitQuantity: '2', status: 'in_transit', receipts: [], reason: 'Передача' };
    let sent = false;
    global.fetch = jest.fn(async (url, options) => {
      if (options?.method === 'POST') { sent = true; return response({ ok: true, requestId: JSON.parse(options.body).requestId, item }); }
      if (url.includes('/transfers')) return response({ items: sent ? [item] : [], nextCursor: null });
      return response({ items: url.includes('/sources') ? sources : [{ ...records[0], netQuantity: sent ? '13' : '15', transferredQuantity: sent ? '2' : '0' }] });
    });
    render(<DistributionWorkspace {...props} projects={[...props.projects, { id: 13, companyId: 2, name: 'Сад' }]} />);
    fireEvent.click(await screen.findByText('Отправить на другой объект'));
    fireEvent.change(screen.getByLabelText('Объект назначения'), { target: { value: '13' } });
    fireEvent.change(screen.getByLabelText('Количество отправки'), { target: { value: '2' } });
    fireEvent.change(screen.getByLabelText('Основание отправки'), { target: { value: 'Передача' } });
    fireEvent.click(screen.getByText('Подтвердить отправку'));
    await screen.findByText('Осталось по распределению: 13 м');
    expect(screen.getByText(/Перемещение сохранено/)).toBeInTheDocument();
    expect(screen.getByText('В пути: 2 м')).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText('Оформить возврат')).toBeEnabled());
  });
});
