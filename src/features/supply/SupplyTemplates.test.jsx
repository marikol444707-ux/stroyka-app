import React, { useState } from 'react';
import { act, fireEvent, render, renderHook, screen, waitFor } from '@testing-library/react';
import { C } from '../../constants/uiTheme';
import { buildAppRenderContext } from '../app-shell/buildAppRenderContext';
import SupplyTemplates from './SupplyTemplates';
import { useSupplyWorkflowState } from './useSupplyWorkflowState';

const companyContext = { mode: 'company', selectedCompanyId: 2 };
const user = { id: 9, role: 'директор', name: 'Директор' };
const draft = {
  project: 'Школа', category: 'Черновая', notes: 'Не менять', urgency: 'срочная',
  items: [
    { materialName: 'Цемент', quantity: '10', unit: 'меш', workPackage: 'Стены' },
    { materialName: 'Песок', quantity: '2.5', unit: 'м³', workPackage: 'Чужой раздел' },
  ],
};
const template = { id: 7, name: 'Коробка', category: 'Общестрой', version: 3, items: draft.items };
const catalog = (items = [template], extra = {}) => ({ items, truncated: false, canCreate: true, canArchive: true, ...extra });
const response = (body, status = 200) => ({ ok: status < 400, status, json: async () => body });
const baseProps = {
  API: '/api', companyContext, user, C, draft, setDraft: jest.fn(), disabled: false,
  getProjectWorkPackageOptions: () => ['Стены', 'Кровля'],
};

beforeAll(() => Object.defineProperty(window, 'crypto', { configurable: true, value: require('crypto').webcrypto }));
beforeEach(() => {
  sessionStorage.clear();
  jest.clearAllMocks();
  process.env.REACT_APP_WORK_MATERIAL_ACCOUNTING_ENABLED = '1';
});
afterEach(() => { delete process.env.REACT_APP_WORK_MATERIAL_ACCOUNTING_ENABLED; });

function DraftHarness(props = {}) {
  const [value, setValue] = useState(props.draft || draft);
  return <>
    <SupplyTemplates {...baseProps} {...props} draft={value} setDraft={setValue} />
    <output data-testid="draft">{JSON.stringify(value)}</output>
  </>;
}

test('catalogue is selected-company scoped and changing company and user removes private template state', async () => {
  const headers = [];
  global.fetch = jest.fn(async (url, options = {}) => {
    headers.push([new Headers(options.headers).get('X-Company-Id'), url]);
    const companyId = new Headers(options.headers).get('X-Company-Id');
    return response(catalog([{ ...template, id: Number(companyId), name: `Склад ${companyId}` }]));
  });
  const view = render(<SupplyTemplates {...baseProps} />);
  expect(await screen.findAllByRole('option', { name: /Склад 2/ })).toHaveLength(2);
  fireEvent.click(screen.getByRole('button', { name: 'Сохранить как шаблон' }));
  fireEvent.change(screen.getByLabelText('Название шаблона'), { target: { value: 'Частный черновик' } });

  view.rerender(<SupplyTemplates {...baseProps} companyContext={{ mode: 'company', selectedCompanyId: 3 }} user={{ ...user, id: 10 }} />);

  expect(await screen.findAllByRole('option', { name: /Склад 3/ })).toHaveLength(2);
  expect(screen.queryAllByRole('option', { name: /Склад 2/ })).toHaveLength(0);
  expect(screen.queryByDisplayValue('Частный черновик')).not.toBeInTheDocument();
  expect(headers).toEqual(expect.arrayContaining([['2', '/api/supply-request-templates/catalog'], ['3', '/api/supply-request-templates/catalog']]));
});

test('all-company mode exposes no catalogue and performs no request', () => {
  global.fetch = jest.fn();
  render(<SupplyTemplates {...baseProps} companyContext={{ mode: 'all_companies' }} />);
  expect(screen.getByText(/Выберите компанию/)).toBeInTheDocument();
  expect(global.fetch).not.toHaveBeenCalled();
});

test('request workflow clears its open private draft when the user or company scope changes', () => {
  const { result, rerender } = renderHook(({ scope }) => useSupplyWorkflowState(scope), {
    initialProps: { scope: '9:company:2' },
  });
  act(() => {
    result.current.setNewSupplyReq({ ...draft, notes: 'Частный черновик' });
    result.current.setShowSupplyForm(true);
  });
  expect(result.current.showSupplyForm).toBe(true);
  expect(result.current.newSupplyReq.notes).toBe('Частный черновик');

  rerender({ scope: '10:company:3' });

  expect(result.current.showSupplyForm).toBe(false);
  expect(result.current.newSupplyReq.notes).toBe('');
  expect(result.current.newSupplyReq.project).toBe('');
});

test('saving validates every row without dropping it and pins company and actor instead of client authors', async () => {
  const posts = [];
  global.fetch = jest.fn(async (url, options = {}) => {
    if (options.method === 'POST') { posts.push(JSON.parse(options.body)); return response({ ok: true, id: 8, eventId: 12 }); }
    return response(catalog());
  });
  const invalidDraft = { ...draft, items: [draft.items[0], { materialName: '', quantity: '', unit: '', workPackage: '' }] };
  const view = render(<SupplyTemplates {...baseProps} draft={invalidDraft} />);
  fireEvent.click(await screen.findByRole('button', { name: 'Сохранить как шаблон' }));
  fireEvent.change(screen.getByLabelText('Название шаблона'), { target: { value: 'Полный набор' } });
  fireEvent.click(screen.getByRole('button', { name: 'Сохранить набор' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('строке 2');
  expect(posts).toHaveLength(0);

  view.rerender(<SupplyTemplates {...baseProps} />);
  fireEvent.click(screen.getByRole('button', { name: 'Сохранить набор' }));
  await waitFor(() => expect(posts).toHaveLength(1));
  expect(posts[0]).toMatchObject({
    name: 'Полный набор', category: 'Черновая', expectedCompanyId: 2, expectedActorId: 9,
    items: draft.items,
  });
  expect(posts[0].items).toHaveLength(2);
  expect(posts[0]).not.toHaveProperty('createdBy');
  expect(posts[0]).not.toHaveProperty('owner');
});

test('lost create response keeps the form and recovery sends the exact UUID and payload once more', async () => {
  const posts = [];
  let lost = true;
  global.fetch = jest.fn(async (url, options = {}) => {
    if (options.method === 'POST') {
      posts.push(JSON.parse(options.body));
      if (lost) { lost = false; throw new Error('Failed to fetch'); }
      return response({ ok: true, id: 8, eventId: 12 });
    }
    return response(catalog());
  });
  render(<SupplyTemplates {...baseProps} />);
  fireEvent.click(await screen.findByRole('button', { name: 'Сохранить как шаблон' }));
  fireEvent.change(screen.getByLabelText('Название шаблона'), { target: { value: 'Повторяемый набор' } });
  fireEvent.click(screen.getByRole('button', { name: 'Сохранить набор' }));

  expect(await screen.findByRole('alert')).toHaveTextContent('Связь прервалась');
  expect(screen.getByLabelText('Название шаблона')).toHaveValue('Повторяемый набор');
  fireEvent.click(screen.getByRole('button', { name: 'Повторить сохранённую отправку' }));

  await waitFor(() => expect(posts).toHaveLength(2));
  expect(posts[1]).toEqual(posts[0]);
  expect(posts[0]).toMatchObject({ expectedCompanyId: 2, expectedActorId: 9, name: 'Повторяемый набор' });
  await waitFor(() => expect(screen.queryByLabelText('Название шаблона')).not.toBeInTheDocument());
});

test('pending save disables the template controls and prevents a duplicate command', async () => {
  let resolvePost;
  const pending = new Promise(resolve => { resolvePost = resolve; });
  let posts = 0;
  global.fetch = jest.fn(async (url, options = {}) => {
    if (options.method === 'POST') { posts += 1; return pending; }
    return response(catalog());
  });
  render(<SupplyTemplates {...baseProps} />);
  fireEvent.click(await screen.findByRole('button', { name: 'Сохранить как шаблон' }));
  fireEvent.change(screen.getByLabelText('Название шаблона'), { target: { value: 'Ожидающий набор' } });
  const save = screen.getByRole('button', { name: 'Сохранить набор' });
  fireEvent.click(save);
  fireEvent.click(save);
  expect(posts).toBe(1);
  expect(screen.getByLabelText('Название шаблона')).toBeDisabled();
  expect(screen.getByRole('button', { name: 'Сохранение…' })).toBeDisabled();

  await act(async () => resolvePost(response({ ok: true, id: 8, eventId: 12 })));
  await waitFor(() => expect(screen.queryByLabelText('Название шаблона')).not.toBeInTheDocument());
});

test('applying a template keeps the current request context and maps sections only for its current project', async () => {
  global.fetch = jest.fn(async () => response(catalog()));
  render(<DraftHarness />);
  fireEvent.change(await screen.findByLabelText('Готовый набор'), { target: { value: '7' } });
  const applied = JSON.parse(screen.getByTestId('draft').textContent);

  expect(applied).toMatchObject({ project: 'Школа', notes: 'Не менять', urgency: 'срочная', category: 'Общестрой' });
  expect(applied.items).toEqual([
    { materialName: 'Цемент', quantity: '10', unit: 'меш', workPackage: 'Стены' },
    { materialName: 'Песок', quantity: '2.5', unit: 'м³', workPackage: '' },
  ]);
});

test('archive requires an explicit confirmation and preserves it with a helpful server error', async () => {
  const posts = [];
  global.fetch = jest.fn(async (url, options = {}) => {
    if (options.method === 'POST') { posts.push([url, JSON.parse(options.body)]); return response({ detail: 'Шаблон уже изменён. Обновите список.' }, 409); }
    return response(catalog());
  });
  render(<SupplyTemplates {...baseProps} />);
  fireEvent.change(await screen.findByLabelText('Архивировать шаблон'), { target: { value: '7' } });
  expect(screen.getByText(/Перенести «Коробка» в архив/)).toBeInTheDocument();
  expect(posts).toHaveLength(0);
  fireEvent.click(screen.getByRole('button', { name: 'Перенести в архив' }));

  expect(await screen.findByRole('alert')).toHaveTextContent('Шаблон уже изменён');
  expect(screen.getByText(/Перенести «Коробка» в архив/)).toBeInTheDocument();
  expect(posts[0]).toEqual(['/api/supply-request-templates/7/archive', expect.objectContaining({
    expectedVersion: 3, expectedCompanyId: 2, expectedActorId: 9,
  })]);
});

test.each(['мастер', 'субподрядчик', 'бригадир'])('early %s route forwards the real project section getter to its cabinet', role => {
  const getProjectWorkPackageOptions = jest.fn(() => ['Стены']);
  const { earlyRoleRoute } = buildAppRenderContext({
    actionGroups: {
      documentActions: {}, personnelActions: {}, pricelistActions: {}, projectCrudActions: {},
      projectOperationActions: {}, supplyActions: {}, supplyPlanningUi: {}, userAccessActions: {},
      warehouseActions: {}, workJournalActions: {},
    },
    appBusinessRuntime: { getProjectWorkPackageOptions },
    appCoreRuntime: { myNotifications: () => [] },
    companyContext,
    user: { ...user, role },
  });
  expect(earlyRoleRoute.props.actions.getProjectWorkPackageOptions).toBe(getProjectWorkPackageOptions);
  const cabinetRoute = earlyRoleRoute.type(earlyRoleRoute.props);
  expect(cabinetRoute.props.children.props.getProjectWorkPackageOptions).toBe(getProjectWorkPackageOptions);
});
