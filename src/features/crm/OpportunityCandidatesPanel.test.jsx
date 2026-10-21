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
    json: async () => options.method === 'PUT' ? { ok: true } : [candidate],
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
    json: async () => options.method === 'POST' ? { ok: true, id: 21 } : [],
  }));

  render(<OpportunityCandidatesPanel API="/api" C={{ text: '#111', textSec: '#555', border: '#ddd' }} />);
  fireEvent.click(screen.getByRole('button', { name: 'Добавить находку' }));
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

test('imports JEV confirmed and review rows while excluding its excluded bucket', async () => {
  const alert = jest.spyOn(window, 'alert').mockImplementation(() => {});
  const fetchMock = jest.spyOn(global, 'fetch').mockImplementation(async (_url, options = {}) => ({
    ok: true,
    json: async () => options.method === 'POST' ? { ok: true, received: 1, created: 1, updated: 0 } : [],
  }));
  const report = {
    region: 'Ставропольский край',
    confirmed: [{ source: 'B2B-Center', id: '77', url: 'https://b2b-center.ru/tender/77', title: 'Ремонт школы', price: '1.234.567,89 ₽', deadline_msk: '2026-11-01T12:00:00+03:00', reasons: [] }],
    review: [],
    excluded: { other_region: 4 },
  };
  const file = new File([JSON.stringify(report)], 'report.json', { type: 'application/json' });
  Object.defineProperty(file, 'text', { value: async () => JSON.stringify(report) });

  render(<OpportunityCandidatesPanel API="/api" C={{ text: '#111', textSec: '#555', border: '#ddd' }} />);
  fireEvent.change(screen.getByLabelText('Файл отчёта JEV'), { target: { files: [file] } });

  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith('/api/crm/job-candidates/import-report', expect.objectContaining({ method: 'POST' })));
  const request = fetchMock.mock.calls.find(([, options]) => options?.method === 'POST');
  const body = JSON.parse(request[1].body);
  expect(body.items).toHaveLength(1);
  expect(body.items[0]).toMatchObject({
    source: 'browser_agent', sourceName: 'B2B-Center', sourceItemId: 'B2B-Center:77',
    title: 'Ремонт школы', region: 'Ставропольский край', price: '1234567.89',
  });
  expect(alert).toHaveBeenCalledWith('Импорт завершён: новых 1, обновлено 0.');
});
