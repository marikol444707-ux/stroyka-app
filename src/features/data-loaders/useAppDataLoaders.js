import { useCallback, useEffect } from 'react';
import { createDataLoadPolicy } from './dataLoadPolicy';
import { createFullDataLoader } from './fullDataLoader';
import { createMobilePageDataLoader } from './mobilePageDataLoader';

export const useAppDataLoaders = (ctx) => {
  const {
    activePage, API, buildPagedPath, canAccessRole, createMaterialNormsPageState,
    createMaterialsPageState, createWorkJournalPageState, estimatesTab, initialDataLoaded, MATERIAL_NORMS_PAGE_LIMIT, materialNormSearch,
    MATERIALS_PAGE_LIMIT, mergeRowsByIdValue, mobileApiRequestsRef, mobileLoadedScopesRef, mobileScopeForPage, normalizeEstimateList, roleFlagsForUser,
    ROLES, setAiTasks, setAllBrigadeItems, setBrigadeContracts, setCableJournal, setContracts,
    setEstimateReconciliations, setEstimatesList, setEstimatesPage, setHiddenActs, setInitialDataLoaded,
    setInterimActs, setMasterProfiles, setMaterialInspections, setMaterialNorms, setMaterialNormsPage,
    setMaterials, setMaterialsPage, setOwnExpenses, setPiecework, setProjectDocuments,
    setProjectMeasurements, setProjectPayments, setProjects, setStaff, setSupervisorActs,
    setSupplyRequests, setUser, setUsers, setWarehouseMain, setWorkJournal, setWorkJournalPage,
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
  const handleApiUnauthorized = () => {
    try {
      localStorage.removeItem('authToken');
      localStorage.removeItem('user');
    } catch (e) {}
    mobileLoadedScopesRef.current.clear();
    mobileApiRequestsRef.current.clear();
    setInitialDataLoaded(false);
    setUser(null);
  };

  const getApi = (path, fallback = []) => {
    if (mobileApiRequestsRef.current.has(path)) return mobileApiRequestsRef.current.get(path);
    const token = localStorage.getItem('authToken');
    const request = fetch(API + path, token ? {headers: {Authorization: 'Bearer ' + token}} : undefined)
      .then(r => {
        if (r.ok) return r.json();
        if (r.status === 401) handleApiUnauthorized();
        return fallback;
      })
      .catch(() => fallback)
      .finally(() => mobileApiRequestsRef.current.delete(path));
    mobileApiRequestsRef.current.set(path, request);
    return request;
  };
  const apiAuthHeaders = (headers={}) => {
    const token = localStorage.getItem('authToken');
    return token ? {...headers, Authorization: 'Bearer ' + token} : headers;
  };

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

  const loadMobileScopeOnce = async (scope, loader) => {
    if (mobileLoadedScopesRef.current.has('full') || mobileLoadedScopesRef.current.has(scope)) return;
    mobileLoadedScopesRef.current.add(scope);
    try { await loader(); }
    catch(e) {
      console.error(`loadMobileScopeOnce failed: ${scope}`, e);
      mobileLoadedScopesRef.current.delete(scope);
    }
  };

  const loadMobileInitial = async () => {
    try {
      await loadMobileScopeOnce('mobile:init', async () => {
        const {
          role, isFinanceRole, isSupplyRole, isInternalRole, canSeeProjectDocs,
          canLoadEstimates, estimatesLoadPath, canLoadPeopleData: shouldLoadPeopleAtBoot,
          canLoadUserDirectory: shouldLoadUsersAtBoot, canLoadAccountingData: shouldLoadAccountingAtBoot,
          canLoadBrigadeData: shouldLoadBrigadeAtBoot, assignmentsPath,
        } = dataLoadPolicyForUser();
        const [
          p,u,sr,ait,oe,pp,wm,wj,s,pw,ct,ia,mp,bc,abi,est,er,hwa,mij,cbj,sva,pdocs,pmeas
        ] = await Promise.all([
          role === 'поставщик' ? Promise.resolve([]) : getApi('/projects'),
          shouldLoadUsersAtBoot ? getApi('/users') : Promise.resolve([]),
          isSupplyRole ? getApi('/supply-requests') : Promise.resolve([]),
          canSeeProjectDocs ? getApi(assignmentsPath) : Promise.resolve([]),
          isInternalRole ? getApi('/own-expenses') : Promise.resolve([]),
          isFinanceRole ? getApi('/project-payments') : Promise.resolve([]),
          role === 'кладовщик' ? getApi('/warehouse-main') : Promise.resolve([]),
          role === 'поставщик' ? Promise.resolve([]) : getApi(pagedPath('/work-journal', {limit: WORK_JOURNAL_PAGE_LIMIT})),
          shouldLoadPeopleAtBoot ? getApi('/staff') : Promise.resolve([]),
          shouldLoadPeopleAtBoot ? getApi('/piecework') : Promise.resolve([]),
          shouldLoadAccountingAtBoot ? getApi('/contracts') : Promise.resolve([]),
          shouldLoadAccountingAtBoot ? getApi('/interim-acts') : Promise.resolve([]),
          shouldLoadPeopleAtBoot ? getApi('/master-profiles') : Promise.resolve([]),
          shouldLoadBrigadeAtBoot ? getApi('/brigade-contracts') : Promise.resolve([]),
          shouldLoadBrigadeAtBoot ? getApi('/brigade-contract-items-all') : Promise.resolve([]),
          canLoadEstimates ? getApi(estimatesLoadPath, null) : Promise.resolve(null),
          canLoadEstimates ? getApi('/estimate-reconciliations') : Promise.resolve([]),
          canSeeProjectDocs ? getApi('/hidden-works-acts') : Promise.resolve([]),
          canSeeProjectDocs ? getApi('/material-inspection') : Promise.resolve([]),
          canSeeProjectDocs ? getApi('/cable-journal') : Promise.resolve([]),
          canSeeProjectDocs ? getApi('/supervisor-acts') : Promise.resolve([]),
          (isInternalRole || isFinanceRole || role === 'заказчик') ? getApi('/project-documents') : Promise.resolve([]),
          canSeeProjectDocs ? getApi('/project-measurements') : Promise.resolve([]),
        ]);
        const safeWorkJournal = Array.isArray(wj) ? wj : [];
        setProjects(Array.isArray(p)?p:[]);
        setUsers(Array.isArray(u)?u:[]);
        setSupplyRequests(Array.isArray(sr)?sr:[]);
        setAiTasks(Array.isArray(ait)?ait:[]);
        setOwnExpenses(Array.isArray(oe)?oe:[]);
        setProjectPayments(Array.isArray(pp)?pp:[]);
        setWarehouseMain(Array.isArray(wm)?wm:[]);
        setWorkJournal(safeWorkJournal);
        resetWorkJournalPage(safeWorkJournal);
        setStaff(Array.isArray(s)?s:[]);
        setPiecework(Array.isArray(pw)?pw:[]);
        setContracts(Array.isArray(ct)?ct:[]);
        setInterimActs(Array.isArray(ia)?ia:[]);
        setMasterProfiles(Array.isArray(mp)?mp:[]);
        setBrigadeContracts(Array.isArray(bc)?bc:[]);
        setAllBrigadeItems(Array.isArray(abi)?abi:[]);
        applyLoadedEstimates(est, canLoadEstimates);
        setEstimateReconciliations(Array.isArray(er)?er:[]);
        setHiddenActs(Array.isArray(hwa)?hwa:[]);
        setMaterialInspections(Array.isArray(mij)?mij:[]);
        setCableJournal(Array.isArray(cbj)?cbj:[]);
        setSupervisorActs(Array.isArray(sva)?sva:[]);
        setProjectDocuments(Array.isArray(pdocs)?pdocs:[]);
        setProjectMeasurements(Array.isArray(pmeas)?pmeas:[]);
      });
    } finally {
      setInitialDataLoaded(true);
    }
  };

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
