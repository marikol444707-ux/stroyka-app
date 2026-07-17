export const createMobileInitialDataLoader = (deps) => {
  const {
    WORK_JOURNAL_PAGE_LIMIT, dataLoadPolicyForUser, getApi, pagedPath,
    loadMobileScopeOnce, resetWorkJournalPage, applyLoadedEstimates,
    setAiTasks, setAllBrigadeItems, setBrigadeContracts, setCableJournal,
    setContracts, setEstimateReconciliations, setHiddenActs,
    setInitialDataLoaded, setInterimActs, setMasterProfiles,
    setMaterialInspections, setOwnExpenses, setPiecework,
    setProjectDocuments, setProjectMeasurements, setProjectPayments,
    setProjects, setStaff, setSupervisorActs, setSupplyRequests, setUsers,
    setWarehouseMain, setWorkJournal,
  } = deps;

  return async () => {
    try {
      await loadMobileScopeOnce('mobile:init', async () => {
        const {
          role, isFinanceRole, isSupplyRole, isInternalRole, canSeeProjectDocs,
          canLoadEstimates, estimatesLoadPath, canLoadPeopleData: shouldLoadPeopleAtBoot,
          canLoadUserDirectory: shouldLoadUsersAtBoot,
          canLoadAccountingData: shouldLoadAccountingAtBoot,
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
};
