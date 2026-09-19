import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import CompanyWarehouses from './CompanyWarehouses';

const card = { id: 7, companyId: 2, name: 'Лесной', city: 'Ставрополь', address: 'Лесная, 1', notes: 'Въезд со двора', version: 3, archived: false };
const props = { API: '/api', companyContext: { mode: 'company', selectedCompanyId: 2 }, user: { id: 9, role: 'директор' }, C: {}, onChanged: jest.fn() };
const response = (body, status = 200) => ({ ok: status < 400, status, json: async () => body });
const list = (items = [card], extra = {}) => ({ items, canManage: true, canArchive: true, ...extra });
beforeAll(() => Object.defineProperty(window, 'crypto', { configurable: true, value: require('crypto').webcrypto }));
beforeEach(() => { sessionStorage.clear(); jest.clearAllMocks(); process.env.REACT_APP_WORK_MATERIAL_ACCOUNTING_ENABLED = '1'; });
afterEach(() => { delete process.env.REACT_APP_WORK_MATERIAL_ACCOUNTING_ENABLED; });

test('read-only roles see their cards without management controls; archive is separate', async () => {
  global.fetch = jest.fn(async () => response(list([card, { ...card, id: 8, name: 'Старый', archived: true }], { canManage: false, canArchive: false })));
  render(<CompanyWarehouses {...props} />);
  expect(await screen.findByText('Лесной')).toBeInTheDocument();
  expect(screen.queryByText('Старый')).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Добавить склад' })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /Изменить/ })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: /Архив/ }));
  expect(screen.getByText('Старый')).toBeInTheDocument();
});

test('lost update response preserves the form and retries exact UUID, version, company and content', async () => {
  const posts = []; let updated = false;
  global.fetch = jest.fn(async (url, options = {}) => {
    if (options.method === 'POST') {
      posts.push(JSON.parse(options.body));
      if (!updated) { updated = true; throw new Error('Failed to fetch'); }
      return response({ ok: true, warehouseId: 7, eventId: 81 });
    }
    return response(list([{ ...card, name: updated ? 'Новый адрес' : card.name }]));
  });
  render(<CompanyWarehouses {...props} />);
  fireEvent.click(await screen.findByRole('button', { name: 'Изменить Лесной' }));
  fireEvent.change(screen.getByLabelText('Название склада'), { target: { value: 'Новый адрес' } });
  fireEvent.click(screen.getByRole('button', { name: 'Сохранить карточку' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Связь прервалась');
  expect(screen.getByLabelText('Название склада')).toHaveValue('Новый адрес');
  fireEvent.click(screen.getByRole('button', { name: 'Повторить сохранённую отправку' }));
  await waitFor(() => expect(posts).toHaveLength(2));
  expect(posts[1]).toEqual(posts[0]);
  expect(posts[0]).toMatchObject({ action: 'update', expectedVersion: 3, expectedCompanyId: 2, expectedActorId: 9, name: 'Новый адрес' });
  await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument());
  expect(screen.queryByLabelText('Название склада')).not.toBeInTheDocument();
  expect(screen.getByText('Новый адрес')).toBeInTheDocument();
});

test('archive requires a reason and sends a versioned command without deleting the card', async () => {
  const posts = [];
  global.fetch = jest.fn(async (url, options = {}) => {
    if (options.method === 'POST') { posts.push({ url, data: JSON.parse(options.body) }); return response({ ok: true }); }
    return response(list());
  });
  render(<CompanyWarehouses {...props} />);
  fireEvent.click(await screen.findByRole('button', { name: 'В архив Лесной' }));
  expect(screen.getByRole('button', { name: 'Подтвердить архивирование' })).toBeDisabled();
  fireEvent.change(screen.getByLabelText('Основание'), { target: { value: 'Площадка закрыта' } });
  fireEvent.click(screen.getByRole('button', { name: 'Подтвердить архивирование' }));
  await waitFor(() => expect(posts).toHaveLength(1));
  expect(posts[0]).toMatchObject({ url: '/api/warehouses/7/directory', data: { action: 'archive', expectedVersion: 3, reason: 'Площадка закрыта' } });
});

test('a stale version error explains the conflict and preserves the edited card', async () => {
  global.fetch = jest.fn(async (url, options = {}) => options.method === 'POST'
    ? response({ detail: 'Карточка изменена. Обновите её перед сохранением' }, 409)
    : response(list()));
  render(<CompanyWarehouses {...props} />);
  fireEvent.click(await screen.findByRole('button', { name: 'Изменить Лесной' }));
  fireEvent.change(screen.getByLabelText('Адрес'), { target: { value: 'Новая улица, 4' } });
  fireEvent.click(screen.getByRole('button', { name: 'Сохранить карточку' }));

  expect(await screen.findByRole('alert')).toHaveTextContent('Карточка изменена. Обновите её перед сохранением');
  expect(screen.getByLabelText('Адрес')).toHaveValue('Новая улица, 4');
  expect(screen.getByRole('button', { name: 'Сохранить карточку' })).toBeInTheDocument();
});

test('recovering an unrelated saved command does not discard an open warehouse draft', async () => {
  sessionStorage.setItem('stroyka:work-material-batch:v2:2:9', JSON.stringify({ next: 0, commands: [{
    path: '/inventory/41/reconciliation', method: 'POST', attempted: true,
    payload: { requestId: '31f41973-3a60-4fc8-a4d5-73f4952c913c' },
  }] }));
  global.fetch = jest.fn(async (url, options = {}) => options.method === 'POST'
    ? response({ ok: true, inventoryId: 41, eventId: 82 })
    : response(list()));
  render(<CompanyWarehouses {...props} />);
  fireEvent.click(await screen.findByRole('button', { name: 'Изменить Лесной' }));
  fireEvent.change(screen.getByLabelText('Заметки'), { target: { value: 'Не терять этот черновик' } });
  fireEvent.click(screen.getByRole('button', { name: 'Повторить сохранённую отправку' }));

  await waitFor(() => expect(screen.queryByText('Есть сохранённая отправка')).not.toBeInTheDocument());
  expect(screen.getByLabelText('Заметки')).toHaveValue('Не терять этот черновик');
});

test('recovering another warehouse command does not discard the warehouse currently being edited', async () => {
  sessionStorage.setItem('stroyka:work-material-batch:v2:2:9', JSON.stringify({ next: 0, commands: [{
    path: '/warehouses/8/directory', method: 'POST', attempted: true,
    payload: {
      requestId: '31f41973-3a60-4fc8-a4d5-73f4952c913d',
      action: 'update', expectedVersion: 4,
      name: 'Южный', city: 'Ставрополь', address: 'Южная, 2', notes: 'Другая карточка',
    },
  }] }));
  global.fetch = jest.fn(async (url, options = {}) => options.method === 'POST'
    ? response({ ok: true, warehouseId: 8, eventId: 83 })
    : response(list()));
  render(<CompanyWarehouses {...props} />);
  fireEvent.click(await screen.findByRole('button', { name: 'Изменить Лесной' }));
  fireEvent.change(screen.getByLabelText('Заметки'), { target: { value: 'Текущая карточка остаётся открытой' } });
  fireEvent.click(screen.getByRole('button', { name: 'Повторить сохранённую отправку' }));

  await waitFor(() => expect(screen.queryByText('Есть сохранённая отправка')).not.toBeInTheDocument());
  expect(screen.getByLabelText('Заметки')).toHaveValue('Текущая карточка остаётся открытой');
});

test('switching company removes an unsaved private draft and history', async () => {
  global.fetch = jest.fn(async (url, options = {}) => response(list(new Headers(options.headers).get('X-Company-Id') === '3' ? [] : [card])));
  const view = render(<CompanyWarehouses {...props} />);
  fireEvent.click(await screen.findByRole('button', { name: 'Изменить Лесной' }));
  fireEvent.change(screen.getByLabelText('Заметки'), { target: { value: 'Частные сведения' } });
  view.rerender(<CompanyWarehouses {...props} companyContext={{ mode: 'company', selectedCompanyId: 3 }} />);
  expect(await screen.findByText(/Действующих карточек пока нет/)).toBeInTheDocument();
  expect(screen.queryByDisplayValue('Частные сведения')).not.toBeInTheDocument();
  expect(screen.queryByText('Лесной')).not.toBeInTheDocument();
});

test('switching user or role removes an unsaved private draft', async () => {
  global.fetch = jest.fn(async () => response(list()));
  const view = render(<CompanyWarehouses {...props} />);
  fireEvent.click(await screen.findByRole('button', { name: 'Изменить Лесной' }));
  fireEvent.change(screen.getByLabelText('Заметки'), { target: { value: 'Черновик директора' } });
  view.rerender(<CompanyWarehouses {...props} user={{ id: 10, role: 'бухгалтер' }} />);

  await waitFor(() => expect(screen.queryByDisplayValue('Черновик директора')).not.toBeInTheDocument());
  expect(screen.queryByRole('button', { name: 'Сохранить карточку' })).not.toBeInTheDocument();
});

test('all-companies mode requires a selection and performs no fetch', () => {
  global.fetch = jest.fn();
  render(<CompanyWarehouses {...props} companyContext={{ mode: 'all_companies' }} />);
  expect(screen.getByText(/выберите конкретную компанию/)).toBeInTheDocument();
  expect(global.fetch).not.toHaveBeenCalled();
});
