export const createMobilePageDataLoader = (deps) => {
  const {
    activePage, user, AUDIT_LOG_PAGE_LIMIT, MATERIAL_NORMS_PAGE_LIMIT, MATERIALS_PAGE_LIMIT,
    WORK_JOURNAL_PAGE_LIMIT, mobileLoadedScopesRef, dataLoadPolicyForUser, getApi, pagedPath,
    loadMobileScopeOnce, markEstimatesLoading, applyLoadedEstimates, resetWorkJournalPage,
    resetMaterialsPage, resetMaterialNormsPage, setAccountablePayments, setAiFindings, setAiTasks,
    setAllBrigadeItems, setAllBrigadePayments, setAuditLog, setBrigadeContracts, setCableJournal,
    setChecklists, setClients, setCompanyDocuments, setCompanyRequisites, setContracts,
    setEstimateReconciliations, setExpenseReports, setHiddenActs, setHistory, setInspectionOrders,
    setInterimActs, setInviteCodes, setInvoices, setLeads, setManualExpenses, setMasterProfiles,
    setMaterialAliases, setMaterialInspections, setMaterialNormOverrides, setMaterialNorms,
    setMaterialNormSuggestions, setMaterials, setMaterialTransfers, setMeasurementRoomDrafts,
    setOwnExpenses, setPdConsents, setPiecework, setPrescriptionsList, setPricelists,
    setProjectDocuments, setProjectLetters, setProjectMeasurements, setProjectPayments,
    setProjects, setProjectStages, setRoomDoors, setRooms, setRoomWindows, setRoomWorks,
    setSalaryPayments, setStaff, setSupervisorActs, setSupplierCatalog, setSupplierInvoices,
    setSupplierOffers, setSuppliers, setSupplyClaims, setSupplyDeliveries, setSupplyHistory,
    setSupplyRequests, setSupplyTemplates, setTimesheet, setUnexpectedWorksList, setUsers,
    setWarehouseMain, setWarehouseMovements, setWarehouses, setWarrantyDefects, setWorkJournal,
  } = deps;

  return async (page = activePage) => {
    if (!user) return;
    const {
      role, isLeadershipRole, isFinanceRole, isWarehouseRole, isSupplyRole, canSeeSupplierInvoices,
      isInternalRole, canSeeProjectDocs, isWorkerRole, canLoadPeopleData, canLoadUserDirectory,
      canLoadAccountingData, canLoadBrigadeData, canLoadBrigadePayments, canLoadEstimates,
      estimatesLoadPath, assignmentsPath,
    } = dataLoadPolicyForUser();
    if (page === 'dashboard') return loadMobileScopeOnce('mobile:dashboard', async () => {
      const [aif,ait,sh,sd,scat] = await Promise.all([
        canSeeProjectDocs ? getApi('/ai-findings') : Promise.resolve([]),
        canSeeProjectDocs ? getApi(assignmentsPath) : Promise.resolve([]),
        (isSupplyRole || isWarehouseRole || isFinanceRole) ? getApi('/supply-history') : Promise.resolve([]),
        isSupplyRole ? getApi('/supply-deliveries') : Promise.resolve([]),
        (isSupplyRole || isWarehouseRole || isFinanceRole || role === 'поставщик') ? getApi('/supplier-catalog') : Promise.resolve([]),
      ]);
      setAiFindings(Array.isArray(aif)?aif:[]);
      setAiTasks(Array.isArray(ait)?ait:[]);
      setSupplyHistory(Array.isArray(sh)?sh:[]);
      setSupplyDeliveries(Array.isArray(sd)?sd:[]);
      setSupplierCatalog(Array.isArray(scat)?scat:[]);
    });
    if (page === 'assignments') return loadMobileScopeOnce('mobile:assignments', async () => {
      const [p, ait, u] = await Promise.all([
        role === 'поставщик' ? Promise.resolve([]) : getApi('/projects'),
        canSeeProjectDocs ? getApi(assignmentsPath) : Promise.resolve([]),
        canLoadUserDirectory ? getApi('/users') : Promise.resolve([]),
      ]);
      setProjects(Array.isArray(p)?p:[]);
      setAiTasks(Array.isArray(ait)?ait:[]);
      setUsers(Array.isArray(u)?u:[]);
    });
    if (['projects','site','works','documents','cable'].includes(page)) return loadMobileScopeOnce('mobile:projects-docs', async () => {
      if (canSeeProjectDocs) markEstimatesLoading(true);
      const [p,wj,mt,ro,rw,rwin,rdoor,ps,pcl,pres,uw,est,er,bc,abi,hwa,mij,cbj,sva,inspO,warD,pdocs,plet,pmeas,mdrafts,s,u,ct,ia,pw,mp] = await Promise.all([
        role === 'поставщик' ? Promise.resolve([]) : getApi('/projects'),
        role === 'поставщик' ? Promise.resolve([]) : getApi(pagedPath('/work-journal', {limit: WORK_JOURNAL_PAGE_LIMIT})),
        (isWarehouseRole || ['мастер','субподрядчик','бригадир'].includes(role)) ? getApi('/material-transfers') : Promise.resolve([]),
        canSeeProjectDocs ? getApi('/rooms') : Promise.resolve([]),
        canSeeProjectDocs ? getApi('/room-works') : Promise.resolve([]),
        canSeeProjectDocs ? getApi('/room-windows') : Promise.resolve([]),
        canSeeProjectDocs ? getApi('/room-doors') : Promise.resolve([]),
        canSeeProjectDocs ? getApi('/project-stages') : Promise.resolve([]),
        canSeeProjectDocs ? getApi('/project-checklists') : Promise.resolve([]),
        canSeeProjectDocs ? getApi('/prescriptions') : Promise.resolve([]),
        canSeeProjectDocs ? getApi('/unexpected-works') : Promise.resolve([]),
        canSeeProjectDocs ? getApi(estimatesLoadPath, null) : Promise.resolve(null),
        canSeeProjectDocs ? getApi('/estimate-reconciliations') : Promise.resolve([]),
        (canLoadPeopleData || isWorkerRole) ? getApi('/brigade-contracts') : Promise.resolve([]),
        (canLoadPeopleData || isWorkerRole) ? getApi('/brigade-contract-items-all') : Promise.resolve([]),
        canSeeProjectDocs ? getApi('/hidden-works-acts') : Promise.resolve([]),
        (canSeeProjectDocs || isWarehouseRole) ? getApi('/material-inspection') : Promise.resolve([]),
        (canSeeProjectDocs || isWarehouseRole) ? getApi('/cable-journal') : Promise.resolve([]),
        canSeeProjectDocs ? getApi('/supervisor-acts') : Promise.resolve([]),
        canSeeProjectDocs ? getApi('/inspection-orders') : Promise.resolve([]),
        canSeeProjectDocs ? getApi('/warranty-defects') : Promise.resolve([]),
        (isInternalRole || isFinanceRole || role==='заказчик') ? getApi('/project-documents') : Promise.resolve([]),
        (isInternalRole || isFinanceRole || role==='заказчик') ? getApi('/project-letters') : Promise.resolve([]),
        canSeeProjectDocs ? getApi('/project-measurements') : Promise.resolve([]),
        canSeeProjectDocs ? getApi('/measurement-room-drafts') : Promise.resolve([]),
        canLoadPeopleData ? getApi('/staff') : Promise.resolve([]),
        canLoadUserDirectory ? getApi('/users') : Promise.resolve([]),
        canLoadAccountingData ? getApi('/contracts') : Promise.resolve([]),
        canLoadAccountingData ? getApi('/interim-acts') : Promise.resolve([]),
        canLoadPeopleData ? getApi('/piecework') : Promise.resolve([]),
        canLoadPeopleData ? getApi('/master-profiles') : Promise.resolve([]),
      ]);
      const safeWorkJournal = Array.isArray(wj) ? wj : [];
      setProjects(Array.isArray(p)?p:[]);
      setWorkJournal(safeWorkJournal);
      resetWorkJournalPage(safeWorkJournal);
      setMaterialTransfers(Array.isArray(mt)?mt:[]);
      setRooms(Array.isArray(ro)?ro:[]); setRoomWorks(Array.isArray(rw)?rw:[]);
      setRoomWindows(Array.isArray(rwin)?rwin:[]); setRoomDoors(Array.isArray(rdoor)?rdoor:[]);
      setProjectStages(Array.isArray(ps)?ps:[]); setChecklists(Array.isArray(pcl)?pcl:[]);
      setPrescriptionsList(Array.isArray(pres)?pres:[]); setUnexpectedWorksList(Array.isArray(uw)?uw:[]);
      applyLoadedEstimates(est, canSeeProjectDocs);
      if (canSeeProjectDocs && est === null) mobileLoadedScopesRef.current.delete('mobile:projects-docs');
      setEstimateReconciliations(Array.isArray(er)?er:[]); setBrigadeContracts(Array.isArray(bc)?bc:[]); setAllBrigadeItems(Array.isArray(abi)?abi:[]);
      setHiddenActs(Array.isArray(hwa)?hwa:[]); setMaterialInspections(Array.isArray(mij)?mij:[]);
      setCableJournal(Array.isArray(cbj)?cbj:[]); setSupervisorActs(Array.isArray(sva)?sva:[]);
      setInspectionOrders(Array.isArray(inspO)?inspO:[]); setWarrantyDefects(Array.isArray(warD)?warD:[]);
      setProjectDocuments(Array.isArray(pdocs)?pdocs:[]); setProjectLetters(Array.isArray(plet)?plet:[]);
      setProjectMeasurements(Array.isArray(pmeas)?pmeas:[]); setMeasurementRoomDrafts(Array.isArray(mdrafts)?mdrafts:[]);
      setStaff(Array.isArray(s)?s:[]);
      setUsers(Array.isArray(u)?u:[]);
      setContracts(Array.isArray(ct)?ct:[]);
      setInterimActs(Array.isArray(ia)?ia:[]);
      setPiecework(Array.isArray(pw)?pw:[]);
      setMasterProfiles(Array.isArray(mp)?mp:[]);
    });
    if (page === 'estimates') return loadMobileScopeOnce('mobile:estimates', async () => {
      if (canLoadEstimates) markEstimatesLoading(true);
      const [est,er,pl,mn,ma,mno,mns,bc,abi,abp] = await Promise.all([
        canLoadEstimates ? getApi(estimatesLoadPath, null) : Promise.resolve(null),
        canLoadEstimates ? getApi('/estimate-reconciliations') : Promise.resolve([]),
        ((isInternalRole && !['мастер','субподрядчик','бригадир'].includes(role)) || role === 'технадзор') ? getApi('/pricelists') : Promise.resolve([]),
        canSeeProjectDocs ? getApi(pagedPath('/material-norms', {limit: MATERIAL_NORMS_PAGE_LIMIT})) : Promise.resolve([]),
        canSeeProjectDocs ? getApi('/material-aliases') : Promise.resolve([]),
        canSeeProjectDocs ? getApi('/material-norms/overrides') : Promise.resolve([]),
        canSeeProjectDocs ? getApi('/material-norm-suggestions') : Promise.resolve([]),
        canLoadBrigadeData ? getApi('/brigade-contracts') : Promise.resolve([]),
        canLoadBrigadeData ? getApi('/brigade-contract-items-all') : Promise.resolve([]),
        canLoadBrigadePayments ? getApi('/brigade-payments') : Promise.resolve([]),
      ]);
      applyLoadedEstimates(est, canLoadEstimates);
      if (canLoadEstimates && est === null) mobileLoadedScopesRef.current.delete('mobile:estimates');
      setEstimateReconciliations(Array.isArray(er)?er:[]); setPricelists(Array.isArray(pl)?pl:[]);
      setMaterialNorms(Array.isArray(mn)?mn:[]); resetMaterialNormsPage(mn); setMaterialAliases(Array.isArray(ma)?ma:[]);
      setMaterialNormOverrides(Array.isArray(mno)?mno:[]); setMaterialNormSuggestions(Array.isArray(mns)?mns:[]);
      setBrigadeContracts(Array.isArray(bc)?bc:[]); setAllBrigadeItems(Array.isArray(abi)?abi:[]);
      setAllBrigadePayments(Array.isArray(abp)?abp:[]);
    });
    if (['warehouse','materials'].includes(page)) return loadMobileScopeOnce('mobile:warehouse', async () => {
      const [m,winv,wm,wmov,h,wh,mt,mij,cbj,sr,sh,sd] = await Promise.all([
        role === 'поставщик' ? Promise.resolve([]) : getApi(pagedPath('/materials', {limit: MATERIALS_PAGE_LIMIT})),
        (isWarehouseRole || isFinanceRole) ? getApi('/warehouse-invoices') : Promise.resolve([]),
        (isWarehouseRole || isFinanceRole) ? getApi('/warehouse-main') : Promise.resolve([]),
        (isWarehouseRole || isFinanceRole) ? getApi('/warehouse-movements') : Promise.resolve([]),
        (isWarehouseRole || isFinanceRole || ['мастер','субподрядчик','бригадир'].includes(role)) ? getApi('/warehouse-history') : Promise.resolve([]),
        (isWarehouseRole || isSupplyRole || isFinanceRole) ? getApi('/warehouses') : Promise.resolve([]),
        (isWarehouseRole || ['мастер','субподрядчик','бригадир'].includes(role)) ? getApi('/material-transfers') : Promise.resolve([]),
        (canSeeProjectDocs || isWarehouseRole) ? getApi('/material-inspection') : Promise.resolve([]),
        (canSeeProjectDocs || isWarehouseRole) ? getApi('/cable-journal') : Promise.resolve([]),
        isSupplyRole ? getApi('/supply-requests') : Promise.resolve([]),
        (isSupplyRole || isWarehouseRole || isFinanceRole) ? getApi('/supply-history') : Promise.resolve([]),
        isSupplyRole ? getApi('/supply-deliveries') : Promise.resolve([]),
      ]);
      setMaterials(Array.isArray(m)?m:[]); resetMaterialsPage(m); setInvoices(Array.isArray(winv)?winv:[]);
      setWarehouseMain(Array.isArray(wm)?wm:[]); setWarehouseMovements(Array.isArray(wmov)?wmov:[]);
      setHistory(Array.isArray(h)?h:[]); setWarehouses(Array.isArray(wh)?wh:[]);
      setMaterialTransfers(Array.isArray(mt)?mt:[]); setMaterialInspections(Array.isArray(mij)?mij:[]);
      setCableJournal(Array.isArray(cbj)?cbj:[]);
      setSupplyRequests(Array.isArray(sr)?sr:[]);
      setSupplyHistory(Array.isArray(sh)?sh:[]);
      setSupplyDeliveries(Array.isArray(sd)?sd:[]);
    });
    if (['supply','suppliers'].includes(page)) return loadMobileScopeOnce('mobile:supply', async () => {
      const [sup,sr,so,sh,sd,sc,supI,scat,stpl,winv] = await Promise.all([
        (isSupplyRole || isWarehouseRole || isFinanceRole) ? getApi('/suppliers') : Promise.resolve([]),
        isSupplyRole ? getApi('/supply-requests') : Promise.resolve([]),
        isSupplyRole ? getApi('/supplier-offers') : Promise.resolve([]),
        (isSupplyRole || isWarehouseRole || isFinanceRole) ? getApi('/supply-history') : Promise.resolve([]),
        isSupplyRole ? getApi('/supply-deliveries') : Promise.resolve([]),
        isSupplyRole ? getApi('/supply-claims') : Promise.resolve([]),
        canSeeSupplierInvoices ? getApi('/supplier-invoices') : Promise.resolve([]),
        (isSupplyRole || isWarehouseRole || isFinanceRole || role === 'поставщик') ? getApi('/supplier-catalog') : Promise.resolve([]),
        isSupplyRole ? getApi('/supply-request-templates') : Promise.resolve([]),
        (isWarehouseRole || isFinanceRole) ? getApi('/warehouse-invoices') : Promise.resolve([]),
      ]);
      setSuppliers(Array.isArray(sup)?sup:[]); setSupplyRequests(Array.isArray(sr)?sr:[]);
      setSupplierOffers(Array.isArray(so)?so:[]); setSupplyHistory(Array.isArray(sh)?sh:[]);
      setSupplyDeliveries(Array.isArray(sd)?sd:[]); setSupplyClaims(Array.isArray(sc)?sc:[]);
      setSupplierInvoices(Array.isArray(supI)?supI:[]); setSupplierCatalog(Array.isArray(scat)?scat:[]);
      setSupplyTemplates(Array.isArray(stpl)?stpl:[]);
      setInvoices(Array.isArray(winv)?winv:[]);
    });
    if (['personnel','users'].includes(page)) return loadMobileScopeOnce('mobile:people', async () => {
      const [s,pw,u,mp,ts,pdc,ic] = await Promise.all([
        canLoadPeopleData ? getApi('/staff') : Promise.resolve([]),
        canLoadPeopleData ? getApi('/piecework') : Promise.resolve([]),
        canLoadUserDirectory ? getApi('/users') : Promise.resolve([]),
        canLoadPeopleData ? getApi('/master-profiles') : Promise.resolve([]),
        canLoadPeopleData ? getApi('/timesheet') : Promise.resolve([]),
        (isLeadershipRole || isFinanceRole) ? getApi('/pd-consents') : Promise.resolve([]),
        isLeadershipRole ? getApi('/invite-codes') : Promise.resolve([]),
      ]);
      setStaff(Array.isArray(s)?s:[]); setPiecework(Array.isArray(pw)?pw:[]);
      setUsers(Array.isArray(u)?u:[]); setMasterProfiles(Array.isArray(mp)?mp:[]);
      if (Array.isArray(ts)) setTimesheet(Object.fromEntries(ts.map(t=>[t.staffId+'-'+t.day, true])));
      setPdConsents(Array.isArray(pdc)?pdc:[]);
      setInviteCodes(Array.isArray(ic)?ic:[]);
    });
    if (page === 'accounting') return loadMobileScopeOnce('mobile:accounting', async () => {
      const [pp,acp,oe,me,ct,ia,expR,supI,winv,sup,cd,sp,s,pw,u,bc] = await Promise.all([
        isFinanceRole ? getApi('/project-payments') : Promise.resolve([]),
        isFinanceRole ? getApi('/accountable-payments') : Promise.resolve([]),
        isInternalRole ? getApi('/own-expenses') : Promise.resolve([]),
        isFinanceRole ? getApi('/expenses') : Promise.resolve([]),
        canLoadAccountingData ? getApi('/contracts') : Promise.resolve([]),
        canLoadAccountingData ? getApi('/interim-acts') : Promise.resolve([]),
        isFinanceRole ? getApi('/expense-reports') : Promise.resolve([]),
        canSeeSupplierInvoices ? getApi('/supplier-invoices') : Promise.resolve([]),
        (isWarehouseRole || isFinanceRole) ? getApi('/warehouse-invoices') : Promise.resolve([]),
        (isSupplyRole || isWarehouseRole || isFinanceRole) ? getApi('/suppliers') : Promise.resolve([]),
        isFinanceRole ? getApi('/company-documents') : Promise.resolve([]),
        isFinanceRole ? getApi('/salary-payments') : Promise.resolve([]),
        canLoadPeopleData ? getApi('/staff') : Promise.resolve([]),
        canLoadPeopleData ? getApi('/piecework') : Promise.resolve([]),
        canLoadUserDirectory ? getApi('/users') : Promise.resolve([]),
        canLoadBrigadeData ? getApi('/brigade-contracts') : Promise.resolve([]),
      ]);
      setProjectPayments(Array.isArray(pp)?pp:[]); setAccountablePayments(Array.isArray(acp)?acp:[]);
      setOwnExpenses(Array.isArray(oe)?oe:[]); setManualExpenses(Array.isArray(me)?me:[]);
      setContracts(Array.isArray(ct)?ct:[]); setInterimActs(Array.isArray(ia)?ia:[]);
      setExpenseReports(Array.isArray(expR)?expR:[]); setSupplierInvoices(Array.isArray(supI)?supI:[]);
      setInvoices(Array.isArray(winv)?winv:[]); setSuppliers(Array.isArray(sup)?sup:[]);
      setCompanyDocuments(Array.isArray(cd)?cd:[]); setSalaryPayments(Array.isArray(sp)?sp:[]);
      setStaff(Array.isArray(s)?s:[]); setPiecework(Array.isArray(pw)?pw:[]); setUsers(Array.isArray(u)?u:[]);
      setBrigadeContracts(Array.isArray(bc)?bc:[]);
    });
    if (page === 'history') return loadMobileScopeOnce('mobile:history', async () => {
      const [wj,h,mt] = await Promise.all([
        role === 'поставщик' ? Promise.resolve([]) : getApi(pagedPath('/work-journal', {limit: WORK_JOURNAL_PAGE_LIMIT})),
        (isWarehouseRole || isFinanceRole || ['мастер','субподрядчик','бригадир'].includes(role)) ? getApi('/warehouse-history') : Promise.resolve([]),
        (isWarehouseRole || ['мастер','субподрядчик','бригадир'].includes(role)) ? getApi('/material-transfers') : Promise.resolve([]),
      ]);
      const safeWorkJournal = Array.isArray(wj) ? wj : [];
      setWorkJournal(safeWorkJournal);
      resetWorkJournalPage(safeWorkJournal);
      setHistory(Array.isArray(h)?h:[]);
      setMaterialTransfers(Array.isArray(mt)?mt:[]);
    });
    if (page === 'myexpenses') return loadMobileScopeOnce('mobile:myexpenses', async () => {
      const oe = isInternalRole ? await getApi('/own-expenses') : [];
      setOwnExpenses(Array.isArray(oe)?oe:[]);
    });
    if (page === 'clients') return loadMobileScopeOnce('mobile:clients', async () => {
      const c = (isLeadershipRole || role === 'менеджер_crm') ? await getApi('/clients') : [];
      setClients(Array.isArray(c)?c:[]);
    });
    if (page === 'pricelists') return loadMobileScopeOnce('mobile:pricelists', async () => {
      const pl = ((isInternalRole && !['мастер','субподрядчик','бригадир'].includes(role)) || role === 'технадзор') ? await getApi('/pricelists') : [];
      setPricelists(Array.isArray(pl)?pl:[]);
    });
    if (page === 'crm') return loadMobileScopeOnce('mobile:crm', async () => {
      const ls = (isLeadershipRole || role === 'менеджер_crm') ? await getApi('/crm/lead-summaries') : [];
      setLeads(Array.isArray(ls)?ls:[]);
    });
    if (page === 'analytics') return loadMobileScopeOnce('mobile:analytics', async () => {
      if (canLoadEstimates) markEstimatesLoading(true);
      const [pp,me,wj,est] = await Promise.all([
        isFinanceRole ? getApi('/project-payments') : Promise.resolve([]),
        isFinanceRole ? getApi('/expenses') : Promise.resolve([]),
        role === 'поставщик' ? Promise.resolve([]) : getApi(pagedPath('/work-journal', {limit: WORK_JOURNAL_PAGE_LIMIT})),
        canLoadEstimates ? getApi(estimatesLoadPath, null) : Promise.resolve(null),
      ]);
      setProjectPayments(Array.isArray(pp)?pp:[]);
      setManualExpenses(Array.isArray(me)?me:[]);
      const safeWorkJournal = Array.isArray(wj) ? wj : [];
      setWorkJournal(safeWorkJournal);
      resetWorkJournalPage(safeWorkJournal);
      applyLoadedEstimates(est, canLoadEstimates);
      if (canLoadEstimates && est === null) mobileLoadedScopesRef.current.delete('mobile:analytics');
    });
    if (page === 'settings') return loadMobileScopeOnce('mobile:settings', async () => {
      const [cr,cd] = await Promise.all([
        role === 'поставщик' ? Promise.resolve({}) : getApi('/company-requisites', {}),
        isFinanceRole ? getApi('/company-documents') : Promise.resolve([]),
      ]);
      setCompanyRequisites(cr || {});
      setCompanyDocuments(Array.isArray(cd)?cd:[]);
    });
    if (page === 'activitylog') return loadMobileScopeOnce('mobile:activitylog', async () => {
      const aud = (isLeadershipRole || isFinanceRole) ? await getApi(pagedPath('/audit-log', {limit: AUDIT_LOG_PAGE_LIMIT})) : [];
      setAuditLog(Array.isArray(aud) ? aud : []);
    });
    if (page === 'companychat') return undefined;
  };
};
