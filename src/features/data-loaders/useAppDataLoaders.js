import { useCallback, useEffect } from 'react';
import { createDataLoadPolicy } from './dataLoadPolicy';
import { createMobilePageDataLoader } from './mobilePageDataLoader';

export const useAppDataLoaders = (ctx) => {
  const {
    activePage, API, AUDIT_LOG_PAGE_LIMIT, buildPagedPath, canAccessRole, createMaterialNormsPageState,
    createMaterialsPageState, createWorkJournalPageState, estimatesTab, initialDataLoaded, MATERIAL_NORMS_PAGE_LIMIT, materialNormSearch,
    MATERIALS_PAGE_LIMIT, mergeRowsByIdValue, mobileApiRequestsRef, mobileLoadedScopesRef, mobileScopeForPage, normalizeEstimateList, roleFlagsForUser,
    ROLES, setAccountablePayments, setAiFindings, setAiTasks, setAllBrigadeItems, setAllBrigadePayments, setAuditLog,
    setBrigadeContracts, setCableJournal, setChecklists, setClients, setCompanyDocuments, setCompanyRequisites,
    setContracts, setEstimateReconciliations, setEstimatesList, setEstimatesPage, setExpenseReports, setHiddenActs, setHistory,
    setInitialDataLoaded, setInspectionOrders, setInterimActs, setInventory, setInviteCodes, setInvoices, setLeads,
    setManualExpenses, setMasterProfiles, setMaterialAliases, setMaterialInspections, setMaterialNormOverrides, setMaterialNorms, setMaterialNormsPage,
    setMaterialNormSuggestions, setMaterials, setMaterialsPage, setMaterialTransfers, setMeasurementRoomDrafts, setOwnExpenses, setPdConsents,
    setPiecework, setPrescriptionsList, setPricelists, setProjectDocuments, setProjectLetters, setProjectMeasurements, setProjectPayments,
    setProjects, setProjectStages, setRoomDoors, setRooms, setRoomWindows, setRoomWorks, setSalaryPayments,
    setStaff, setSupervisorActs, setSupplierCatalog, setSupplierInvoices, setSupplierOffers, setSuppliers, setSupplyClaims,
    setSupplyDeliveries, setSupplyHistory, setSupplyRequests, setSupplyTemplates, setTbJournal, setTimesheet,
    setToolHistory, setTools, setUnexpectedWorksList, setUser, setUsers, setWarehouseMain, setWarehouseMovements,
    setWarehouses, setWarrantyDefects, setWorkJournal, setWorkJournalPage, user, WORK_JOURNAL_PAGE_LIMIT,
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

  const loadAll = async () => {
    try {
      const {
        role,
        isLeadershipRole,
        isFinanceRole,
        isWarehouseRole,
        isSupplyRole,
        canSeeSupplierInvoices,
        isInternalRole,
        canSeeProjectDocs,
        canLoadPeopleData,
        canLoadUserDirectory,
        canLoadAccountingData,
        canLoadBrigadeData,
        canLoadBrigadePayments,
        canLoadEstimates,
        estimatesLoadPath,
        assignmentsPath,
      } = dataLoadPolicyForUser(user);
      if (canLoadEstimates) markEstimatesLoading(true);
      const token = localStorage.getItem('authToken');
      const LOAD_FAILED = Symbol('LOAD_FAILED');
      const isLoaded = (value) => value !== LOAD_FAILED;
      const asArray = (value) => Array.isArray(value) ? value : [];
      const setLoaded = (setter, value, normalize = asArray) => {
        if (!isLoaded(value)) return;
        setter(normalize(value));
      };
      const get = (path, fallback = []) => fetch(API + path, token ? {headers: {Authorization: 'Bearer ' + token}} : undefined)
        .then(r => {
          if (r.ok) return r.json();
          if (r.status === 401) handleApiUnauthorized();
          return fallback === null ? null : LOAD_FAILED;
        })
        .catch(() => fallback === null ? null : LOAD_FAILED);
      const skip = (fallback = []) => Promise.resolve(fallback);

      const [p,c,m,winv,pp,acp,oe,me,wm,wmov,h,s,pw,u,pl,ic,sup,sr,so,sh,sd,sc,wj,mp,ct,ia,ro,rw,tl,th,inv,pdc,wh,cr,cd,ps,pcl,pres,uw,est,er,bc,hwa,mij,cbj,sva,inspO,expR,supI,warD,scat,stpl,aif,ait,mn,ma,mno,mns,aud] = await Promise.all([
        role === 'поставщик' ? skip([]) : get('/projects'),
        (isLeadershipRole || role === 'менеджер_crm') ? get('/clients') : skip([]),
        role === 'поставщик' ? skip([]) : get(pagedPath('/materials', {limit: MATERIALS_PAGE_LIMIT})),
        (isWarehouseRole || isFinanceRole) ? get('/warehouse-invoices') : skip([]),
        isFinanceRole ? get('/project-payments') : skip([]),
        isFinanceRole ? get('/accountable-payments') : skip([]),
        isInternalRole ? get('/own-expenses') : skip([]),
        isFinanceRole ? get('/expenses') : skip([]),
        (isWarehouseRole || isFinanceRole) ? get('/warehouse-main') : skip([]),
        (isWarehouseRole || isFinanceRole) ? get('/warehouse-movements') : skip([]),
	        (isWarehouseRole || isFinanceRole || ['мастер','субподрядчик','бригадир'].includes(role)) ? get('/warehouse-history') : skip([]),
        canLoadPeopleData ? get('/staff') : skip([]),
        canLoadPeopleData ? get('/piecework') : skip([]),
        canLoadUserDirectory ? get('/users') : skip([]),
        ((isInternalRole && !['мастер','субподрядчик','бригадир'].includes(role)) || role === 'технадзор') ? get('/pricelists') : skip([]),
        isLeadershipRole ? get('/invite-codes') : skip([]),
        (isSupplyRole || isWarehouseRole || isFinanceRole) ? get('/suppliers') : skip([]),
        isSupplyRole ? get('/supply-requests') : skip([]),
        isSupplyRole ? get('/supplier-offers') : skip([]),
        (isSupplyRole || isWarehouseRole || isFinanceRole) ? get('/supply-history') : skip([]),
        isSupplyRole ? get('/supply-deliveries') : skip([]),
        isSupplyRole ? get('/supply-claims') : skip([]),
        role === 'поставщик' ? skip([]) : get(pagedPath('/work-journal', {limit: WORK_JOURNAL_PAGE_LIMIT})),
        canLoadPeopleData ? get('/master-profiles') : skip([]),
        canLoadAccountingData ? get('/contracts') : skip([]),
        canLoadAccountingData ? get('/interim-acts') : skip([]),
        canSeeProjectDocs ? get('/rooms') : skip([]),
        canSeeProjectDocs ? get('/room-works') : skip([]),
        isInternalRole ? get('/tools') : skip([]),
        isInternalRole ? get('/tool-history') : skip([]),
        isInternalRole ? get('/inventory') : skip([]),
        (isLeadershipRole || isFinanceRole) ? get('/pd-consents') : skip([]),
        (isWarehouseRole || isSupplyRole || isFinanceRole) ? get('/warehouses') : skip([]),
        role === 'поставщик' ? skip({}) : get('/company-requisites', {}),
        isFinanceRole ? get('/company-documents') : skip([]),
        canSeeProjectDocs ? get('/project-stages') : skip([]),
        canSeeProjectDocs ? get('/project-checklists') : skip([]),
        canSeeProjectDocs ? get('/prescriptions') : skip([]),
        canSeeProjectDocs ? get('/unexpected-works') : skip([]),
        canLoadEstimates ? get(estimatesLoadPath, null) : skip(null),
        canLoadEstimates ? get('/estimate-reconciliations') : skip([]),
        canLoadBrigadeData ? get('/brigade-contracts') : skip([]),
        canSeeProjectDocs ? get('/hidden-works-acts') : skip([]),
        (canSeeProjectDocs || isWarehouseRole) ? get('/material-inspection') : skip([]),
        (canSeeProjectDocs || isWarehouseRole) ? get('/cable-journal') : skip([]),
        canSeeProjectDocs ? get('/supervisor-acts') : skip([]),
        canSeeProjectDocs ? get('/inspection-orders') : skip([]),
        isFinanceRole ? get('/expense-reports') : skip([]),
        canSeeSupplierInvoices ? get('/supplier-invoices') : skip([]),
        canSeeProjectDocs ? get('/warranty-defects') : skip([]),
        (isSupplyRole || isWarehouseRole || isFinanceRole || role === 'поставщик') ? get('/supplier-catalog') : skip([]),
        isSupplyRole ? get('/supply-request-templates') : skip([]),
        canSeeProjectDocs ? get('/ai-findings') : skip([]),
        canSeeProjectDocs ? get(assignmentsPath) : skip([]),
        canSeeProjectDocs ? get(pagedPath('/material-norms', {limit: MATERIAL_NORMS_PAGE_LIMIT})) : skip([]),
        canSeeProjectDocs ? get('/material-aliases') : skip([]),
        canSeeProjectDocs ? get('/material-norms/overrides') : skip([]),
        canSeeProjectDocs ? get('/material-norm-suggestions') : skip([]),
        (isLeadershipRole || isFinanceRole) ? get(pagedPath('/audit-log', {limit: AUDIT_LOG_PAGE_LIMIT})) : skip([]),
      ]);
      setLoaded(setProjects, p); setLoaded(setClients, c);
      if (isLoaded(m)) { setMaterials(asArray(m)); resetMaterialsPage(asArray(m)); }
      setLoaded(setInvoices, winv); setLoaded(setProjectPayments, pp); setLoaded(setAccountablePayments, acp);
      setLoaded(setOwnExpenses, oe); setLoaded(setManualExpenses, me); setLoaded(setWarehouseMain, wm); setLoaded(setWarehouseMovements, wmov);
      setLoaded(setHistory, h); setLoaded(setStaff, s); setLoaded(setPiecework, pw); setLoaded(setUsers, u); setLoaded(setPricelists, pl);
      setLoaded(setInviteCodes, ic); setLoaded(setSuppliers, sup); setLoaded(setSupplyRequests, sr); setLoaded(setSupplierOffers, so);
      setLoaded(setSupplyHistory, sh); setLoaded(setSupplyDeliveries, sd); setLoaded(setSupplyClaims, sc);
      if (isLoaded(wj)) { setWorkJournal(asArray(wj)); resetWorkJournalPage(asArray(wj)); }
      setLoaded(setMasterProfiles, mp); setLoaded(setContracts, ct); setLoaded(setInterimActs, ia);
      setLoaded(setRooms, ro); setLoaded(setRoomWorks, rw); setLoaded(setTools, tl); setLoaded(setToolHistory, th);
      setLoaded(setInventory, inv); setLoaded(setPdConsents, pdc); setLoaded(setWarehouses, wh);
      if (isLoaded(cr)) setCompanyRequisites(cr || {});
      setLoaded(setCompanyDocuments, cd);
      setLoaded(setProjectStages, ps); setLoaded(setChecklists, pcl);
      setLoaded(setPrescriptionsList, pres); setLoaded(setUnexpectedWorksList, uw);
      if (isLoaded(est)) applyLoadedEstimates(est, canLoadEstimates);
      setLoaded(setEstimateReconciliations, er); setLoaded(setBrigadeContracts, bc); setLoaded(setHiddenActs, hwa);
      setLoaded(setMaterialInspections, mij); setLoaded(setCableJournal, cbj); setLoaded(setSupervisorActs, sva);
      setLoaded(setInspectionOrders, inspO); setLoaded(setExpenseReports, expR); setLoaded(setSupplierInvoices, supI);
      setLoaded(setWarrantyDefects, warD); setLoaded(setSupplierCatalog, scat); setLoaded(setSupplyTemplates, stpl);
      setLoaded(setAiFindings, aif); setLoaded(setAiTasks, ait);
      if (isLoaded(mn)) { setMaterialNorms(asArray(mn)); resetMaterialNormsPage(asArray(mn)); }
      setLoaded(setMaterialAliases, ma); setLoaded(setMaterialNormOverrides, mno); setLoaded(setMaterialNormSuggestions, mns); setLoaded(setAuditLog, aud);
      if (canSeeProjectDocs) try {
        const [rwin,rdoor] = await Promise.all([
          get('/room-windows'),
          get('/room-doors'),
        ]);
        setLoaded(setRoomWindows, rwin); setLoaded(setRoomDoors, rdoor);
      } catch(e) {}
      if (canLoadPeopleData) try {
        const ts = await get('/timesheet');
        if (isLoaded(ts) && Array.isArray(ts)) setTimesheet(Object.fromEntries(ts.map(t=>[t.staffId+'-'+t.day, true])));
      } catch(e) {}
      if (isFinanceRole) try {
        const sp = await get('/salary-payments');
        setLoaded(setSalaryPayments, sp);
      } catch(e) {}
      try {
        let ls = await get('/crm/lead-summaries');
        if (!isLoaded(ls)) ls = null;
        else if (!Array.isArray(ls)) ls = [];
        // Одноразовая миграция старых лидов из localStorage в БД
        const oldRaw = ls !== null ? localStorage.getItem('leads') : null;
        if (Array.isArray(ls) && ls.length===0 && oldRaw) {
          try {
            const old = JSON.parse(oldRaw);
            if (Array.isArray(old) && old.length>0) {
              for (const l of old) {
                await fetch(API+'/crm/leads',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:l.name||'',phone:l.phone||'',email:l.email||'',source:l.source||'',budget:Number(l.budget)||0,notes:l.notes||'',stage:l.stage||'Новый',createdBy:l.createdBy||user.name,createdAt:l.createdAt||''})});
              }
              localStorage.removeItem('leads');
              ls = await get('/crm/lead-summaries');
              if (!isLoaded(ls)) ls = null;
            }
          } catch(_){}
        }
        if (ls !== null) setLeads(Array.isArray(ls)?ls:[]);
      } catch(e) {}
      if (isWarehouseRole || ['мастер','субподрядчик','бригадир'].includes(role)) try {
        const mt = await get('/material-transfers');
        setLoaded(setMaterialTransfers, mt);
      } catch(e) {}
      if (isInternalRole) try {
        const tb = await get('/tb-journal');
        if (isLoaded(tb)) {
          const tbNorm = (Array.isArray(tb)?tb:[]).map(t=>({...t, project: t.projectName, type: t.instructionType}));
          setTbJournal(tbNorm);
          try { localStorage.setItem('tbJournal', JSON.stringify(tbNorm)); } catch(e){}
        }
      } catch(e) {}
      if (canLoadBrigadeData) try {
        const abi = await get('/brigade-contract-items-all');
        setLoaded(setAllBrigadeItems, abi);
      } catch(e) {}
      if (canLoadBrigadePayments) try {
        const abp = await get('/brigade-payments');
        setLoaded(setAllBrigadePayments, abp);
      } catch(e) {}
      if (canSeeProjectDocs || canLoadAccountingData || role==='заказчик') try {
        const pdocs = await get('/project-documents');
        setLoaded(setProjectDocuments, pdocs);
        const plet = await get('/project-letters');
        setLoaded(setProjectLetters, plet);
      } catch(e) {}
      if (canSeeProjectDocs) try {
        const pmeas = await get('/project-measurements');
        setLoaded(setProjectMeasurements, pmeas);
        const mdrafts = await get('/measurement-room-drafts');
        setLoaded(setMeasurementRoomDrafts, mdrafts);
      } catch(e) {}
      mobileLoadedScopesRef.current.add('full');
    } catch(e) {
      console.error('loadAll failed', e);
      setEstimatesPage(prev => prev.loading ? {
        loading:false,
        error:'Не удалось загрузить сметы. Проверьте соединение или повторите загрузку.',
      } : prev);
    } finally {
      setInitialDataLoaded(true);
    }
  };

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
