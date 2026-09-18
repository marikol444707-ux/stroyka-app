import { act, renderHook } from '@testing-library/react';
import useJournalMutation from './useJournalMutation';
import { beginQualityJournalMutation, finishQualityJournalMutation } from '../utils/qualityJournalEvents';

jest.mock('../utils/qualityJournalEvents', () => ({ beginQualityJournalMutation: jest.fn(), finishQualityJournalMutation: jest.fn() }));

const row = { id: 7, companyId: 2, projectId: 3 };
const scope = companyId => {
  localStorage.setItem('user', JSON.stringify({ id: 1 }));
  localStorage.setItem('stroyka.companyContext.v1.1', JSON.stringify({ mode: 'company', companyId }));
};
const response = (ok = true, data = { ok: true }) => ({ ok, status: ok ? 200 : 409, json: async () => data });
const originalFetch = global.fetch;
beforeEach(() => {
  localStorage.clear(); scope(2); global.fetch = jest.fn();
  beginQualityJournalMutation.mockReset().mockImplementation(() => Symbol('mutation'));
  finishQualityJournalMutation.mockReset();
});
afterEach(() => { global.fetch = originalFetch; localStorage.clear(); });

test('HTTP failure preserves caller state and exposes detail; retry only applies success', async () => {
  fetch.mockResolvedValueOnce(response(false, { detail: 'Данные изменились' })).mockResolvedValueOnce(response());
  const saved = jest.fn();
  const { result } = renderHook(() => useJournalMutation(row));
  await act(async () => { await result.current.run({ url: '/test', body: { remarks: 'draft' }, onSuccess: saved }); });
  expect(result.current.error).toBe('Данные изменились');
  expect(saved).not.toHaveBeenCalled();
  expect(finishQualityJournalMutation).toHaveBeenLastCalledWith(beginQualityJournalMutation.mock.results[0].value, { confirmed: false, uncertain: false });
  expect(result.current.busy).toBe(false);
  await act(async () => { await result.current.run({ url: '/test', body: {}, onSuccess: saved }); });
  expect(saved).toHaveBeenCalledTimes(1);
  expect(finishQualityJournalMutation).toHaveBeenLastCalledWith(beginQualityJournalMutation.mock.results[1].value, { confirmed: true, uncertain: false });
  expect(result.current.error).toBe('');
});

test.each(['row', 'company', 'unmount', 'close'])('late response after %s does not apply', async change => {
  let finish;
  fetch.mockImplementation(() => new Promise(resolve => { finish = resolve; }));
  const saved = jest.fn();
  const { result, rerender, unmount } = renderHook(({ record }) => useJournalMutation(record), { initialProps: { record: row } });
  let pending;
  act(() => { pending = result.current.run({ url: '/test', body: {}, onSuccess: saved }); });
  expect(result.current.busy).toBe(true);
  if (change === 'row') rerender({ record: { ...row, id: 8 } });
  if (change === 'company') scope(9); // no rerender required
  if (change === 'unmount') unmount();
  if (change === 'close') act(() => result.current.cancel());
  await act(async () => { finish(response()); await pending; });
  expect(saved).not.toHaveBeenCalled();
  expect(finishQualityJournalMutation).toHaveBeenCalledTimes(1);
  expect(finishQualityJournalMutation).toHaveBeenCalledWith(beginQualityJournalMutation.mock.results[0].value,
    { confirmed: change === 'company', uncertain: change !== 'company' });
});

test('same-tick duplicate and cross-company submissions never reach fetch twice', async () => {
  let finish;
  fetch.mockImplementation(() => new Promise(resolve => { finish = resolve; }));
  const { result } = renderHook(() => useJournalMutation(row));
  let pending;
  act(() => { pending = result.current.run({ url: '/test', body: {} }); result.current.run({ url: '/test', body: {} }); });
  expect(fetch).toHaveBeenCalledTimes(1);
  expect(beginQualityJournalMutation).toHaveBeenCalledTimes(1);
  await act(async () => { finish(response()); await pending; });
  scope(9);
  await act(async () => { await result.current.run({ url: '/test', body: {} }); });
  expect(fetch).toHaveBeenCalledTimes(1);
});

test('network and malformed success responses never call success', async () => {
  fetch.mockRejectedValueOnce(new Error('offline')).mockResolvedValueOnce({ ok: true, json: async () => { throw new Error('bad json'); } });
  const saved = jest.fn();
  const { result } = renderHook(() => useJournalMutation(row));
  for (let i = 0; i < 2; i += 1) {
    await act(async () => { await result.current.run({ url: '/test', body: {}, onSuccess: saved }); });
    expect(result.current.busy).toBe(false);
    expect(result.current.error).toBeTruthy();
    expect(finishQualityJournalMutation).toHaveBeenLastCalledWith(beginQualityJournalMutation.mock.results[i].value, { confirmed: false, uncertain: true });
  }
  expect(saved).not.toHaveBeenCalled();
});

test.each(['network', 'abort', '408', '418', '500', 'bad-json', 'unconfirmed'])('%s keeps outcome uncertain and begins before dispatch', async kind => {
  const saved = jest.fn();
  fetch.mockImplementation(async () => {
    expect(beginQualityJournalMutation).toHaveBeenCalledTimes(1);
    expect(finishQualityJournalMutation).not.toHaveBeenCalled();
    if (kind === 'network' || kind === 'abort') throw new Error(kind);
    if (['408', '418', '500'].includes(kind)) return { ok: false, status: Number(kind), json: async () => ({ detail: 'Failed' }) };
    if (kind === 'bad-json') return { ok: true, status: 200, json: async () => { throw new Error('Invalid JSON'); } };
    return response(true, { ok: false });
  });
  const { result } = renderHook(() => useJournalMutation(row));
  await act(async () => result.current.run({ url: '/test', onSuccess: saved }));
  expect(saved).not.toHaveBeenCalled();
  expect(finishQualityJournalMutation).toHaveBeenCalledTimes(1);
  expect(finishQualityJournalMutation).toHaveBeenCalledWith(beginQualityJournalMutation.mock.results[0].value, { confirmed: false, uncertain: true });
});

test.each([400, 401, 403, 404, 409, 422, 429])('known HTTP %s rejection remains definitive with unreadable JSON', async status => {
  fetch.mockResolvedValue({ ok: false, status, json: async () => { throw new Error('Invalid JSON'); } });
  const { result } = renderHook(() => useJournalMutation(row));
  await act(async () => result.current.run({ url: '/test' }));
  expect(finishQualityJournalMutation).toHaveBeenCalledWith(beginQualityJournalMutation.mock.results[0].value, { confirmed: false, uncertain: false });
});

test('closing aborts and settles uncertain even if fetch ignores abort; later success cannot confirm that token', async () => {
  let resolve;
  fetch.mockImplementation(() => new Promise(done => { resolve = done; }));
  const { result } = renderHook(() => useJournalMutation(row));
  let pending;
  act(() => { pending = result.current.run({ url: '/test' }); });
  act(() => result.current.cancel());
  expect(finishQualityJournalMutation).toHaveBeenCalledWith(beginQualityJournalMutation.mock.results[0].value, { confirmed: false, uncertain: true });
  await act(async () => { resolve(response()); await pending; });
  expect(finishQualityJournalMutation).toHaveBeenCalledTimes(1);
});

test('an unrelated successful write only confirms its own token', async () => {
  fetch.mockRejectedValueOnce(new Error('lost response')).mockResolvedValueOnce(response());
  const { result } = renderHook(() => useJournalMutation(row));
  await act(async () => result.current.run({ url: '/test' }));
  await act(async () => result.current.run({ url: '/other' }));
  expect(finishQualityJournalMutation.mock.calls).toEqual([
    [beginQualityJournalMutation.mock.results[0].value, { confirmed: false, uncertain: true }],
    [beginQualityJournalMutation.mock.results[1].value, { confirmed: true, uncertain: false }],
  ]);
});

test.each(['company', 'owner', 'unmount'])('print rejects stale or unowned record: %s', change => {
  const builder = jest.fn(() => 'document');
  const preview = jest.fn();
  const { result, unmount } = renderHook(() => useJournalMutation(change === 'owner' ? { id: 7 } : row));
  const print = result.current.print;
  if (change === 'company') scope(9);
  if (change === 'unmount') unmount();
  act(() => print(builder, preview, 'Title'));
  expect(builder).not.toHaveBeenCalled();
  expect(preview).not.toHaveBeenCalled();
});
