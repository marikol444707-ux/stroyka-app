import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import InventoryWorkspace from './InventoryWorkspace';

const companyContext = { mode: 'company', selectedCompanyId: 2 };
const user = { id: 9, role: 'кладовщик', name: 'Кладовщик' };
const C = { card: '#fff', bg: '#f8fafc', text: '#111', textSec: '#555', border: '#ddd', warning: '#a60', danger: '#c00' };

const listView = (overrides = {}) => ({
  items: [{ id: 41, project: 'Лицей', date: '2026-09-19', status: 'Черновик' }],
  projects: [{ id: 11, name: 'Лицей' }],
  canCreate: true,
  ...overrides,
});

const detailView = (overrides = {}) => ({
  inventory: { id: 41, project: 'Лицей', date: '2026-09-19', status: 'Черновик', notes: 'Плановая сверка' },
  rows: [
    { key: 'material:101', kind: 'material', name: 'Цемент М500', unit: 'кг', expected: '12.5',
      actual: '9.25', reason: 'Повреждён мешок', condition: null, lots: [], untrackedQuantity: '0' },
    { key: 'material:102', kind: 'material', name: 'Шпаклёвка', unit: 'кг', expected: '0',
      actual: null, reason: '', condition: null, lots: [], untrackedQuantity: '0' },
  ],
  expectedState: 'inventory-state-1',
  canCount: true,
  canDecide: false,
  history: [],
  ...overrides,
});

const props = (overrides = {}) => ({
  API: '/api', companyContext, user, C, onChanged: jest.fn(), ...overrides,
});

const response = (body, status = 200) => ({
  ok: status >= 200 && status < 300,
  status,
  json: async () => body,
});

const companyHeader = options => {
  const headers = new Headers(options?.headers || {});
  return headers.get('X-Company-Id');
};

beforeAll(() => {
  Object.defineProperty(window, 'crypto', { configurable: true, value: require('crypto').webcrypto });
});

beforeEach(() => {
  process.env.REACT_APP_INVENTORY_RECONCILIATION_ENABLED = '1';
  process.env.REACT_APP_WORK_MATERIAL_ACCOUNTING_ENABLED = '1';
  sessionStorage.clear();
  jest.clearAllMocks();
});

afterEach(() => {
  delete process.env.REACT_APP_INVENTORY_RECONCILIATION_ENABLED;
  delete process.env.REACT_APP_WORK_MATERIAL_ACCOUNTING_ENABLED;
});

async function openInventory() {
  fireEvent.click(await screen.findByRole('button', { name: 'Открыть' }));
  return screen.findByLabelText('Факт: Цемент М500');
}

test('opening a saved reconciliation restores its actual values and keeps blank distinct from zero', async () => {
  global.fetch = jest.fn(async url => response(
    url.endsWith('/inventory/41/reconciliation') ? detailView() : listView(),
  ));

  render(<InventoryWorkspace {...props()} />);
  expect(await openInventory()).toHaveValue(9.25);
  expect(screen.getByLabelText('Причина: Цемент М500')).toHaveValue('Повреждён мешок');
  expect(screen.getByLabelText('Факт: Шпаклёвка')).toHaveValue(null);
  expect(screen.getByText(/По учёту:\s*12[.,]5\s*кг/)).toBeInTheDocument();
});

test('save reads the controlled draft on click without blur and sends only row identity, fact and reason', async () => {
  const posts = [];
  global.fetch = jest.fn(async (url, options = {}) => {
    if (options.method === 'POST') {
      posts.push({ url, payload: JSON.parse(options.body) });
      return response({ ok: true, inventoryId: 41, eventId: 71 });
    }
    return response(url.endsWith('/inventory/41/reconciliation') ? detailView() : listView());
  });

  render(<InventoryWorkspace {...props()} />);
  const actual = await openInventory();
  fireEvent.change(actual, { target: { value: '0' } });
  fireEvent.change(screen.getByLabelText('Причина: Цемент М500'), { target: { value: 'Пересчитано дважды' } });
  fireEvent.click(screen.getByRole('button', { name: 'Сохранить пересчёт' }));

  await waitFor(() => expect(posts).toHaveLength(1));
  expect(posts[0].url).toBe('/api/inventory/41/reconciliation');
  expect(posts[0].payload).toMatchObject({ action: 'save', expectedState: 'inventory-state-1' });
  expect(posts[0].payload.requestId).toMatch(/^[0-9a-f-]{36}$/i);
  expect(posts[0].payload.counts).toEqual([
    { key: 'material:101', actual: '0', reason: 'Пересчитано дважды' },
    { key: 'material:102', actual: null, reason: '' },
  ]);
  for (const count of posts[0].payload.counts) {
    expect(Object.keys(count).sort()).toEqual(['actual', 'key', 'reason']);
    expect(count).not.toHaveProperty('expected');
    expect(count).not.toHaveProperty('difference');
    expect(count).not.toHaveProperty('name');
    expect(count).not.toHaveProperty('unit');
  }
});

test('a failed save leaves the reconciliation open with the unsaved draft intact', async () => {
  global.fetch = jest.fn(async (url, options = {}) => {
    if (options.method === 'POST') return response({ detail: 'Сеть недоступна' }, 503);
    return response(url.endsWith('/inventory/41/reconciliation') ? detailView() : listView());
  });

  render(<InventoryWorkspace {...props()} />);
  const actual = await openInventory();
  fireEvent.change(actual, { target: { value: '4.5' } });
  fireEvent.click(screen.getByRole('button', { name: 'Сохранить пересчёт' }));

  expect(await screen.findByRole('alert')).toHaveTextContent('Сеть недоступна');
  expect(screen.getByLabelText('Факт: Цемент М500')).toHaveValue(4.5);
  expect(screen.getByRole('button', { name: 'Сохранить пересчёт' })).toBeInTheDocument();
});

test('a lost save response keeps the draft and recovery retries the identical UUID and payload', async () => {
  const posts = [];
  let dropped = false;
  global.fetch = jest.fn(async (url, options = {}) => {
    if (options.method === 'POST') {
      posts.push({ url, payload: JSON.parse(options.body) });
      if (!dropped) { dropped = true; throw new Error('Failed to fetch'); }
      return response({ ok: true, inventoryId: 41, eventId: 71 });
    }
    return response(url.endsWith('/inventory/41/reconciliation') ? detailView() : listView());
  });

  render(<InventoryWorkspace {...props()} />);
  const actual = await openInventory();
  fireEvent.change(actual, { target: { value: '4.5' } });
  fireEvent.change(screen.getByLabelText('Причина: Цемент М500'), { target: { value: 'Повторный пересчёт' } });
  fireEvent.click(screen.getByRole('button', { name: 'Сохранить пересчёт' }));

  await screen.findByText(/Связь прервалась/);
  expect(screen.getByLabelText('Факт: Цемент М500')).toHaveValue(4.5);
  fireEvent.click(screen.getByRole('button', { name: 'Повторить сохранённую отправку' }));
  await waitFor(() => expect(posts).toHaveLength(2));
  expect(posts[1]).toEqual(posts[0]);
  await waitFor(() => expect(screen.queryByText(/Связь прервалась/)).not.toBeInTheDocument());
});

test('print uses only the saved view and remains blocked while a controlled draft is dirty', async () => {
  const showPreview = jest.fn();
  global.fetch = jest.fn(async url => response(
    url.endsWith('/inventory/41/reconciliation') ? detailView() : listView(),
  ));
  render(<InventoryWorkspace {...props({ showPreview })} />);
  const actual = await openInventory();
  const print = screen.getByRole('button', { name: 'Печатная ведомость' });
  fireEvent.click(print);
  expect(showPreview).toHaveBeenCalledTimes(1);
  expect(showPreview.mock.calls[0][0]).toContain('9.25');

  fireEvent.change(actual, { target: { value: '999' } });
  expect(print).toBeDisabled();
  fireEvent.click(print);
  expect(showPreview).toHaveBeenCalledTimes(1);
  expect(showPreview.mock.calls[0][0]).not.toContain('999');
});

test('director approval sends an exact main-stock lot allocation and renders decision history', async () => {
  const posts = [];
  const submitted = detailView({
    inventory: { id: 41, project: 'Основной склад', date: '2026-09-19', status: 'На проверке',
      state: 'submitted', notes: '' },
    rows: [{ key: 'material:101', kind: 'material', name: 'Цемент М500', unit: 'кг',
      expected: '5', actual: '2', difference: '-3', reason: 'Недостача', stockTable: 'warehouse_main',
      lots: [{ lotId: 501, invoiceId: 77, quantity: '2' }], untrackedQuantity: '1' }],
    expectedState: 'inventory-submitted-state', canCount: false, canDecide: true,
    history: [{ id: 72, action: 'submit', actorName: 'Кладовщик', createdAt: '2026-09-19T10:00:00Z', reason: '' }],
  });
  global.fetch = jest.fn(async (url, options = {}) => {
    if (options.method === 'POST') {
      posts.push({ url, payload: JSON.parse(options.body) });
      return response({ ok: true, inventoryId: 41, eventId: 73 });
    }
    return response(url.endsWith('/inventory/41/reconciliation') ? submitted : listView());
  });

  render(<InventoryWorkspace {...props({ user: { id: 8, role: 'директор', name: 'Директор' } })} />);
  await openInventory();
  expect(screen.getByText('Передано на проверку')).toBeInTheDocument();
  expect(screen.getByText(/Кладовщик/)).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText(/Без привязки к партии/), { target: { value: '1' } });
  fireEvent.change(screen.getByLabelText(/Партия №501/), { target: { value: '2' } });
  fireEvent.change(screen.getByLabelText('Основание решения'), { target: { value: 'Подтверждено комиссией' } });
  fireEvent.click(screen.getByRole('button', { name: 'Утвердить и скорректировать остатки' }));

  await waitFor(() => expect(posts).toHaveLength(1));
  expect(posts[0]).toMatchObject({ url: '/api/inventory/41/reconciliation', payload: {
    action: 'approve', expectedState: 'inventory-submitted-state', reason: 'Подтверждено комиссией',
    lotDeductions: [{ key: 'material:101', untrackedQuantity: '1', lots: [{ lotId: 501, quantity: '2' }] }],
  } });
});

test('a successful detail reload clears the previous read error', async () => {
  let detailReads = 0;
  global.fetch = jest.fn(async url => {
    if (url.endsWith('/inventory/41/reconciliation')) {
      detailReads += 1;
      return detailReads === 1 ? response({ detail: 'Временно недоступно' }, 503) : response(detailView());
    }
    return response(listView());
  });

  render(<InventoryWorkspace {...props()} />);
  fireEvent.click(await screen.findByRole('button', { name: 'Открыть' }));
  fireEvent.click(await screen.findByRole('button', { name: 'Обновить ведомость' }));
  expect(await screen.findByLabelText('Факт: Цемент М500')).toHaveValue(9.25);
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
});

test('changing company clears the open reconciliation and loads only the new company list', async () => {
  const requests = [];
  global.fetch = jest.fn(async (url, options = {}) => {
    const companyId = companyHeader(options);
    requests.push({ url, companyId });
    if (url.endsWith('/inventory/41/reconciliation')) return response(detailView());
    if (companyId === '3') return response(listView({
      items: [{ id: 91, project: 'Школа', date: '2026-09-20', status: 'Черновик' }],
      projects: [{ id: 19, name: 'Школа' }],
    }));
    return response(listView());
  });
  const baseProps = props();
  const rendered = render(<InventoryWorkspace {...baseProps} />);
  const actual = await openInventory();
  fireEvent.change(actual, { target: { value: '8' } });

  rendered.rerender(<InventoryWorkspace {...baseProps} companyContext={{ mode: 'company', selectedCompanyId: 3 }} />);

  expect(await screen.findByText('Школа')).toBeInTheDocument();
  expect(screen.queryByLabelText('Факт: Цемент М500')).not.toBeInTheDocument();
  expect(screen.queryByText('Лицей')).not.toBeInTheDocument();
  expect(requests).toContainEqual({ url: '/api/inventory/reconciliation', companyId: '3' });
});
