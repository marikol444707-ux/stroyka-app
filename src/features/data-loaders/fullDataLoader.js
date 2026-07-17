export const createFullDataLoader = (deps) => {
  const {
    API, AUDIT_LOG_PAGE_LIMIT, MATERIAL_NORMS_PAGE_LIMIT, MATERIALS_PAGE_LIMIT,
    WORK_JOURNAL_PAGE_LIMIT, user, mobileLoadedScopesRef, dataLoadPolicyForUser,
    pagedPath, markEstimatesLoading, applyLoadedEstimates, resetWorkJournalPage,
    resetMaterialsPage, resetMaterialNormsPage, handleApiUnauthorized,
    setAccountablePayments, setAiFindings, setAiTasks, setAllBrigadeItems,
    setAllBrigadePayments, setAuditLog, setBrigadeContracts, setCableJournal,
    setChecklists, setClients, setCompanyDocuments, setCompanyRequisites,
    setContracts, setEstimateReconciliations, setEstimatesPage, setExpenseReports,
    setHiddenActs, setHistory, setInitialDataLoaded, setInspectionOrders,
    setInterimActs, setInventory, setInviteCodes, setInvoices, setLeads,
    setManualExpenses, setMasterProfiles, setMaterialAliases, setMaterialInspections,
    setMaterialNormOverrides, setMaterialNorms, setMaterialNormSuggestions,
    setMaterials, setMaterialTransfers, setMeasurementRoomDrafts, setOwnExpenses,
    setPdConsents, setPiecework, setPrescriptionsList, setPricelists,
    setProjectDocuments, setProjectLetters, setProjectMeasurements,
    setProjectPayments, setProjects, setProjectStages, setRoomDoors, setRooms,
    setRoomWindows, setRoomWorks, setSalaryPayments, setStaff, setSupervisorActs,
    setSupplierCatalog, setSupplierInvoices, setSupplierOffers, setSuppliers,
    setSupplyClaims, setSupplyDeliveries, setSupplyHistory, setSupplyRequests,
    setSupplyTemplates, setTbJournal, setTimesheet, setToolHistory, setTools,
    setUnexpectedWorksList, setUsers, setWarehouseMain, setWarehouseMovements,
    setWarehouses, setWarrantyDefects, setWorkJournal,
    fetchImpl = fetch,
  } = deps;

  return async () => {
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
      const get = (path, fallback = []) => fetchImpl(API + path, token ? {headers: {Authorization: 'Bearer ' + token}} : undefined)
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
                await fetchImpl(API+'/crm/leads',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:l.name||'',phone:l.phone||'',email:l.email||'',source:l.source||'',budget:Number(l.budget)||0,notes:l.notes||'',stage:l.stage||'Новый',createdBy:l.createdBy||user.name,createdAt:l.createdAt||''})});
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
};
