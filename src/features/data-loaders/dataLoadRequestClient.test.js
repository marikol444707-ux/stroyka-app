import { createDataLoadRequestClient } from './dataLoadRequestClient';

const createDeps = (overrides = {}) => {
  const storage = {
    getItem: jest.fn(key => key === 'authToken' ? 'token-123' : null),
    removeItem: jest.fn(),
  };
  const deps = {
    API: 'https://example.test',
    fetchImpl: jest.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => [{ id: 1 }],
    })),
    logger: { error: jest.fn() },
    mobileApiRequestsRef: { current: new Map() },
    mobileLoadedScopesRef: { current: new Set() },
    setInitialDataLoaded: jest.fn(),
    setUser: jest.fn(),
    storage,
  };
  return { ...deps, ...overrides };
};

describe('createDataLoadRequestClient', () => {
  it('adds authorization and clears the pending request after success', async () => {
    const deps = createDeps();
    const client = createDataLoadRequestClient(deps);

    await expect(client.getApi('/projects')).resolves.toEqual([{ id: 1 }]);

    expect(deps.fetchImpl).toHaveBeenCalledWith('https://example.test/projects', {
      headers: { Authorization: 'Bearer token-123' },
    });
    expect(deps.mobileApiRequestsRef.current.size).toBe(0);
  });

  it('deduplicates concurrent requests to the same path', async () => {
    let resolveFetch;
    const fetchImpl = jest.fn(() => new Promise(resolve => { resolveFetch = resolve; }));
    const deps = createDeps({ fetchImpl });
    const client = createDataLoadRequestClient(deps);

    const first = client.getApi('/materials');
    const second = client.getApi('/materials');

    expect(second).toBe(first);
    expect(fetchImpl).toHaveBeenCalledTimes(1);
    resolveFetch({ ok: true, status: 200, json: async () => [{ id: 2 }] });
    await expect(first).resolves.toEqual([{ id: 2 }]);
    expect(deps.mobileApiRequestsRef.current.size).toBe(0);
  });

  it('returns the fallback and resets the session on an unauthorized response', async () => {
    const deps = createDeps({
      fetchImpl: jest.fn(async () => ({ ok: false, status: 401 })),
    });
    deps.mobileApiRequestsRef.current.set('/pending', Promise.resolve());
    deps.mobileLoadedScopesRef.current.add('mobile:init');
    const client = createDataLoadRequestClient(deps);

    await expect(client.getApi('/projects', null)).resolves.toBeNull();

    expect(deps.storage.removeItem.mock.calls).toEqual([
      ['authToken'],
      ['user'],
    ]);
    expect(deps.mobileApiRequestsRef.current.size).toBe(0);
    expect(deps.mobileLoadedScopesRef.current.size).toBe(0);
    expect(deps.setInitialDataLoaded).toHaveBeenCalledWith(false);
    expect(deps.setUser).toHaveBeenCalledWith(null);
  });

  it('returns the fallback when the request fails', async () => {
    const deps = createDeps({
      fetchImpl: jest.fn(async () => { throw new Error('network'); }),
    });
    const client = createDataLoadRequestClient(deps);

    await expect(client.getApi('/projects', ['cached'])).resolves.toEqual(['cached']);
    expect(deps.mobileApiRequestsRef.current.size).toBe(0);
  });

  it('builds authenticated headers without discarding caller headers', () => {
    const deps = createDeps();
    const client = createDataLoadRequestClient(deps);

    expect(client.apiAuthHeaders({ 'Content-Type': 'application/json' })).toEqual({
      'Content-Type': 'application/json',
      Authorization: 'Bearer token-123',
    });

    deps.storage.getItem.mockReturnValue('');
    const originalHeaders = { Accept: 'application/json' };
    expect(client.apiAuthHeaders(originalHeaders)).toBe(originalHeaders);
  });

  it('runs each mobile scope once and makes a failed scope retryable', async () => {
    const deps = createDeps();
    const client = createDataLoadRequestClient(deps);
    const successfulLoader = jest.fn(async () => {});

    await client.loadMobileScopeOnce('materials', successfulLoader);
    await client.loadMobileScopeOnce('materials', successfulLoader);

    expect(successfulLoader).toHaveBeenCalledTimes(1);
    expect(deps.mobileLoadedScopesRef.current.has('materials')).toBe(true);

    const failure = new Error('failed');
    const failedLoader = jest.fn(async () => { throw failure; });
    await client.loadMobileScopeOnce('estimates', failedLoader);

    expect(deps.logger.error).toHaveBeenCalledWith(
      'loadMobileScopeOnce failed: estimates',
      failure,
    );
    expect(deps.mobileLoadedScopesRef.current.has('estimates')).toBe(false);
  });

  it('skips scoped mobile loading after the full dataset is loaded', async () => {
    const deps = createDeps();
    deps.mobileLoadedScopesRef.current.add('full');
    const client = createDataLoadRequestClient(deps);
    const loader = jest.fn(async () => {});

    await client.loadMobileScopeOnce('dashboard', loader);

    expect(loader).not.toHaveBeenCalled();
  });
});
