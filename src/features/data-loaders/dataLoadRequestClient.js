export const createDataLoadRequestClient = ({
  API,
  fetchImpl = fetch,
  logger = console,
  mobileApiRequestsRef,
  mobileLoadedScopesRef,
  setInitialDataLoaded,
  setUser,
  storage = localStorage,
}) => {
  const handleApiUnauthorized = () => {
    try {
      storage.removeItem('authToken');
      storage.removeItem('user');
    } catch (e) {}
    mobileLoadedScopesRef.current.clear();
    mobileApiRequestsRef.current.clear();
    setInitialDataLoaded(false);
    setUser(null);
  };

  const getApi = (path, fallback = []) => {
    if (mobileApiRequestsRef.current.has(path)) {
      return mobileApiRequestsRef.current.get(path);
    }

    const token = storage.getItem('authToken');
    const request = fetchImpl(
      API + path,
      token ? { headers: { Authorization: 'Bearer ' + token } } : undefined,
    )
      .then(response => {
        if (response.ok) return response.json();
        if (response.status === 401) handleApiUnauthorized();
        return fallback;
      })
      .catch(() => fallback)
      .finally(() => mobileApiRequestsRef.current.delete(path));

    mobileApiRequestsRef.current.set(path, request);
    return request;
  };

  const apiAuthHeaders = (headers = {}) => {
    const token = storage.getItem('authToken');
    return token ? { ...headers, Authorization: 'Bearer ' + token } : headers;
  };

  const loadMobileScopeOnce = async (scope, loader) => {
    if (
      mobileLoadedScopesRef.current.has('full')
      || mobileLoadedScopesRef.current.has(scope)
    ) {
      return;
    }

    mobileLoadedScopesRef.current.add(scope);
    try {
      await loader();
    } catch (error) {
      logger.error(`loadMobileScopeOnce failed: ${scope}`, error);
      mobileLoadedScopesRef.current.delete(scope);
    }
  };

  return {
    apiAuthHeaders,
    getApi,
    handleApiUnauthorized,
    loadMobileScopeOnce,
  };
};
