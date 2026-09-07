import { act, renderHook } from '@testing-library/react';
import { createSupplyActions } from './supplyActions';
import { useSupplyWorkflowState } from './useSupplyWorkflowState';
import { buildAppActionGroups } from '../app-shell/buildAppActionGroups';

const deferred = () => {
  let resolve;
  const promise = new Promise(done => { resolve = done; });
  return { promise, resolve };
};
const response = (body, ok = true) => ({ ok, status: ok ? 200 : 409, json: async () => body });
const context = (overrides = {}) => ({
  API: '/api', companyContext: { mode: 'company', selectedCompanyId: 4 },
  user: { id: 7, name: 'Директор', role: 'директор' },
  getProjectWorkPackageOptions: () => [],
  newRequest: { project: 'Лицей', items: [{ materialName: 'Труба', quantity: 10 }], selectedSuppliers: [] },
  newSupplyReq: { project: 'Лицей', items: [{ materialName: 'Труба', quantity: 10 }] },
  notify: jest.fn(), refreshData: jest.fn().mockResolvedValue(),
  setNewRequest: jest.fn(), setShowForm: jest.fn(),
  setNewSupplyReq: jest.fn(), setShowSupplyForm: jest.fn(),
  supplyRequestCreationRef: { current: false },
  ...overrides,
});

describe('request creation in-flight protection', () => {
  const originalFetch = global.fetch;
  beforeEach(() => {
    global.fetch = jest.fn();
    jest.spyOn(window, 'alert').mockImplementation(() => {});
  });
  afterEach(() => { global.fetch = originalFetch; jest.restoreAllMocks(); });

  it.each(['saveRequest', 'createSupplyReq'])('sends one POST during concurrent %s calls and factory recreation', async method => {
    const pending = deferred();
    global.fetch.mockReturnValue(pending.promise);
    const deps = context();
    const first = createSupplyActions(deps)[method]();
    const second = createSupplyActions(deps)[method]();
    expect(global.fetch).toHaveBeenCalledTimes(1);
    expect(deps.supplyRequestCreationRef.current).toBe(true);
    pending.resolve(response({ id: 31, status: 'Новая' }));
    await Promise.all([first, second]);
    expect(deps.supplyRequestCreationRef.current).toBe(false);
    expect(deps.refreshData).toHaveBeenCalledTimes(1);
  });

  it('shares the same guard across both request forms, but not independent app instances', async () => {
    const pending = deferred();
    global.fetch.mockReturnValue(pending.promise);
    const deps = context();
    const first = createSupplyActions(deps).saveRequest();
    const duplicate = createSupplyActions(deps).createSupplyReq();
    const independent = createSupplyActions(context()).createSupplyReq();
    expect(global.fetch).toHaveBeenCalledTimes(2);
    pending.resolve(response({ id: 31, status: 'Новая' }));
    await Promise.all([first, duplicate, independent]);
  });

  it('keeps the guard stable across workflow hook rerenders', async () => {
    const { result, rerender } = renderHook(() => useSupplyWorkflowState());
    const ref = result.current.supplyRequestCreationRef;
    expect(ref).toEqual({ current: false });
    const pending = deferred();
    global.fetch.mockReturnValue(pending.promise);
    const first = createSupplyActions(context({ supplyRequestCreationRef: ref })).saveRequest();
    act(() => { result.current.setSupplyTab('all'); });
    rerender();
    expect(result.current.supplyRequestCreationRef).toBe(ref);
    const second = createSupplyActions(context({ supplyRequestCreationRef: result.current.supplyRequestCreationRef })).saveRequest();
    expect(global.fetch).toHaveBeenCalledTimes(1);
    pending.resolve(response({ id: 31, status: 'Новая' }));
    await Promise.all([first, second]);
  });

  it('passes the stable workflow guard through the real app action builder', async () => {
    const deps = context();
    const build = () => buildAppActionGroups({
      API: deps.API, user: deps.user, companyContext: deps.companyContext,
      constants: { ROLE_LABELS: {} },
      appMainState: deps, supplyWorkflowState: deps, coreRuntime: deps,
      businessRuntime: deps,
    });
    const pending = deferred();
    global.fetch.mockReturnValue(pending.promise);
    const first = build().supplyActions.saveRequest();
    const duplicate = build().supplyActions.createSupplyReq();
    expect(global.fetch).toHaveBeenCalledTimes(1);
    pending.resolve(response({ id: 31, status: 'Новая' }));
    await Promise.all([first, duplicate]);
  });

  it.each(['saveRequest', 'createSupplyReq'])('retains the draft and releases %s after a rejected HTTP response', async method => {
    const deps = context();
    global.fetch.mockResolvedValueOnce(response({ detail: 'Заявка уже существует' }, false))
      .mockResolvedValueOnce(response({ id: 32, status: 'Новая' }));
    await createSupplyActions(deps)[method]();
    expect(deps.setNewRequest).not.toHaveBeenCalled();
    expect(deps.setNewSupplyReq).not.toHaveBeenCalled();
    expect(deps.notify).not.toHaveBeenCalled();
    expect(deps.supplyRequestCreationRef.current).toBe(false);
    await createSupplyActions(deps)[method]();
    expect(global.fetch).toHaveBeenCalledTimes(2);
    expect(deps.refreshData).toHaveBeenCalledTimes(1);
  });

  it.each(['saveRequest', 'createSupplyReq'])('handles ambiguous network failure without retrying %s automatically', async method => {
    const deps = context();
    global.fetch.mockRejectedValue(new Error('network unavailable'));
    await expect(createSupplyActions(deps)[method]()).resolves.toBeUndefined();
    expect(global.fetch).toHaveBeenCalledTimes(1);
    expect(deps.supplyRequestCreationRef.current).toBe(false);
    expect(deps.setNewRequest).not.toHaveBeenCalled();
    expect(deps.setNewSupplyReq).not.toHaveBeenCalled();
    expect(deps.notify).not.toHaveBeenCalled();
    expect(window.alert).toHaveBeenCalledWith(expect.stringContaining('Проверьте список заявок'));
  });

  it.each(['saveRequest', 'createSupplyReq'])('retains the draft when %s returns no confirmed request ID', async method => {
    const deps = context();
    global.fetch.mockResolvedValue(response({}));
    await createSupplyActions(deps)[method]();
    expect(deps.setNewRequest).not.toHaveBeenCalled();
    expect(deps.setNewSupplyReq).not.toHaveBeenCalled();
    expect(deps.notify).not.toHaveBeenCalled();
    expect(deps.supplyRequestCreationRef.current).toBe(false);
    expect(window.alert).toHaveBeenCalledWith(expect.stringContaining('Проверьте список заявок'));
  });

  it.each(['saveRequest', 'createSupplyReq'])('does not retain a successfully saved draft when list refresh fails: %s', async method => {
    const deps = context({ refreshData: jest.fn().mockRejectedValue(new Error('offline')) });
    global.fetch.mockResolvedValue(response({ id: 31, status: 'Новая' }));
    await expect(createSupplyActions(deps)[method]()).resolves.toBeUndefined();
    const reset = method === 'saveRequest' ? deps.setNewRequest : deps.setNewSupplyReq;
    const close = method === 'saveRequest' ? deps.setShowForm : deps.setShowSupplyForm;
    expect(reset).toHaveBeenCalledTimes(1);
    expect(close).toHaveBeenCalledWith(false);
    expect(global.fetch).toHaveBeenCalledTimes(1);
    expect(window.alert).toHaveBeenCalledWith(expect.stringContaining('Заявка создана, но список не обновился'));
    expect(deps.supplyRequestCreationRef.current).toBe(false);
  });
});
