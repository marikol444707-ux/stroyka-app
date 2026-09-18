import { useState } from 'react';
import { act, renderHook, waitFor } from '@testing-library/react';
import { useAppDataLoaders } from './useAppDataLoaders';
import { beginQualityJournalMutation, finishQualityJournalMutation, getQualityJournalMutationState, notifyQualityJournalMutation } from '../../utils/qualityJournalEvents';
import { qualityJournalLoadIssue, qualityJournalScopeKey } from '../../utils/qualityJournalScope';

const setter = () => jest.fn();
const snapshotHeaders = { get: name => name === 'X-Quality-Journal-Snapshot' ? 'owned-v1' : null };

const company = id => ({ mode: 'company', selectedCompanyId: id, companies: [{ companyId: id, role: 'директор' }] });
const journalRow = { id: 1, companyId: 2, projectId: 11, projectName: 'Школа', materialName: 'Кабель', cableBrand: 'ВВГ', quantity: 10, lengthReceived: 10 };
function useJournalHarness(companyContext, overrides = {}) {
  const [inspections, setMaterialInspections] = useState([journalRow]);
  const [cables, setCableJournal] = useState([journalRow]);
  const [qualityJournalLoadState, setQualityJournalLoadState] = useState({});
  const ctx = new Proxy({
    companyContext, API: '/api', user: { id: 1, role: 'директор' },
    setMaterialInspections, setCableJournal, setQualityJournalLoadState,
    activePage: 'warehouse', initialDataLoaded: false, materialNormSearch: '',
    buildPagedPath: path => path, canAccessRole: () => false,
    createMaterialsPageState: value => value, createMaterialNormsPageState: value => value,
    createWorkJournalPageState: value => value,
    mobileApiRequestsRef: { current: new Map() }, mobileLoadedScopesRef: { current: new Set() },
    mobileScopeForPage: page => `mobile:${page}`, normalizeEstimateList: rows => rows,
    roleFlagsForUser: () => ({ role: 'директор', canSeeProjectDocs: true, isWarehouseRole: true }),
    ...overrides,
  }, { get: (target, name) => name in target ? target[name] : String(name).startsWith('set') ? jest.fn() : undefined });
  return { ...useAppDataLoaders(ctx), inspections, cables, qualityJournalLoadState };
}

test.each([undefined, { get: () => null }, { get: () => 'legacy' }])('missing or unsupported snapshot proof blocks even an empty journal: %j', async headers => {
  global.fetch = jest.fn(async () => ({ ok: true, headers, json: async () => [] }));
  const { result } = renderHook(() => useJournalHarness(company(2)));
  await waitFor(() => expect(result.current.qualityJournalLoadState.inspections?.status).toBe('error'));
  for (const kind of ['inspections', 'cables']) {
    expect(result.current.qualityJournalLoadState[kind]).toMatchObject({ complete: false, error: expect.stringContaining('миграция') });
  }
  expect(result.current.inspections).toEqual([]);
  expect(result.current.cables).toEqual([]);
});

test('owned-v1 confirms an empty authorized subset without claiming all company rows', async () => {
  global.fetch = jest.fn(async () => ({ ok: true, headers: snapshotHeaders, json: async () => [] }));
  const { result } = renderHook(() => useJournalHarness(company(2)));
  await waitFor(() => expect(result.current.qualityJournalLoadState.cables?.complete).toBe(true));
  expect(result.current.qualityJournalLoadState.inspections).toMatchObject({ status: 'ready', complete: true });
});

test('journal 409 after success clears stale rows and surfaces incomplete error on desktop', async () => {
  global.fetch = jest.fn(async () => ({ ok: true, headers: snapshotHeaders, json: async () => [journalRow] }));
  const { result } = renderHook(() => useJournalHarness(company(2)));
  await waitFor(() => expect(result.current.qualityJournalLoadState.inspections?.status).toBe('ready'));
  global.fetch = jest.fn(async url => url.endsWith('/material-inspection')
    ? { ok: false, status: 409, json: async () => ({ detail: 'Уточните объект: журнал содержит более 5000 записей' }) }
    : { ok: true, headers: snapshotHeaders, json: async () => [] });
  await act(async () => { await result.current.loadAll(); });
  expect(result.current.inspections).toEqual([]);
  expect(result.current.qualityJournalLoadState.inspections).toMatchObject({ status: 'error', complete: false, error: expect.stringContaining('5000') });
});

test('mobile failure and malformed success are not empty ready snapshots', async () => {
  global.fetch = jest.fn(async () => ({ ok: true, headers: snapshotHeaders, json: async () => [] }));
  const { result } = renderHook(() => useJournalHarness(company(2)));
  await waitFor(() => expect(result.current.qualityJournalLoadState.cables?.complete).toBe(true));
  global.fetch = jest.fn(async url => {
    if (url.endsWith('/material-inspection')) throw new Error('offline');
    return { ok: true, headers: snapshotHeaders, json: async () => url.endsWith('/cable-journal') ? {} : [] };
  });
  await act(async () => { await result.current.refreshData('warehouse'); });
  expect(result.current.qualityJournalLoadState.inspections.status).toBe('error');
  expect(result.current.qualityJournalLoadState.cables.status).toBe('error');
  expect(result.current.inspections).toEqual([]); expect(result.current.cables).toEqual([]);
});

test('late old company responses cannot overwrite the new company snapshot', async () => {
  const resolveOld = [];
  global.fetch = jest.fn((url, options) => options.headers['X-Company-Id'] === '2'
    ? new Promise(resolve => resolveOld.push(resolve))
    : Promise.resolve({ ok: true, headers: snapshotHeaders, json: async () => [] }));
  const { result, rerender } = renderHook(({ context }) => useJournalHarness(context), { initialProps: { context: company(2) } });
  rerender({ context: company(3) });
  await waitFor(() => expect(result.current.qualityJournalLoadState.inspections?.status).toBe('ready'));
  const scopeKey = result.current.qualityJournalLoadState.inspections.scopeKey;
  await act(async () => { resolveOld.forEach(resolve => resolve({ ok: true, headers: snapshotHeaders, json: async () => [journalRow] })); });
  expect(result.current.inspections).toEqual([]);
  expect(result.current.qualityJournalLoadState.inspections.scopeKey).toBe(scopeKey);
});

test('latest request wins within a company and 403 disables old data', async () => {
  const old = [];
  global.fetch = jest.fn(() => new Promise(resolve => old.push(resolve)));
  const { result } = renderHook(() => useJournalHarness(company(2)));
  global.fetch = jest.fn(async () => ({ ok: false, status: 403, json: async () => ({ detail: 'Доступ отозван' }) }));
  await act(async () => { await result.current.reloadQualityJournals(); });
  await act(async () => { old.forEach(resolve => resolve({ ok: true, headers: snapshotHeaders, json: async () => [journalRow] })); });
  expect(result.current.qualityJournalLoadState.inspections).toMatchObject({ status: 'denied', complete: false });
  expect(result.current.inspections).toEqual([]);
});

test('logout or all-company mode immediately invalidates journal snapshots without fetching', async () => {
global.fetch = jest.fn(async () => ({ ok: true, headers: snapshotHeaders, json: async () => [journalRow] }));
  const { result, rerender } = renderHook(({ context }) => useJournalHarness(context), { initialProps: { context: company(2) } });
  await waitFor(() => expect(result.current.inspections).toHaveLength(1));
  const count = global.fetch.mock.calls.length;
  rerender({ context: { mode: 'all_companies' } });
  await waitFor(() => expect(result.current.qualityJournalLoadState.inspections.status).toBe('denied'));
  expect(result.current.inspections).toEqual([]);
  expect(global.fetch).toHaveBeenCalledTimes(count);
});

test('malformed journal rows cannot be stamped complete', async () => {
  global.fetch = jest.fn(async () => ({ ok: true, headers: snapshotHeaders, json: async () => [{ id: 1 }] }));
  const { result } = renderHook(() => useJournalHarness(company(2)));
  await waitFor(() => expect(result.current.qualityJournalLoadState.inspections?.status).toBe('error'));
  expect(result.current.qualityJournalLoadState.inspections.complete).toBe(false);
});

test.each([
  { companyId: undefined, projectId: undefined },
  { companyId: 2, projectId: null }, { companyId: null, projectId: 11 },
  { companyId: 3, projectId: 11 }, { companyId: 2, projectId: 0 },
  { companyId: 2, projectId: 'invalid' },
])('unowned/partial/foreign response blocks company completeness: %j', ownership => {
  global.fetch = jest.fn(async () => ({ ok: true, headers: snapshotHeaders, json: async () => [{ ...journalRow, ...ownership }] }));
  return (async () => {
    const { result } = renderHook(() => useJournalHarness(company(2)));
    await waitFor(() => expect(result.current.qualityJournalLoadState.inspections?.status).toBe('error'));
    for (const kind of ['inspections', 'cables']) {
      expect(result.current.qualityJournalLoadState[kind]).toMatchObject({ complete: false, error: expect.stringContaining('миграция') });
    }
    expect(result.current.inspections).toEqual([]); expect(result.current.cables).toEqual([]);
  })();
});

test('confirmed mutation invalidates in-flight GET and reloads the current company', async () => {
  const beforeMutation = [];
  global.fetch = jest.fn(() => new Promise(resolve => beforeMutation.push(resolve)));
  const { result } = renderHook(() => useJournalHarness(company(2)));
  const confirmed = { ...journalRow, quantity: 12, lengthReceived: 12 };
  const afterMutation = [];
  global.fetch = jest.fn(() => new Promise(resolve => afterMutation.push(resolve)));
  act(() => { notifyQualityJournalMutation(); });
  expect(global.fetch).toHaveBeenCalledTimes(2);
  expect(result.current.qualityJournalLoadState.inspections.complete).toBe(false);
  await act(async () => { beforeMutation.forEach(resolve => resolve({ ok: true, headers: snapshotHeaders, json: async () => [journalRow] })); });
  expect(result.current.inspections).toEqual([]);
  expect(result.current.qualityJournalLoadState.inspections.status).toBe('loading');
  await act(async () => { afterMutation.forEach(resolve => resolve({ ok: true, headers: snapshotHeaders, json: async () => [confirmed] })); });
  expect(result.current.inspections).toEqual([confirmed]);
  expect(result.current.qualityJournalLoadState.inspections.complete).toBe(true);
});

test('mutation reload preserves rows for onSuccess map while completeness is false', async () => {
  global.fetch = jest.fn(async () => ({ ok: true, headers: snapshotHeaders, json: async () => [journalRow] }));
  const { result } = renderHook(() => useJournalHarness(company(2)));
  await waitFor(() => expect(result.current.qualityJournalLoadState.inspections?.complete).toBe(true));
  const replies = [];
  global.fetch = jest.fn(() => new Promise(resolve => replies.push(resolve)));
  act(() => { notifyQualityJournalMutation(); });
  expect(result.current.inspections).toEqual([journalRow]);
  expect(result.current.qualityJournalLoadState.inspections.complete).toBe(false);
  await act(async () => { replies.forEach(resolve => resolve({ ok: false, status: 409, json: async () => ({ detail: 'Повторите загрузку' }) })); });
  expect(result.current.inspections).toEqual([]);
  expect(result.current.qualityJournalLoadState.inspections.status).toBe('error');
});

test('pending writes invalidate old GETs but defer reload until every write settles', async () => {
  const old = [];
  global.fetch = jest.fn(() => new Promise(resolve => old.push(resolve)));
  const { result } = renderHook(() => useJournalHarness(company(2)));
  let first; let second;
  act(() => { first = beginQualityJournalMutation(); second = beginQualityJournalMutation(); });
  expect(global.fetch).toHaveBeenCalledTimes(2);
  await act(async () => { old.forEach(resolve => resolve({ ok: true, headers: snapshotHeaders, json: async () => [journalRow] })); });
  expect(result.current.qualityJournalLoadState.inspections.complete).toBe(false);
  expect(result.current.inspections).toEqual([]);
  await act(async () => { await result.current.reloadQualityJournals(); });
  expect(global.fetch).toHaveBeenCalledTimes(2);
  act(() => { finishQualityJournalMutation(first, { confirmed: true, uncertain: false }); });
  expect(global.fetch).toHaveBeenCalledTimes(2);
  global.fetch = jest.fn(async () => ({ ok: true, headers: snapshotHeaders, json: async () => [journalRow] }));
  act(() => { finishQualityJournalMutation(second, { confirmed: false, uncertain: false }); });
  await waitFor(() => expect(result.current.qualityJournalLoadState.inspections.complete).toBe(true));
  expect(global.fetch).toHaveBeenCalledTimes(2);
});

test('refreshing the warehouse reloads tools, tool history and inventory', async () => {
  const setTools = setter();
  const setToolHistory = setter();
  const setInventory = setter();
  global.fetch = jest.fn(async url => ({ok: true, headers: snapshotHeaders, json: async () => [{id: url}]}));

  const {result} = renderHook(() => useAppDataLoaders({
    activePage: 'warehouse',
    API: '/api',
    AUDIT_LOG_PAGE_LIMIT: 50,
    buildPagedPath: path => path,
    canAccessRole: () => false,
    createMaterialNormsPageState: value => value,
    createMaterialsPageState: value => value,
    createWorkJournalPageState: value => value,
    estimatesTab: 'list',
    initialDataLoaded: false,
    MATERIAL_NORMS_PAGE_LIMIT: 100,
    materialNormSearch: '',
    MATERIALS_PAGE_LIMIT: 100,
    mergeRowsByIdValue: (_current, incoming) => incoming,
    mobileApiRequestsRef: {current: new Map()},
    mobileLoadedScopesRef: {current: new Set()},
    mobileScopeForPage: page => `mobile:${page}`,
    normalizeEstimateList: rows => rows,
    roleFlagsForUser: () => ({
      role: 'директор', isLeadershipRole: true, isFinanceRole: false,
      isWarehouseRole: true, isSupplyRole: true, canSeeSupplierInvoices: true,
      isInternalRole: true, canSeeProjectDocs: true,
    }),
    ROLES: {},
    setMaterials: setter(), setMaterialsPage: setter(), setInvoices: setter(),
    setWarehouseMain: setter(), setWarehouseMovements: setter(), setHistory: setter(),
    setWarehouses: setter(), setMaterialTransfers: setter(), setMaterialInspections: setter(),
    setCableJournal: setter(), setSupplyRequests: setter(), setSupplyHistory: setter(),
    setSupplyDeliveries: setter(), setTools, setToolHistory, setInventory,
    setEstimatesPage: setter(), setInitialDataLoaded: setter(), setUser: setter(),
    user: {id: 1, role: 'директор'},
    WORK_JOURNAL_PAGE_LIMIT: 100,
  }));

  await act(async () => {
    await result.current.refreshData('warehouse');
  });

  const paths = global.fetch.mock.calls.map(([url]) => url);
  expect(paths).toEqual(expect.arrayContaining(['/api/tools', '/api/tool-history', '/api/inventory']));
  expect(setTools).toHaveBeenCalledWith([{id: '/api/tools'}]);
  expect(setToolHistory).toHaveBeenCalledWith([{id: '/api/tool-history'}]);
  expect(setInventory).toHaveBeenCalledWith([{id: '/api/inventory'}]);
});

test('loading settings hydrates both document data and the editable requisites form', async () => {
  const requisites = {
    companyId: 42,
    fullName: 'ООО Клиент',
    inn: '1234567890',
    directorName: 'Иван Петров',
  };
  const setCompanyRequisites = setter();
  const setCompanyReqForm = setter();
  global.fetch = jest.fn(async url => ({
    ok: true,
    json: async () => url.endsWith('/company-requisites') ? requisites : [],
  }));

  const {result} = renderHook(() => useAppDataLoaders({
    activePage: 'settings',
    API: '/api',
    canAccessRole: () => false,
    initialDataLoaded: true,
    mobileApiRequestsRef: {current: new Map()},
    mobileLoadedScopesRef: {current: new Set()},
    mobileScopeForPage: page => `mobile:${page}`,
    roleFlagsForUser: () => ({role: 'директор', isFinanceRole: true}),
    ROLES: {},
    setCompanyDocuments: setter(),
    setCompanyRequisites,
    setCompanyReqForm,
    setInitialDataLoaded: setter(),
    setUser: setter(),
    user: {id: 1, role: 'директор'},
  }));

  await act(async () => {
    await result.current.refreshData('settings');
  });

  expect(setCompanyRequisites).toHaveBeenCalledWith(requisites);
  expect(setCompanyReqForm).toHaveBeenCalledWith(expect.objectContaining({
    fullName: 'ООО Клиент',
    inn: '1234567890',
    directorName: 'Иван Петров',
    basis: 'Устава',
  }));
});

test.each(['1', '0'])('first master works load hydrates warehouse stock, norms and history only with accounting flag=%s', async flag => {
  const previous = process.env.REACT_APP_WORK_MATERIAL_ACCOUNTING_ENABLED;
  process.env.REACT_APP_WORK_MATERIAL_ACCOUNTING_ENABLED = flag;
  const rowsByPath = {
    '/api/materials': [{ id: 41, project: 'Школа', name: 'Кабель', unit: 'м', quantity: 1, workPackage: 'Основная' }],
    '/api/material-norms': [{ id: 51, workName: 'Монтаж', materialName: 'Кабель', quantity: 2 }],
    '/api/material-norms/overrides': [{ id: 61, project: 'Школа', normId: 51, quantity: 3 }],
    '/api/warehouse-history': [{ id: 71, material: 'Кабель', project: 'Школа', type: 'возврат', quantity: 1 }],
    '/api/material-transfers': [{ id: 81, projectName: 'Школа', toUserId: 7, materialName: 'Кабель', quantity: 1, signed: true }],
  };
  const setters = {
    setMaterials: setter(), setMaterialNorms: setter(), setMaterialNormOverrides: setter(),
    setHistory: setter(), setMaterialTransfers: setter(),
  };
  global.fetch = jest.fn(async url => ({ ok: true, headers: snapshotHeaders,
    json: async () => rowsByPath[String(url).split('?')[0]] || [],
  }));
  const context = { ...company(2), companies: [{ companyId: 2, role: 'мастер' }] };
  let unmount;
  try {
    const hook = renderHook(() => useJournalHarness(context, {
      ...setters, activePage: 'works', initialDataLoaded: false,
      user: { id: 7, role: 'мастер', name: 'Мастер' }, ROLES: {},
      MATERIALS_PAGE_LIMIT: 100, MATERIAL_NORMS_PAGE_LIMIT: 100, WORK_JOURNAL_PAGE_LIMIT: 100,
      roleFlagsForUser: () => ({ role: 'мастер', canSeeProjectDocs: true, isInternalRole: true }),
    }));
    unmount = hook.unmount;
    // This is the first page load, without first visiting warehouse or estimates.
    await act(async () => { await hook.result.current.refreshData('works'); });
    expect(setters.setMaterialTransfers).toHaveBeenCalledWith(rowsByPath['/api/material-transfers']);
    const paths = global.fetch.mock.calls.map(([url]) => String(url).split('?')[0]);
    for (const [setterName, path] of [['setMaterials', '/api/materials'], ['setMaterialNorms', '/api/material-norms'],
      ['setMaterialNormOverrides', '/api/material-norms/overrides'], ['setHistory', '/api/warehouse-history']]) {
      if (flag === '1') {
        expect(paths).toContain(path);
        expect(setters[setterName]).toHaveBeenCalledWith(rowsByPath[path]);
      } else {
        expect(paths).not.toContain(path);
        expect(setters[setterName]).not.toHaveBeenCalled();
      }
    }
  } finally {
    unmount?.();
    if (previous === undefined) delete process.env.REACT_APP_WORK_MATERIAL_ACCOUNTING_ENABLED;
    else process.env.REACT_APP_WORK_MATERIAL_ACCOUNTING_ENABLED = previous;
  }
});

test('uncertain write stays blocked through manual reload, remount and another confirmed save', async () => {
  global.fetch = jest.fn(async () => ({ ok: true, headers: snapshotHeaders, json: async () => [journalRow] }));
  const { result, unmount } = renderHook(() => useJournalHarness(company(2)));
  await waitFor(() => expect(result.current.qualityJournalLoadState.inspections.complete).toBe(true));
  let token;
  act(() => { token = beginQualityJournalMutation(); });
  expect(result.current.inspections).toEqual([journalRow]);
  expect(result.current.qualityJournalLoadState.inspections.complete).toBe(false);
  act(() => { finishQualityJournalMutation(token, { confirmed: false, uncertain: true }); });
  const calls = global.fetch.mock.calls.length;
  await act(async () => { await result.current.reloadQualityJournals(); });
  act(() => {
    const other = beginQualityJournalMutation();
    finishQualityJournalMutation(other, { confirmed: true, uncertain: false });
    notifyQualityJournalMutation();
  });
  expect(global.fetch).toHaveBeenCalledTimes(calls);
  expect(getQualityJournalMutationState()).toMatchObject({ pendingCount: 0, uncertain: true });
  expect(result.current.qualityJournalLoadState.inspections).toMatchObject({ complete: false, error: expect.stringMatching(/провер/i) });
  const ready = { scopeKey: qualityJournalScopeKey(company(2), { id: 1 }), revision: getQualityJournalMutationState().revision, complete: true, status: 'ready' };
  expect(qualityJournalLoadIssue({ inspections: ready, cables: ready }, { id: 11, companyId: 2 }, company(2), { id: 1 })).toMatch(/провер/i);
  unmount();
  const { result: remountedResult } = renderHook(() => useJournalHarness(company(2)));
  await waitFor(() => expect(remountedResult.current.qualityJournalLoadState.inspections.complete).toBe(false));
  expect(global.fetch).toHaveBeenCalledTimes(calls);
});
