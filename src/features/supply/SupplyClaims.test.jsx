import React from 'react';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { C } from '../../constants/uiTheme';
import SupplyClaims from './SupplyClaims';

const companyContext = { mode: 'company', selectedCompanyId: 2 };
const user = { id: 9, role: 'директор', name: 'Директор' };
const claim = {
  id: 7, companyId: 2, deliveryId: 31, materialName: 'Цемент М500', claimType: 'Качество',
  description: 'Повреждена упаковка', project: 'Школа', workPackage: 'Стены',
  supplierName: 'ООО Поставка', status: 'Открыта', version: 3,
};
const history = [{
  id: 81, action: 'comment', text: 'Проверили партию', actorName: 'Кладовщик',
  createdAt: '2026-09-19T08:00:00Z',
}];
const list = (items = [claim]) => ({ items, truncated: false });
const detail = (extra = {}) => ({
  claim, history, historyTruncated: false,
  canComment: true, canStart: true, canReply: false, canResolve: true, canReopen: false,
  ...extra,
});
const response = (body, status = 200) => ({ ok: status < 400, status, json: async () => body });
const props = { API: '/api', companyContext, user, C, onChanged: jest.fn() };

beforeAll(() => Object.defineProperty(window, 'crypto', { configurable: true, value: require('crypto').webcrypto }));
beforeEach(() => {
  sessionStorage.clear();
  jest.clearAllMocks();
  process.env.REACT_APP_WORK_MATERIAL_ACCOUNTING_ENABLED = '1';
});
afterEach(() => { delete process.env.REACT_APP_WORK_MATERIAL_ACCOUNTING_ENABLED; });

async function openClaim(id = 7) {
  fireEvent.click(await screen.findByRole('button', { name: `Открыть претензию ${id}` }));
  const card = await screen.findByRole('region', { name: `Претензия ${id}` });
  await waitFor(() => expect(within(card).queryByText('Загрузка карточки…')).not.toBeInTheDocument());
  return card;
}

test('loads only the selected company, opens a case and renders server capabilities and immutable history', async () => {
  const requests = [];
  global.fetch = jest.fn(async (url, options = {}) => {
    requests.push([url, new Headers(options.headers).get('X-Company-Id')]);
    return response(url.endsWith('/cases') ? list() : detail());
  });
  render(<SupplyClaims {...props} />);
  const card = await openClaim();

  expect(requests).toEqual([
    ['/api/supply-claims/cases', '2'],
    ['/api/supply-claims/7/case', '2'],
  ]);
  expect(within(card).getByText('Повреждена упаковка')).toBeInTheDocument();
  expect(within(card).getByText('Проверили партию')).toBeInTheDocument();
  expect(within(card).getByText(/Кладовщик/)).toBeInTheDocument();
  expect(within(card).getByText(/поставщик/i)).toBeInTheDocument();
  expect([...within(card).getByLabelText('Действие').options].map(option => option.value))
    .toEqual(['start', 'comment', 'resolve']);
});

test('changing company or user removes the opened case and its private draft before loading the new scope', async () => {
  global.fetch = jest.fn(async (url, options = {}) => {
    const companyId = Number(new Headers(options.headers).get('X-Company-Id'));
    if (url.endsWith('/cases')) return response(list([{ ...claim, id: companyId, companyId, materialName: `Материал ${companyId}` }]));
    return response(detail({ claim: { ...claim, id: companyId, companyId, materialName: `Материал ${companyId}` } }));
  });
  const view = render(<SupplyClaims {...props} />);
  await openClaim(2);
  fireEvent.change(screen.getByLabelText('Сообщение'), { target: { value: 'Закрытый черновик компании 2' } });

  view.rerender(<SupplyClaims {...props} companyContext={{ mode: 'company', selectedCompanyId: 3 }} user={{ ...user, id: 10 }} />);

  expect(await screen.findByText('Материал 3')).toBeInTheDocument();
  expect(screen.queryByText('Материал 2')).not.toBeInTheDocument();
  expect(screen.queryByDisplayValue('Закрытый черновик компании 2')).not.toBeInTheDocument();
  expect(screen.queryByRole('region', { name: 'Претензия 2' })).not.toBeInTheDocument();
});

test('closed or read-only cases render facts and history without inventing actions absent from server caps', async () => {
  global.fetch = jest.fn(async url => response(url.endsWith('/cases')
    ? list([{ ...claim, status: 'Закрыта' }])
    : detail({
      claim: { ...claim, status: 'Закрыта' }, canComment: false, canStart: false,
      canReply: false, canResolve: false, canReopen: false,
    })));
  render(<SupplyClaims {...props} user={{ ...user, role: 'бухгалтер' }} />);
  const card = await openClaim();

  expect(within(card).getByText('Закрыта')).toBeInTheDocument();
  expect(within(card).getByText('Проверили партию')).toBeInTheDocument();
  expect(within(card).queryByLabelText('Действие')).not.toBeInTheDocument();
  expect(within(card).queryByLabelText('Сообщение')).not.toBeInTheDocument();
  expect(within(card).queryByRole('button', { name: 'Сохранить' })).not.toBeInTheDocument();
});

test('supplier replies in the actual buyer company from the claim without requiring buyer membership', async () => {
  const posts = [];
  const supplierClaim = { ...claim, companyId: 44, supplierName: 'Моя поставка' };
  global.fetch = jest.fn(async (url, options = {}) => {
    const companyId = new Headers(options.headers).get('X-Company-Id');
    if (options.method === 'POST') {
      posts.push([url, companyId, JSON.parse(options.body)]);
      return response({ ok: true, id: 7, eventId: 82 });
    }
    if (url.endsWith('/cases')) return response(list([supplierClaim]));
    return response(detail({
      claim: supplierClaim, canComment: false, canStart: false, canReply: true,
      canResolve: false, canReopen: false,
    }));
  });
  render(<SupplyClaims {...props}
    companyContext={{ mode: 'company', selectedCompanyId: null, companies: [] }}
    user={{ id: 19, role: 'поставщик', name: 'Моя поставка' }} />);
  const card = await openClaim();
  expect([...within(card).getByLabelText('Действие').options].map(option => option.value)).toEqual(['reply']);
  fireEvent.change(within(card).getByLabelText('Сообщение'), { target: { value: 'Заменим повреждённые мешки' } });
  fireEvent.click(within(card).getByRole('button', { name: 'Сохранить' }));

  await waitFor(() => expect(posts).toHaveLength(1));
  expect(posts[0]).toEqual(['/api/supply-claims/7/case', '44', expect.objectContaining({
    action: 'reply', text: 'Заменим повреждённые мешки', expectedVersion: 3,
    expectedCompanyId: 44, expectedActorId: 19,
  })]);
  expect(posts[0][2]).not.toHaveProperty('actorName');
  expect(posts[0][2]).not.toHaveProperty('status');
});

test('lost response preserves the action draft and retries byte-identical UUID, text, version and pins', async () => {
  const posts = [];
  let lost = true;
  global.fetch = jest.fn(async (url, options = {}) => {
    if (options.method === 'POST') {
      posts.push(JSON.parse(options.body));
      if (lost) { lost = false; throw new Error('Failed to fetch'); }
      return response({ ok: true, id: 7, eventId: 83 });
    }
    return response(url.endsWith('/cases') ? list() : detail());
  });
  render(<SupplyClaims {...props} />);
  const card = await openClaim();
  fireEvent.change(within(card).getByLabelText('Действие'), { target: { value: 'comment' } });
  fireEvent.change(within(card).getByLabelText('Сообщение'), { target: { value: 'Нужны фотографии паллеты' } });
  fireEvent.click(within(card).getByRole('button', { name: 'Сохранить' }));

  expect(await screen.findByRole('alert')).toHaveTextContent('Связь прервалась');
  expect(screen.getByLabelText('Сообщение')).toHaveValue('Нужны фотографии паллеты');
  fireEvent.click(screen.getByRole('button', { name: 'Повторить сохранённую отправку' }));

  await waitFor(() => expect(posts).toHaveLength(2));
  expect(posts[1]).toEqual(posts[0]);
  expect(posts[0]).toMatchObject({
    action: 'comment', text: 'Нужны фотографии паллеты', expectedVersion: 3,
    expectedCompanyId: 2, expectedActorId: 9,
  });
  expect(posts[0].requestId).toMatch(/^[0-9a-f-]{36}$/);
});

test('recovering another claim command does not clear the currently edited claim', async () => {
  sessionStorage.setItem('stroyka:work-material-batch:v2:2:9', JSON.stringify({ next: 0, commands: [{
    path: '/supply-claims/8/case', method: 'POST', attempted: true,
    payload: {
      requestId: '31f41973-3a60-4fc8-a4d5-73f4952c913e', action: 'comment', text: 'Другая претензия',
      expectedVersion: 4, expectedCompanyId: 2, expectedActorId: 9, materialAccountingVersion: 2,
    },
  }] }));
  global.fetch = jest.fn(async (url, options = {}) => options.method === 'POST'
    ? response({ ok: true, id: 8, eventId: 84 })
    : response(url.endsWith('/cases') ? list() : detail()));
  render(<SupplyClaims {...props} />);
  const card = await openClaim();
  fireEvent.change(within(card).getByLabelText('Действие'), { target: { value: 'resolve' } });
  fireEvent.change(within(card).getByLabelText('Сообщение'), { target: { value: 'Текущий черновик решения' } });
  fireEvent.click(screen.getByRole('button', { name: 'Повторить сохранённую отправку' }));

  await waitFor(() => expect(screen.queryByText('Есть сохранённая отправка')).not.toBeInTheDocument());
  expect(screen.getByLabelText('Действие')).toHaveValue('resolve');
  expect(screen.getByLabelText('Сообщение')).toHaveValue('Текущий черновик решения');
});

test('pending submission disables the form and ignores a double click', async () => {
  let resolvePost;
  const pending = new Promise(resolve => { resolvePost = resolve; });
  let posts = 0;
  global.fetch = jest.fn(async (url, options = {}) => {
    if (options.method === 'POST') { posts += 1; return pending; }
    return response(url.endsWith('/cases') ? list() : detail());
  });
  render(<SupplyClaims {...props} />);
  const card = await openClaim();
  fireEvent.change(within(card).getByLabelText('Сообщение'), { target: { value: 'Начинаем проверку' } });
  const save = within(card).getByRole('button', { name: 'Сохранить' });
  fireEvent.click(save);
  fireEvent.click(save);

  expect(posts).toBe(1);
  expect(screen.getByLabelText('Сообщение')).toBeDisabled();
  expect(screen.getByRole('button', { name: 'Сохранение…' })).toBeDisabled();
  await act(async () => resolvePost(response({ ok: true, id: 7, eventId: 85 })));
  await waitFor(() => expect(screen.getByRole('button', { name: 'Сохранить' })).toBeEnabled());
});

test('list and detail loading errors are visible and independently retryable', async () => {
  let listAttempts = 0;
  let detailAttempts = 0;
  global.fetch = jest.fn(async url => {
    if (url.endsWith('/cases')) {
      listAttempts += 1;
      return listAttempts === 1 ? response({ detail: 'Список временно недоступен' }, 503) : response(list());
    }
    detailAttempts += 1;
    return detailAttempts === 1 ? response({ detail: 'Карточка временно недоступна' }, 503) : response(detail());
  });
  render(<SupplyClaims {...props} />);
  expect(await screen.findByRole('alert')).toHaveTextContent('Список временно недоступен');
  fireEvent.click(screen.getByRole('button', { name: 'Повторить загрузку списка' }));
  await openClaim();
  expect(await screen.findByRole('alert')).toHaveTextContent('Карточка временно недоступна');
  fireEvent.click(screen.getByRole('button', { name: 'Повторить загрузку карточки' }));

  await waitFor(() => expect(screen.getByRole('region', { name: 'Претензия 7' })).toHaveTextContent('Проверили партию'));
  expect(listAttempts).toBe(2);
  expect(detailAttempts).toBe(2);
});


test('after a version conflict explicit refresh preserves text and rebases the next command', async () => {
  let version = 3;
  const posts = [];
  global.fetch = jest.fn(async (url, options = {}) => {
    if (options.method === 'POST') {
      posts.push(JSON.parse(options.body));
      if (posts.length === 1) { version = 4; return response({ detail: 'Претензия изменилась' }, 409); }
      return response({ ok: true, id: 7, eventId: 99 });
    }
    return response(url.endsWith('/cases') ? list() : detail({ claim: { ...claim, version } }));
  });
  render(<SupplyClaims {...props} />);
  const card = await openClaim();
  fireEvent.change(within(card).getByLabelText('Сообщение'), { target: { value: 'Сохранённый черновик' } });
  fireEvent.click(within(card).getByRole('button', { name: 'Сохранить' }));
  await screen.findByRole('alert');
  fireEvent.click(screen.getByRole('button', { name: 'Повторить загрузку карточки' }));
  await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument());
  expect(screen.getByLabelText('Сообщение')).toHaveValue('Сохранённый черновик');
  fireEvent.click(screen.getByRole('button', { name: 'Сохранить' }));
  await waitFor(() => expect(posts).toHaveLength(2));
  expect(posts[0].expectedVersion).toBe(3);
  expect(posts[1].expectedVersion).toBe(4);
});

test('refresh after a committed lost response preserves the frozen command and recovery clears its matching draft', async () => {
  const text = 'Уточнили количество повреждённых мешков';
  const posts = [];
  let committed = false;
  global.fetch = jest.fn(async (url, options = {}) => {
    if (options.method === 'POST') {
      posts.push(options.body);
      if (!committed) {
        committed = true;
        throw new Error('Failed to fetch');
      }
      return response({ ok: true, id: 7, eventId: 100 });
    }
    return response(url.endsWith('/cases') ? list() : detail({
      claim: { ...claim, version: committed ? 4 : 3 },
      history: committed ? [...history, {
        id: 100, action: 'comment', text, actorName: user.name, createdAt: '2026-09-19T09:00:00Z',
      }] : history,
    }));
  });
  render(<SupplyClaims {...props} />);
  const card = await openClaim();
  fireEvent.change(within(card).getByLabelText('Действие'), { target: { value: 'comment' } });
  fireEvent.change(within(card).getByLabelText('Сообщение'), { target: { value: text } });
  fireEvent.click(within(card).getByRole('button', { name: 'Сохранить' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Связь прервалась');

  fireEvent.click(screen.getByRole('button', { name: 'Повторить загрузку карточки' }));
  await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument());
  expect(screen.getByLabelText('Сообщение')).toHaveValue(text);
  expect(within(within(card).getByRole('list')).getByText(text)).toBeInTheDocument();
  const pending = JSON.parse(sessionStorage.getItem('stroyka:work-material-batch:v2:2:9'));
  expect(pending.commands[0].payload.expectedVersion).toBe(3);

  fireEvent.click(screen.getByRole('button', { name: 'Повторить сохранённую отправку' }));
  await waitFor(() => expect(screen.getByLabelText('Сообщение')).toHaveValue(''));
  await waitFor(() => expect(screen.queryByText('Есть сохранённая отправка')).not.toBeInTheDocument());
  expect(posts).toHaveLength(2);
  expect(posts[1]).toBe(posts[0]);
  expect(JSON.parse(posts[1]).expectedVersion).toBe(3);
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
});
