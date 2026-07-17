import { useCallback, useEffect } from 'react';
import { createDataLoadRequestClient } from './dataLoadRequestClient';
import { createDataLoadPolicy } from './dataLoadPolicy';
import { createFullDataLoader } from './fullDataLoader';
import { createMobileInitialDataLoader } from './mobileInitialDataLoader';
import { createMobilePageDataLoader } from './mobilePageDataLoader';
import { createPagedDataLoaders } from './pagedDataLoaders';

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

  const pagedDataLoaders = createPagedDataLoaders({
    MATERIAL_NORMS_PAGE_LIMIT,
    MATERIALS_PAGE_LIMIT,
    WORK_JOURNAL_PAGE_LIMIT,
    createMaterialNormsPageState,
    createMaterialsPageState,
    createWorkJournalPageState,
    getApi,
    mergeRowsById: mergeRowsByIdValue,
    pagedPath,
    setMaterialNorms,
    setMaterialNormsPage,
    setMaterials,
    setMaterialsPage,
    setWorkJournal,
    setWorkJournalPage,
  });
  // Preserve stable loader references for effects and paged list components.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const loadMaterialsPage = useCallback(pagedDataLoaders.loadMaterialsPage, []);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const loadMaterialNormsPage = useCallback(pagedDataLoaders.loadMaterialNormsPage, []);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const loadWorkJournalPage = useCallback(pagedDataLoaders.loadWorkJournalPage, []);
  const {
    resetMaterialNormsPage,
    resetMaterialsPage,
    resetWorkJournalPage,
  } = pagedDataLoaders;

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
