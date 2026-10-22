import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import OpportunityCandidatesPanel from './OpportunityCandidatesPanel';

afterEach(() => {
  jest.restoreAllMocks();
});

test('loads candidates and records a human review in the selected company API', async () => {
  const candidate = {
    id: 12,
    title: 'Капитальный ремонт кровли',
    url: 'https://example.org/tender/12',
    region: 'Ставропольский край',
    workTypes: ['Кровля'],
    status: 'Нужно проверить',
    source: 'eis',
  };
  const fetchMock = jest.spyOn(global, 'fetch').mockImplementation(async (_url, options = {}) => ({
    ok: true,
    json: async () => String(_url).endsWith('/access') ? { enabled: true } : options.method === 'PUT' ? { ok: true } : [candidate],
  }));

  render(<OpportunityCandidatesPanel API="/api" C={{ text: '#111', textSec: '#555', border: '#ddd' }} />);

  const title = await screen.findByText('Капитальный ремонт кровли');
  expect(title).toBeInTheDocument();
  const candidateCard = within(title.closest('article'));
  fireEvent.click(candidateCard.getByRole('button', { name: 'Подходит' }));

  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith('/api/crm/job-candidates/12/review', expect.objectContaining({ method: 'PUT' })));
  expect(candidateCard.getByRole('link', { name: 'Открыть источник' })).toHaveAttribute('href', candidate.url);
});

test('manually adds a candidate with its source URL', async () => {
  const fetchMock = jest.spyOn(global, 'fetch').mockImplementation(async (_url, options = {}) => ({
    ok: true,
    json: async () => String(_url).endsWith('/access') ? { enabled: true } : options.method === 'POST' ? { ok: true, id: 21 } : [],
  }));

  render(<OpportunityCandidatesPanel API="/api" C={{ text: '#111', textSec: '#555', border: '#ddd' }} />);
  fireEvent.click(await screen.findByRole('button', { name: 'Добавить находку' }));
  fireEvent.change(screen.getByLabelText('Название заказа'), { target: { value: 'Ремонт школы' } });
  fireEvent.change(screen.getByLabelText('Ссылка на источник'), { target: { value: 'https://example.org/order/1' } });
  fireEvent.click(screen.getByRole('button', { name: 'Сохранить' }));

  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith('/api/crm/job-candidates', expect.objectContaining({ method: 'POST' })));
  const request = fetchMock.mock.calls.find(([, options]) => options?.method === 'POST');
  expect(JSON.parse(request[1].body)).toMatchObject({
    source: 'manual',
    title: 'Ремонт школы',
    url: 'https://example.org/order/1',
    region: 'Ставропольский край',
  });
});

test('imports JEV commercial and separate government-review rows while excluding its excluded bucket', async () => {
  const alert = jest.spyOn(window, 'alert').mockImplementation(() => {});
  const fetchMock = jest.spyOn(global, 'fetch').mockImplementation(async (_url, options = {}) => ({
    ok: true,
    json: async () => String(_url).endsWith('/access') ? { enabled: true } : options.method === 'POST' ? { ok: true, received: 1, created: 1, updated: 0 } : [],
  }));
  const report = {
    region: 'Ставропольский край',
    confirmed: [{ source: 'B2B-Center', id: '77', url: 'https://b2b-center.ru/tender/77', title: 'Ремонт школы', price: '1.234.567,89 ₽', deadline_msk: '2026-11-01T12:00:00+03:00', reasons: [] }],
    review: [],
    government_review: [{ source: 'ЕИС', provider: 'ЕИС · 44-ФЗ', id: '0123456789012345678', regime: '44-ФЗ', region_scope: 'not_filtered', url: 'https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber=0123456789012345678', title: 'Капитальный ремонт школы', region: '', price: '40538924.61', reasons: ['government_procurement_manual_verification'] }],
    excluded: { other_region: 4 },
  };
  const file = new File([JSON.stringify(report)], 'report.json', { type: 'application/json' });
  Object.defineProperty(file, 'text', { value: async () => JSON.stringify(report) });

  render(<OpportunityCandidatesPanel API="/api" C={{ text: '#111', textSec: '#555', border: '#ddd' }} />);
  fireEvent.change(await screen.findByLabelText('Файл отчёта JEV'), { target: { files: [file] } });

  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith('/api/crm/job-candidates/import-report', expect.objectContaining({ method: 'POST' })));
  const request = fetchMock.mock.calls.find(([, options]) => options?.method === 'POST');
  const body = JSON.parse(request[1].body);
  expect(body.items).toHaveLength(2);
  expect(body.items[0]).toMatchObject({
    source: 'browser_agent', sourceName: 'B2B-Center', sourceItemId: 'B2B-Center:77',
    title: 'Ремонт школы', region: 'Ставропольский край', price: '1234567.89',
  });
  expect(body.items[1]).toMatchObject({
    source: 'browser_agent', sourceName: 'ЕИС · 44-ФЗ', sourceItemId: 'ЕИС · 44-ФЗ:0123456789012345678',
    title: 'Капитальный ремонт школы', region: '', price: '40538924.61',
  });
  expect(body.items[1].evidence).toContain('Режим закупки: 44-ФЗ');
  expect(alert).toHaveBeenCalledWith('Импорт завершён: новых 1, обновлено 0.');
});

test('hides candidate actions for an organization without a JEV subscription', async () => {
  jest.spyOn(global, 'fetch').mockResolvedValue({
    ok: true,
    json: async () => ({ enabled: false }),
  });

  render(<OpportunityCandidatesPanel API="/api" />);

  expect(await screen.findByText(/функция пока не подключена вашей организации/i)).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Добавить находку' })).not.toBeInTheDocument();
});

test('filters the company queue by text, source and deadline without another API request', async () => {
  const candidates = [
    {
      id: 31, title: 'Ремонт школы', description: 'Заказчик: администрация', region: 'Ставропольский край',
      sourceName: 'B2B-Center', url: 'https://example.org/31', status: 'Нужно проверить',
      deadline: '2999-12-31T12:00:00+03:00',
    },
    {
      id: 32, title: 'Ремонт кровли', description: 'Заказчик: лицей', region: 'Ставропольский край',
      sourceName: 'Росэлторг', url: 'https://example.org/32', status: 'Нужно проверить',
      deadline: '2000-01-01T12:00:00+03:00',
    },
  ];
  const fetchMock = jest.spyOn(global, 'fetch').mockResolvedValue({
    ok: true,
    json: async () => String(fetchMock.mock.calls.at(-1)?.[0]).endsWith('/access')
      ? { enabled: true }
      : candidates,
  });

  render(<OpportunityCandidatesPanel API="/api" C={{ text: '#111', textSec: '#555', border: '#ddd' }} />);

  expect(await screen.findByText('Ремонт школы')).toBeInTheDocument();
  fireEvent.change(screen.getByRole('searchbox', { name: 'Поиск по находкам' }), { target: { value: 'кровля' } });
  expect(screen.queryByText('Ремонт школы')).not.toBeInTheDocument();
  expect(screen.getByText('Ремонт кровли')).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText('Площадка'), { target: { value: 'B2B-Center' } });
  expect(screen.queryByText('Ремонт кровли')).not.toBeInTheDocument();
  fireEvent.change(screen.getByRole('searchbox', { name: 'Поиск по находкам' }), { target: { value: '' } });
  expect(screen.getByText('Ремонт школы')).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText('Срок подачи'), { target: { value: 'expired' } });
  expect(screen.queryByText('Ремонт школы')).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('Площадка'), { target: { value: '' } });
  expect(screen.getByText('Ремонт кровли')).toBeInTheDocument();
  expect(fetchMock).toHaveBeenCalledTimes(2);
});
