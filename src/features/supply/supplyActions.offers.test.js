import { createSupplyActions } from './supplyActions';

describe('selectSupplierOffer', () => {
  const originalFetch = global.fetch;
  beforeEach(() => {
    global.fetch = jest.fn();
    jest.spyOn(window, 'confirm').mockReturnValue(true);
    jest.spyOn(window, 'alert').mockImplementation(() => {});
  });
  afterEach(() => {
    global.fetch = originalFetch;
    jest.restoreAllMocks();
  });

  it.each([400, 403, 409, 422])('does not announce approval after HTTP %s', async status => {
    global.fetch.mockResolvedValue({ ok: false, status, json: async () => ({ detail: 'КП отклонено сервером' }) });
    const deps = { API: '/api', notify: jest.fn(), refreshData: jest.fn() };

    await createSupplyActions(deps).selectSupplierOffer(42);

    expect(window.alert).toHaveBeenCalledWith(expect.stringContaining('КП отклонено сервером'));
    expect(deps.notify).not.toHaveBeenCalled();
    expect(deps.refreshData).not.toHaveBeenCalled();
  });

  it('reports an HTTP failure even if the body is not JSON', async () => {
    global.fetch.mockResolvedValue({ ok: false, status: 502, json: async () => { throw new SyntaxError('HTML'); } });
    const deps = { API: '/api', notify: jest.fn(), refreshData: jest.fn() };

    await createSupplyActions(deps).selectSupplierOffer(42);

    expect(window.alert).toHaveBeenCalledWith(expect.stringContaining('502'));
    expect(deps.notify).not.toHaveBeenCalled();
  });

  it('announces approval and refreshes only after a successful response', async () => {
    global.fetch.mockResolvedValue({ ok: true, status: 200, json: async () => ({ id: 42, status: 'Утверждено' }) });
    const deps = { API: '/api', notify: jest.fn(), refreshData: jest.fn() };

    await createSupplyActions(deps).selectSupplierOffer(42);

    expect(JSON.parse(global.fetch.mock.calls[0][1].body)).toEqual({ action: 'select' });
    expect(deps.notify).toHaveBeenCalledWith('КП утверждено директором', 'supply');
    expect(deps.refreshData).toHaveBeenCalledTimes(1);
    expect(window.alert).not.toHaveBeenCalled();
  });
});
