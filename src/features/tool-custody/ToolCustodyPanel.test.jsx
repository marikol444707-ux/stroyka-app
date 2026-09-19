import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import ToolCustodyPanel from './ToolCustodyPanel';

const managerContext = { mode: 'company', selectedCompanyId: 2 };
const manager = { id: 9, role: 'директор', name: 'Директор' };
const colors = { card: '#fff', bg: '#fff', text: '#111', border: '#ddd', warning: '#a60', danger: '#c00' };

const baseTool = {
  id: 5,
  companyId: 2,
  name: 'Перфоратор',
  inventoryNumber: 'INV-005',
  status: 'На складе',
  location: 'Основной склад',
  project: '',
  projectId: null,
  masterId: null,
  masterName: '',
  contractId: null,
  version: 0,
};

const choices = {
  projects: [
    { id: 11, name: 'Одинаковый объект' },
    { id: 12, name: 'Одинаковый объект' },
  ],
  recipients: [
    { id: 21, name: 'Иван Иванов', projectIds: [11] },
    { id: 22, name: 'Иван Иванов', projectIds: [12] },
  ],
  contracts: [
    { id: 31, projectId: 11, recipientId: 21, name: 'Договор ответственности' },
    { id: 32, projectId: 12, recipientId: 22, name: 'Договор ответственности' },
  ],
};

const custodyView = (overrides = {}) => ({
  tool: baseTool,
  expectedState: 'tool-state-1',
  canManage: true,
  canDecide: true,
  canDispute: true,
  choices,
  history: [],
  incidents: [],
  ...overrides,
});

const panelProps = (overrides = {}) => ({
  tool: { id: 5 },
  API: '/api',
  companyContext: managerContext,
  user: manager,
  C: colors,
  onClose: jest.fn(),
  onChanged: jest.fn(),
  ...overrides,
});

function response(body, status = 200) {
  return { ok: status >= 200 && status < 300, status, json: async () => body };
}

beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function showModal() { this.setAttribute('open', ''); };
  Object.defineProperty(window, 'crypto', { configurable: true, value: require('crypto').webcrypto });
});

beforeEach(() => {
  process.env.REACT_APP_TOOL_CUSTODY_ENABLED = 'true';
  process.env.REACT_APP_WORK_MATERIAL_ACCOUNTING_ENABLED = '1';
  sessionStorage.clear();
  jest.clearAllMocks();
});

afterEach(() => {
  delete process.env.REACT_APP_TOOL_CUSTODY_ENABLED;
  delete process.env.REACT_APP_WORK_MATERIAL_ACCOUNTING_ENABLED;
});

test('issue submits project, recipient and contract IDs even when their names are duplicated', async () => {
  const posts = [];
  global.fetch = jest.fn(async (url, options = {}) => {
    if (options.method === 'POST') {
      posts.push({ url, payload: JSON.parse(options.body) });
      return response({ ok: true, toolId: 5, eventId: 101, incidentId: null });
    }
    return response(custodyView());
  });

  render(<ToolCustodyPanel {...panelProps()} />);
  fireEvent.change(await screen.findByLabelText('Объект'), { target: { value: '11' } });
  fireEvent.change(screen.getByLabelText('Получатель'), { target: { value: '21' } });
  fireEvent.change(screen.getByLabelText('Договор ответственности'), { target: { value: '31' } });
  fireEvent.click(screen.getByRole('button', { name: 'Выдать инструмент' }));

  await waitFor(() => expect(posts).toHaveLength(1));
  expect(posts[0].url).toBe('/api/tools/5/custody');
  expect(posts[0].payload).toMatchObject({
    action: 'issue',
    expectedState: 'tool-state-1',
    projectId: 11,
    recipientId: 21,
    contractId: 31,
    expectedCompanyId: 2,
    expectedActorId: 9,
  });
  expect(posts[0].payload).not.toHaveProperty('project');
  expect(posts[0].payload).not.toHaveProperty('recipientName');
  expect(posts[0].payload.requestId).toMatch(/^[0-9a-f-]{36}$/i);
});

test('lost return posts the displayed state, condition and mandatory reason', async () => {
  const posts = [];
  const issued = custodyView({
    tool: { ...baseTool, status: 'У мастера', location: 'У мастера', project: 'Объект 11', projectId: 11,
      masterId: 21, masterName: 'Иван Иванов', contractId: 31, version: 1 },
    expectedState: 'tool-state-issued',
  });
  global.fetch = jest.fn(async (url, options = {}) => {
    if (options.method === 'POST') {
      posts.push({ url, payload: JSON.parse(options.body) });
      return response({ ok: true, toolId: 5, eventId: 102, incidentId: 81 });
    }
    return response(issued);
  });

  render(<ToolCustodyPanel {...panelProps()} />);
  fireEvent.change(await screen.findByLabelText('Состояние при возврате'), { target: { value: 'lost' } });
  expect(screen.getByRole('button', { name: 'Оформить возврат' })).toBeDisabled();
  fireEvent.change(screen.getByLabelText('Причина / примечание'), { target: { value: 'Утерян при перевозке' } });
  fireEvent.click(screen.getByRole('button', { name: 'Оформить возврат' }));

  await waitFor(() => expect(posts).toHaveLength(1));
  expect(posts[0]).toMatchObject({ url: '/api/tools/5/custody', payload: {
    action: 'return', condition: 'lost', reason: 'Утерян при перевозке', expectedState: 'tool-state-issued',
  } });
});

test('network failure preserves the return form and retry sends the exact same UUID and payload', async () => {
  const posts = [];
  let dropped = false;
  let current = custodyView({
    tool: { ...baseTool, status: 'У мастера', location: 'У мастера', project: 'Объект 11', projectId: 11,
      masterId: 21, masterName: 'Иван Иванов', contractId: 31, version: 1 },
    expectedState: 'tool-state-issued',
  });
  global.fetch = jest.fn(async (url, options = {}) => {
    if (options.method === 'POST') {
      posts.push({ url, payload: JSON.parse(options.body) });
      current = custodyView({ tool: { ...baseTool, status: 'Утерян', location: 'Утерян', version: 2 },
        expectedState: 'tool-state-lost' });
      if (!dropped) { dropped = true; throw new Error('Failed to fetch'); }
      return response({ ok: true, toolId: 5, eventId: 102, incidentId: 81 });
    }
    return response(current);
  });

  render(<ToolCustodyPanel {...panelProps()} />);
  fireEvent.change(await screen.findByLabelText('Состояние при возврате'), { target: { value: 'lost' } });
  fireEvent.change(screen.getByLabelText('Причина / примечание'), { target: { value: 'Не найден на объекте' } });
  fireEvent.click(screen.getByRole('button', { name: 'Оформить возврат' }));

  await screen.findByText(/Связь прервалась/);
  expect(screen.getByLabelText('Состояние при возврате')).toHaveValue('lost');
  expect(screen.getByLabelText('Причина / примечание')).toHaveValue('Не найден на объекте');
  fireEvent.click(screen.getByRole('button', { name: 'Повторить сохранённую отправку' }));

  await waitFor(() => expect(posts).toHaveLength(2));
  expect(posts[1]).toEqual(posts[0]);
  await waitFor(() => expect(screen.queryByText('Есть сохранённая отправка')).not.toBeInTheDocument());
});

test('changing actor role or company remounts the form and clears draft selections', async () => {
  global.fetch = jest.fn(async () => response(custodyView()));
  const props = panelProps();
  const rendered = render(<ToolCustodyPanel {...props} />);

  fireEvent.change(await screen.findByLabelText('Объект'), { target: { value: '11' } });
  fireEvent.change(screen.getByLabelText('Получатель'), { target: { value: '21' } });
  expect(screen.getByLabelText('Получатель')).toHaveValue('21');

  rendered.rerender(<ToolCustodyPanel {...props} user={{ ...manager, role: 'зам_директора' }} />);
  await waitFor(() => expect(screen.getByLabelText('Объект')).toHaveValue(''));
  fireEvent.change(screen.getByLabelText('Объект'), { target: { value: '11' } });
  expect(screen.getByLabelText('Объект')).toHaveValue('11');

  rendered.rerender(<ToolCustodyPanel {...props} companyContext={{ mode: 'company', selectedCompanyId: 3 }} />);
  await waitFor(() => expect(screen.getByLabelText('Объект')).toHaveValue(''));
});

test('director reconciliation requires a reason and exact holder IDs before preserving a legacy held record', async () => {
  const posts = [];
  const legacy = custodyView({
    tool: { ...baseTool, status: 'На объекте', location: 'Прежнее место хранения',
      project: 'Прежний объект', masterId: null, masterName: 'Иван Иванов', version: 0 },
    expectedState: 'legacy-tool-state',
    needsReconciliation: true,
  });
  global.fetch = jest.fn(async (url, options = {}) => {
    if (options.method === 'POST') {
      posts.push({ url, payload: JSON.parse(options.body) });
      return response({ ok: true, toolId: 5, eventId: 103, incidentId: null });
    }
    return response(legacy);
  });

  render(<ToolCustodyPanel {...panelProps()} />);
  fireEvent.change(await screen.findByLabelText('Фактическое местонахождение'), { target: { value: 'У мастера' } });
  const reconcile = screen.getByRole('button', { name: 'Уточнить прежнюю запись' });
  expect(reconcile).toBeDisabled();
  fireEvent.change(screen.getByLabelText('Причина / примечание'), { target: { value: 'Проверено по акту передачи' } });
  expect(reconcile).toBeDisabled();
  fireEvent.change(screen.getByLabelText('Объект'), { target: { value: '12' } });
  fireEvent.change(screen.getByLabelText('Получатель'), { target: { value: '22' } });
  fireEvent.change(screen.getByLabelText('Договор ответственности'), { target: { value: '32' } });
  expect(reconcile).toBeEnabled();
  fireEvent.click(reconcile);

  await waitFor(() => expect(posts).toHaveLength(1));
  expect(posts[0]).toMatchObject({ url: '/api/tools/5/custody', payload: {
    action: 'reconcile', expectedState: 'legacy-tool-state', reconciledStatus: 'У мастера',
    projectId: 12, recipientId: 22, contractId: 32, reason: 'Проверено по акту передачи',
    expectedCompanyId: 2, expectedActorId: 9,
  } });
});

test('director confirms responsibility with all monetary evidence and the current decision identity', async () => {
  const posts = [];
  const incident = { id: 81, kind: 'lost', reason: 'Утерян при перевозке', holderId: 21,
    holderName: 'Иван Иванов', contractId: 31, status: 'pending', amount: '0', allocatedAmount: '0',
    decisionId: null, decisions: [] };
  global.fetch = jest.fn(async (url, options = {}) => {
    if (options.method === 'POST') {
      posts.push({ url, payload: JSON.parse(options.body) });
      return response({ ok: true, ...incident, status: 'confirmed', amount: '12500' });
    }
    return response(custodyView({ incidents: [incident] }));
  });

  render(<ToolCustodyPanel {...panelProps()} />);
  fireEvent.change(await screen.findByLabelText('Сумма возмещения, ₽'), { target: { value: '12500' } });
  fireEvent.change(screen.getByLabelText('Документ о стоимости'), { target: { value: 'Счёт поставщика №7' } });
  fireEvent.change(screen.getByLabelText('Договорное основание'), { target: { value: 'Пункт 4.2 договора' } });
  fireEvent.change(screen.getByLabelText('Причина решения'), { target: { value: 'Подтверждено комиссией' } });
  fireEvent.click(screen.getByRole('button', { name: 'Подтвердить штраф' }));

  await waitFor(() => expect(posts).toHaveLength(1));
  expect(posts[0]).toMatchObject({ url: '/api/tools/5/incidents/81/decisions', payload: {
    decision: 'confirmed', amount: '12500', priceEvidence: 'Счёт поставщика №7',
    contractEvidence: 'Пункт 4.2 договора', reason: 'Подтверждено комиссией', expectedDecisionId: null,
  } });
});

test('a prior holder can read and dispute their incident but receives no custody controls', async () => {
  const posts = [];
  const incident = { id: 81, kind: 'lost', reason: 'Утерян при перевозке', holderId: 21,
    holderName: 'Иван Иванов', contractId: 31, status: 'pending', amount: '0', allocatedAmount: '0',
    decisionId: null, decisions: [] };
  const formerHolderView = custodyView({
    tool: { id: 5, companyId: 2, name: 'Перфоратор', inventoryNumber: 'INV-005' },
    canManage: false,
    canDecide: false,
    canDispute: true,
    choices: {},
    incidents: [incident],
  });
  global.fetch = jest.fn(async (url, options = {}) => {
    if (options.method === 'POST') {
      posts.push({ url, payload: JSON.parse(options.body) });
      return response({ ok: true, ...incident, status: 'disputed' });
    }
    return response(formerHolderView);
  });

  render(<ToolCustodyPanel {...panelProps({ user: { id: 21, role: 'мастер', name: 'Иван Иванов' } })} />);
  expect(await screen.findByText('Утерян при перевозке')).toBeInTheDocument();
  expect(screen.queryByLabelText('Объект')).not.toBeInTheDocument();
  expect(screen.queryByLabelText('Состояние при возврате')).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Выдать инструмент' })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Оформить возврат' })).not.toBeInTheDocument();

  fireEvent.change(screen.getByLabelText('Причина решения'), { target: { value: 'Не согласен с обстоятельствами' } });
  fireEvent.click(screen.getByRole('button', { name: 'Оспорить' }));
  await waitFor(() => expect(posts).toHaveLength(1));
  expect(posts[0]).toMatchObject({ url: '/api/tools/5/incidents/81/decisions', payload: {
    decision: 'disputed', reason: 'Не согласен с обстоятельствами', expectedDecisionId: null,
  } });
});
