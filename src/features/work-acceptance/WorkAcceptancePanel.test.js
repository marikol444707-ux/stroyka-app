import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import WorkAcceptancePanel from './WorkAcceptancePanel';

jest.mock('../uploads/useProtectedFileObjectUrl', () => () => ({ src: 'blob:photo' }));
const context = { selectedCompanyId: 2 };
const initial = { journalId: 11, status: 'На проверке', quantity: 100, unit: 'м²', projectId: 7,
  description: 'Штукатурка', project: 'Лицей', masterName: 'Мастер', roomName: 'Класс', photos: [],
  expectedState: 'state-1', history: [], canReview: true, canResubmit: false, parentJournalId: null, reworkJournalId: null };
const props = { journal: { id: 11 }, API: '/api', companyContext: context, user: { id: 9 }, C: {},
  onClose: jest.fn(), onChanged: jest.fn() };
let view, requests;
beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function () { this.setAttribute('open', ''); };
  Object.defineProperty(window, 'crypto', { configurable: true, value: require('crypto').webcrypto });
});
beforeEach(() => {
  process.env.REACT_APP_WORK_MATERIAL_ACCOUNTING_ENABLED = '1';
  sessionStorage.clear(); view = { ...initial }; requests = [];
  global.fetch = jest.fn(async (url, options = {}) => {
    if (url.endsWith('/upload-photo')) return { ok: true, json: async () => ({ contentUrl: '/tenant-files/7/content' }) };
    if (options.method === 'POST') {
      requests.push({ url, payload: JSON.parse(options.body) });
      view = { ...view, canReview: false, canResubmit: false, status: 'Подтверждено' };
      return { ok: true, json: async () => ({ ok: true, journalId: 11, reviewId: 1, reworkJournalId: 12 }) };
    }
    return { ok: true, json: async () => view };
  });
});
afterEach(() => { delete process.env.REACT_APP_WORK_MATERIAL_ACCOUNTING_ENABLED; });

test('partial acceptance requires remarks and posts quantity with the displayed state', async () => {
  render(<WorkAcceptancePanel {...props} />);
  fireEvent.change(await screen.findByLabelText('Принять (м²)'), { target: { value: '60' } });
  expect(screen.getByText(/На доработку: 40/)).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Принять объём' })).toBeDisabled();
  fireEvent.change(screen.getByLabelText('Замечания'), { target: { value: 'Исправить углы' } });
  fireEvent.click(screen.getByRole('button', { name: 'Принять объём' }));
  await waitFor(() => expect(requests).toHaveLength(1));
  expect(requests[0]).toMatchObject({ url: '/api/work-journal/11/acceptance', payload: {
    expectedState: 'state-1', decision: 'accept', acceptedQuantity: '60', reason: 'Исправить углы', photos: [],
    expectedCompanyId: 2, expectedActorId: 9,
  } });
});

test('return uses its own decision and requires a reason', async () => {
  render(<WorkAcceptancePanel {...props} />);
  expect(await screen.findByRole('button', { name: 'Вернуть весь объём' })).toBeDisabled();
  fireEvent.change(screen.getByLabelText('Замечания'), { target: { value: 'Переделать' } });
  fireEvent.click(screen.getByRole('button', { name: 'Вернуть весь объём' }));
  await waitFor(() => expect(requests).toHaveLength(1));
  expect(requests[0].payload).toMatchObject({ decision: 'return', acceptedQuantity: null, reason: 'Переделать' });
});

test('worker resubmits fixed rework quantity only after new photo and comment', async () => {
  view = { ...initial, canReview: false, canResubmit: true, status: 'На доработке', quantity: 40, parentJournalId: 10 };
  const prepare = jest.fn((_project, groups) => groups);
  render(<WorkAcceptancePanel {...props} prepareWorkMaterialGroups={prepare} materialAvailabilityMapForWork={() => ({})} />);
  expect(await screen.findByRole('button', { name: 'Сдать доработку' })).toBeDisabled();
  expect(screen.queryByLabelText('Принять (м²)')).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('Что исправлено'), { target: { value: 'Углы исправлены' } });
  expect(screen.getByRole('button', { name: 'Сдать доработку' })).toBeDisabled();
  fireEvent.change(screen.getByLabelText('Новые фотографии'), { target: { files: [new File(['x'], 'work.jpg', { type: 'image/jpeg' })] } });
  await waitFor(() => expect(screen.getByRole('button', { name: 'Сдать доработку' })).toBeEnabled());
  fireEvent.click(screen.getByRole('button', { name: 'Сдать доработку' }));
  await waitFor(() => expect(requests).toHaveLength(1));
  expect(requests[0]).toMatchObject({ url: '/api/work-journal/11/resubmit', payload: {
    comment: 'Углы исправлены', photos: ['/tenant-files/7/content'], materialsUsed: [], expectedState: 'state-1',
  } });
  expect(requests[0].payload).not.toHaveProperty('quantity');
});

test('lost acceptance reply retries exactly the saved command once', async () => {
  const realMock = global.fetch;
  let dropped = false;
  global.fetch = jest.fn(async (url, options) => {
    const result = await realMock(url, options);
    if (options?.method === 'POST' && !dropped) { dropped = true; throw new Error('Failed to fetch'); }
    return result;
  });
  render(<WorkAcceptancePanel {...props} />);
  fireEvent.click(await screen.findByRole('button', { name: 'Принять объём' }));
  await screen.findByText(/Связь прервалась/);
  fireEvent.click(screen.getByRole('button', { name: 'Повторить сохранённую отправку' }));
  await waitFor(() => expect(requests).toHaveLength(2));
  expect(requests[1]).toEqual(requests[0]);
  await waitFor(() => expect(screen.queryByText('Есть сохранённая отправка')).not.toBeInTheDocument());
});
