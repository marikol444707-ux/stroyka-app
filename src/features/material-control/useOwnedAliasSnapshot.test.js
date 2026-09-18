import { loadOwnedAliasSnapshot, useOwnedAliasSnapshot } from './useOwnedAliasSnapshot';
import { act, renderHook, waitFor } from '@testing-library/react';

const projects = [{id: 7, companyId: 2, name: 'Школа'}, {id: 8, companyId: 3, name: 'Школа'}];
const common = {id: 'cma:1', companyId: 2, projectId: null, aliasName: 'Марка', canonicalName: 'Материал'};
const response = (items, revision) => ({ok: true, json: async () => ({items, revision, limit: 500, offset: 0})});
const companyContext = companyId => ({mode: 'company', selectedCompanyId: companyId, selectedCompany: {
  companyId, membershipId: companyId, source: 'membership', active: true, companyActive: true, role: 'директор',
}});

test('snapshot loads only selected-company scopes and deduplicates common mappings', async () => {
  global.fetch = jest.fn().mockResolvedValueOnce(response([common], 'v1')).mockResolvedValueOnce(response([common], 'v1'));
  expect(await loadOwnedAliasSnapshot('/api', 2, projects)).toEqual([common]);
  expect(global.fetch.mock.calls.map(([url]) => url)).toEqual([
    '/api/company-material-aliases?companyId=2&limit=500&offset=0',
    '/api/company-material-aliases?companyId=2&limit=500&offset=0&projectId=7',
  ]);
});

test('a changing directory never produces a mixed snapshot', async () => {
  global.fetch = jest.fn().mockResolvedValueOnce(response([common], 'v1')).mockResolvedValueOnce(response([], 'v2'));
  await expect(loadOwnedAliasSnapshot('/api', 2, projects)).rejects.toThrow('изменился');
});

test('missing revision and failures never downgrade to legacy data', async () => {
  global.fetch = jest.fn().mockResolvedValue(response([], undefined));
  await expect(loadOwnedAliasSnapshot('/api', 2, projects)).rejects.toThrow('версии');
  expect(global.fetch).toHaveBeenCalledTimes(1);
});

test('invalidation discards outstanding reads and explicit reload publishes a full snapshot', async () => {
  const previous = process.env.REACT_APP_COMPANY_MATERIAL_ALIASES_ENABLED;
  process.env.REACT_APP_COMPANY_MATERIAL_ALIASES_ENABLED = '1';
  let finish;
  global.fetch = jest.fn().mockImplementationOnce(() => new Promise(resolve => {finish = resolve;}));
  const setMaterialAliases = jest.fn();
  const setMaterialAliasesError = jest.fn();
  const props = {API: '/api', companyContext: companyContext(2), projects: [], userId: 1, setMaterialAliases, setMaterialAliasesError};
  try {
    const {result, rerender, unmount} = renderHook(value => useOwnedAliasSnapshot(value), {initialProps: props});
    const reload = result.current.reloadOwnedAliases;
    let release;
    act(() => {release = result.current.invalidateOwnedAliases();});
    await act(async () => finish(response([common], 'old')));
    expect(setMaterialAliases).not.toHaveBeenCalledWith([common]);
    await act(async () => reload());
    expect(global.fetch).toHaveBeenCalledTimes(1);
    expect(result.current.getOwnedAliasSnapshotToken()).toBeNull();
    release();
    global.fetch.mockResolvedValue(response([], 'new'));
    rerender({...props, companyContext: companyContext(3)});
    expect(result.current.reloadOwnedAliases).toBe(reload);
    await act(async () => reload());
    await waitFor(() => expect(setMaterialAliasesError).toHaveBeenLastCalledWith(''));
    expect(global.fetch.mock.calls.at(-1)[0]).toContain('companyId=3');
    expect(result.current.getOwnedAliasSnapshotToken()).not.toBeNull();
    const calls = global.fetch.mock.calls.length;
    rerender({...props, companyContext: {...companyContext(3), loading: true}});
    expect(result.current.getOwnedAliasSnapshotToken()).toBeNull();
    expect(setMaterialAliases).toHaveBeenLastCalledWith([]);
    expect(global.fetch).toHaveBeenCalledTimes(calls);
    unmount();
  } finally {
    if (previous === undefined) delete process.env.REACT_APP_COMPANY_MATERIAL_ALIASES_ENABLED;
    else process.env.REACT_APP_COMPANY_MATERIAL_ALIASES_ENABLED = previous;
  }
});
