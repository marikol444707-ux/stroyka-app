import React from 'react';
import { render, screen, waitFor, act } from '@testing-library/react';
import useProgressData from './useProgressData';

function Harness({ project = { id: 3, companyId: 2, name: 'Site' } }) {
  const data = useProgressData(project, 7, 'stable');
  return <p>{data.loading ? 'loading' : data.error || JSON.stringify(data.journal)}</p>;
}
afterEach(() => jest.restoreAllMocks());
test('loads the full journal and filters exact owner before exposing records', async () => {
  global.fetch = jest.fn(async url => ({ ok: true, json: async () => url.includes('/estimates') ? []
    : [{ id: 1, companyId: 2, projectId: 3, status: 'Подтверждено' }, { id: 2, companyId: 4, projectId: 3, status: 'Подтверждено' }] }));
  render(<Harness />);
  await waitFor(() => expect(screen.queryByText('loading')).toBeNull());
  expect(screen.getByText(/"id":1/)).toBeTruthy();
  expect(screen.queryByText(/"id":2/)).toBeNull();
  expect(fetch.mock.calls[1][0]).not.toContain('limit=');
  expect(fetch.mock.calls[0][1].headers['X-Company-Id']).toBe('2');
});
test('a failed source does not become an empty completed dataset', async () => {
  global.fetch = jest.fn(async () => ({ ok: false, status: 403 }));
  render(<Harness />);
  await screen.findByText(/Не удалось загрузить/);
});
test('late data for a previous object never replaces the new object', async () => {
  const pending = [];
  global.fetch = jest.fn(() => new Promise(resolve => pending.push(resolve)));
  const view = render(<Harness />);
  view.rerender(<Harness project={{ id: 4, companyId: 2, name: 'Other' }} />);
  await act(async () => { for (const resolve of pending.slice(0, 2)) resolve({ ok: true, json: async () => [] }); });
  expect(screen.getByText('loading')).toBeTruthy();
  await act(async () => { for (const resolve of pending.slice(2)) resolve({ ok: true, json: async () => [] }); });
  expect(screen.getByText('[]')).toBeTruthy();
});
