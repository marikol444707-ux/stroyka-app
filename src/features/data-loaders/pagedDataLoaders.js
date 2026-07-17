export const createPagedDataLoaders = ({
  MATERIAL_NORMS_PAGE_LIMIT,
  MATERIALS_PAGE_LIMIT,
  WORK_JOURNAL_PAGE_LIMIT,
  createMaterialNormsPageState,
  createMaterialsPageState,
  createWorkJournalPageState,
  getApi,
  mergeRowsById,
  pagedPath,
  setMaterialNorms,
  setMaterialNormsPage,
  setMaterials,
  setMaterialsPage,
  setWorkJournal,
  setWorkJournalPage,
}) => {
  const loadMaterialsPage = async ({projectName = '', search = '', offset = 0} = {}) => {
    setMaterialsPage(prev => ({...prev, projectName, search, loading: true, error: ''}));
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
        loading: false,
        error: '',
      });
      return rows;
    } catch (error) {
      setMaterialsPage(prev => ({
        ...prev,
        loading: false,
        error: 'Не удалось загрузить материалы',
      }));
      return [];
    }
  };

  const loadMaterialNormsPage = async ({search = '', offset = 0} = {}) => {
    setMaterialNormsPage(prev => ({...prev, search, loading: true, error: ''}));
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
        loading: false,
        error: '',
      });
      return rows;
    } catch (error) {
      setMaterialNormsPage(prev => ({
        ...prev,
        loading: false,
        error: 'Не удалось загрузить нормы',
      }));
      return [];
    }
  };

  const workJournalPageState = (params = {}) => (
    createWorkJournalPageState(params, WORK_JOURNAL_PAGE_LIMIT)
  );

  const loadWorkJournalPage = async ({
    projectName = '',
    search = '',
    dateFrom = '',
    dateTo = '',
    offset = 0,
  } = {}) => {
    setWorkJournalPage(prev => ({
      ...prev,
      projectName,
      search,
      dateFrom,
      dateTo,
      loading: true,
      error: '',
    }));
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
        loading: false,
        error: '',
      }));
      return rows;
    } catch (error) {
      setWorkJournalPage(prev => ({
        ...prev,
        loading: false,
        error: 'Не удалось загрузить ЖПР',
      }));
      return [];
    }
  };

  const resetWorkJournalPage = (rows = []) => {
    setWorkJournalPage(workJournalPageState({rows, loading: false, error: ''}));
  };

  const resetMaterialNormsPage = (rows = []) => {
    setMaterialNormsPage(createMaterialNormsPageState(
      {rows, loading: false, error: ''},
      MATERIAL_NORMS_PAGE_LIMIT,
    ));
  };

  const resetMaterialsPage = (rows = []) => {
    setMaterialsPage(createMaterialsPageState(
      {rows, loading: false, error: ''},
      MATERIALS_PAGE_LIMIT,
    ));
  };

  return {
    loadMaterialNormsPage,
    loadMaterialsPage,
    loadWorkJournalPage,
    resetMaterialNormsPage,
    resetMaterialsPage,
    resetWorkJournalPage,
  };
};
