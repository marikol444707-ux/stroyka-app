import { useCallback, useEffect } from 'react';
import { createDataLoadRequestClient } from './dataLoadRequestClient';
import { createDataLoadPolicy } from './dataLoadPolicy';
import { createFullDataLoader } from './fullDataLoader';
import { createMobileInitialDataLoader } from './mobileInitialDataLoader';
import { createMobilePageDataLoader } from './mobilePageDataLoader';

export const useAppDataLoaders = (ctx) => {
  const {
    activePage, API, buildPagedPath, canAccessRole, createMaterialNormsPageState,
    createMaterialsPageState, createWorkJournalPageState, estimatesTab, initialDataLoaded, MATERIAL_NORMS_PAGE_LIMIT, materialNormSearch,
    MATERIALS_PAGE_LIMIT, mergeRowsByIdValue, mobileApiRequestsRef, mobileLoadedScopesRef, mobileScopeForPage, normalizeEstimateList, roleFlagsForUser,
    ROLES, setEstimatesList, setEstimatesPage, setInitialDataLoaded,
    setMaterialNorms, setMaterialNormsPage, setMaterials, setMaterialsPage,
    setUser, setWorkJournal, setWorkJournalPage,
    user, WORK_JOURNAL_PAGE_LIMIT,
  } = ctx;

  const dataLoadPolicyForUser = (targetUser = user) => {
    const flags = roleFlagsForUser(targetUser);
    return createDataLoadPolicy({
      flags,
      canAccessEstimates: canAccessRole(targetUser, 'estimates', ROLES),
    });
  };
  const markEstimatesLoading = (enabled) => {
    setEstimatesPage(prev => ({...prev, loading:enabled, error:enabled ? '' : prev.error}));
  };
  const applyLoadedEstimates = (payload, expectLoad = true) => {
    if (Array.isArray(payload)) {
      setEstimatesList(normalizeEstimateList(payload));
      setEstimatesPage({loading:false, error:''});
      return;
    }
    if (expectLoad) {
      setEstimatesPage({
        loading:false,
        error:'Не удалось загрузить сметы. Проверьте соединение или повторите загрузку.',
      });
    }
  };
  const {
    apiAuthHeaders,
    getApi,
    handleApiUnauthorized,
    loadMobileScopeOnce,
  } = createDataLoadRequestClient({
    API,
    mobileApiRequestsRef,
    mobileLoadedScopesRef,
    setInitialDataLoaded,
    setUser,
  });

  const pagedPath = (path, params = {}) => buildPagedPath(path, params);

  const mergeRowsById = (current = [], incoming = []) => mergeRowsByIdValue(current, incoming);

  const loadMaterialsPage = useCallback(async ({projectName = '', search = '', offset = 0} = {}) => {
    setMaterialsPage(prev => ({...prev, projectName, search, loading:true, error:''}));
    try {
      const data = await getApi(pagedPath('/materials', {
        project_name: projectName,
        search,
        limit: MATERIALS_PAGE_LIMIT,
        offset,
      }), []);
      const rows = Array.isArray(data) ? data : [];
      setMaterials(prev => mergeRowsById(prev, rows));
      setMaterialsPage({
        projectName,
        search,
        hasMore: rows.length === MATERIALS_PAGE_LIMIT,
        loading:false,
        error:'',
      });
      return rows;
    } catch (e) {
      setMaterialsPage(prev => ({...prev, loading:false, error:'Не удалось загрузить материалы'}));
      return [];
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const loadMaterialNormsPage = useCallback(async ({search = '', offset = 0} = {}) => {
    setMaterialNormsPage(prev => ({...prev, search, loading:true, error:''}));
    try {
      const data = await getApi(pagedPath('/material-norms', {
        search,
        limit: MATERIAL_NORMS_PAGE_LIMIT,
        offset,
      }), []);
      const rows = Array.isArray(data) ? data : [];
      setMaterialNorms(prev => mergeRowsById(prev, rows));
      setMaterialNormsPage({
        search,
        hasMore: rows.length === MATERIAL_NORMS_PAGE_LIMIT,
        loading:false,
        error:'',
      });
      return rows;
    } catch (e) {
      setMaterialNormsPage(prev => ({...prev, loading:false, error:'Не удалось загрузить нормы'}));
      return [];
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const workJournalPageState = (params = {}) => createWorkJournalPageState(params, WORK_JOURNAL_PAGE_LIMIT);

  const loadWorkJournalPage = useCallback(async ({projectName = '', search = '', dateFrom = '', dateTo = '', offset = 0} = {}) => {
    setWorkJournalPage(prev => ({...prev, projectName, search, dateFrom, dateTo, loading:true, error:''}));
    try {
      const data = await getApi(pagedPath('/work-journal', {
        project_name: projectName,
        search,
        date_from: dateFrom,
        date_to: dateTo,
        limit: WORK_JOURNAL_PAGE_LIMIT,
        offset,
      }), []);
      const rows = Array.isArray(data) ? data : [];
      setWorkJournal(prev => mergeRowsById(prev, rows));
      setWorkJournalPage(workJournalPageState({
        projectName,
        search,
        dateFrom,
        dateTo,
        rows,
        loading:false,
        error:'',
      }));
      return rows;
    } catch (e) {
      setWorkJournalPage(prev => ({...prev, loading:false, error:'Не удалось загрузить ЖПР'}));
      return [];
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const resetWorkJournalPage = (rows = []) => {
    setWorkJournalPage(workJournalPageState({
      rows,
      loading:false,
      error:'',
    }));
  };

  const resetMaterialNormsPage = (rows = []) => {
    setMaterialNormsPage(createMaterialNormsPageState({rows, loading:false, error:''}, MATERIAL_NORMS_PAGE_LIMIT));
  };

  const resetMaterialsPage = (rows = []) => {
    setMaterialsPage(createMaterialsPageState({rows, loading:false, error:''}, MATERIALS_PAGE_LIMIT));
  };

  useEffect(() => {
    if (!user || activePage !== 'estimates' || estimatesTab !== 'norms') return undefined;
    const search = materialNormSearch.trim();
    const timer = setTimeout(() => {
      loadMaterialNormsPage({search, offset: 0});
    }, search ? 300 : 0);
    return () => clearTimeout(timer);
  }, [user, activePage, estimatesTab, materialNormSearch, loadMaterialNormsPage]);

  const loadMobileInitial = createMobileInitialDataLoader({
    ...ctx,
    dataLoadPolicyForUser,
    getApi,
    pagedPath,
    loadMobileScopeOnce,
    resetWorkJournalPage,
    applyLoadedEstimates,
  });

  const loadMobilePageData = createMobilePageDataLoader({
    ...ctx,
    dataLoadPolicyForUser,
    getApi,
    pagedPath,
    loadMobileScopeOnce,
    markEstimatesLoading,
    applyLoadedEstimates,
    resetWorkJournalPage,
    resetMaterialsPage,
    resetMaterialNormsPage,
  });

  useEffect(() => {
    if (!user) return undefined;
    if (!initialDataLoaded) return undefined;
    const run = () => loadMobilePageData(activePage);
    if (typeof window !== 'undefined' && typeof window.requestIdleCallback === 'function') {
      const id = window.requestIdleCallback(run, {timeout: 1200});
      return () => window.cancelIdleCallback?.(id);
    }
    const id = setTimeout(run, 250);
    return () => clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, activePage, initialDataLoaded]);

  const loadAll = createFullDataLoader({
    ...ctx,
    dataLoadPolicyForUser,
    pagedPath,
    markEstimatesLoading,
    applyLoadedEstimates,
    resetWorkJournalPage,
    resetMaterialsPage,
    resetMaterialNormsPage,
    handleApiUnauthorized,
  });

  const refreshData = async (page = activePage) => {
    mobileApiRequestsRef.current.clear();
    mobileLoadedScopesRef.current.delete('full');
    const scope = mobileScopeForPage(page);
    if (scope) mobileLoadedScopesRef.current.delete(scope);
    if (page === 'dashboard') {
      mobileLoadedScopesRef.current.delete('mobile:init');
      await loadMobileInitial();
    }
    await loadMobilePageData(page);
  };

  return {
    apiAuthHeaders, loadAll, loadMaterialNormsPage, loadMaterialsPage, loadMobileInitial, loadWorkJournalPage,
    refreshData,
  };
};
