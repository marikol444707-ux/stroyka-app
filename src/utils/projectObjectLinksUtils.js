export const buildProjectObjectLinks = ({
  project,
  C,
  estimatesList = [],
  rooms = [],
  projectMeasurements = [],
  measurementRoomDrafts = [],
  workJournal = [],
  hiddenActs = [],
  materialInspections = [],
  cableJournal = [],
  projectDocuments = [],
  projectLetters = [],
  projectPayments = [],
  ownExpenses = [],
  visibleEstimatesForCurrentUser = list => list,
  isArchivedEstimate = () => false,
  activeEstimatesForProject = () => [],
  roomCompleteness = () => ({}),
  materialControlSummaryForProject = () => ({ rows: [], planRows: [], suppliedRows: [] }),
  estimateReconciliationsForProject = () => [],
  aiFindingsForProject = () => [],
  aiTasksForProject = () => [],
  isFinanceRole = () => false,
} = {}) => {
  if (!project) return [];
  const projectName = project.name || '';
  const projectId = Number(project.id);
  const rowProject = row => row?.projectName || row?.project_name || row?.project || row?.location || '';
  const projectRows = list => (list || []).filter(row => (
    rowProject(row) === projectName || (projectId && Number(row?.projectId || row?.project_id) === projectId)
  ));
  const projectEstimates = visibleEstimatesForCurrentUser(estimatesList)
    .filter(estimate => (
      (
        estimate.projectName === projectName
        || estimate.project === projectName
        || (projectId && Number(estimate.projectId) === projectId)
      )
      && !isArchivedEstimate(estimate)
    ));
  const activeEstimateCount = activeEstimatesForProject(project, 'Заказчик').length;
  const projectRooms = (rooms || []).filter(room => room.project === projectName);
  const roomChecks = projectRooms.map(roomCompleteness);
  const missingRooms = roomChecks.filter(item => item.status === 'Не хватает данных').length;
  const measurementDocs = projectRows(projectMeasurements);
  const measurementDrafts = projectRows(measurementRoomDrafts).filter(draft => draft.status === 'Черновик ИИ');
  const projectWorks = (workJournal || []).filter(work => work.project === projectName);
  const pendingWorks = projectWorks.filter(work => !work.status || work.status === 'На проверке' || work.status === 'Автоматически из сметы').length;
  const hiddenCount = projectRows(hiddenActs).length;
  const inspections = projectRows(materialInspections);
  const inspectionPending = inspections.filter(inspection => !inspection.inspected).length;
  const cables = projectRows(cableJournal);
  const cablePending = cables.filter(cable => !cable.installedAt).length;
  const materialSummary = materialControlSummaryForProject(projectName);
  const materialIssues = (materialSummary.toBuyRows?.length || 0)
    + (materialSummary.outsideRows?.length || 0)
    + (materialSummary.mismatchRows?.length || 0)
    + (materialSummary.stockMismatchRows?.length || 0)
    + (materialSummary.usedOverControlRows?.length || 0);
  const docs = projectRows(projectDocuments);
  const letters = projectRows(projectLetters);
  const estimateRecs = estimateReconciliationsForProject(projectName);
  const estimateRecChecks = estimateRecs.reduce((sum, rec) => sum + Number(rec.reviewCount || 0), 0);
  const aiOpen = aiFindingsForProject(projectName).length;
  const aiTasksOpen = aiTasksForProject(projectName).length;
  const payments = projectRows(projectPayments);
  const objectExpenses = (ownExpenses || []).filter(expense => rowProject(expense) === projectName);
  const items = [
    {
      key: 'estimates',
      tab: 'Смета',
      icon: '📋',
      label: 'Сметы',
      count: projectEstimates.length,
      hint: activeEstimateCount + ' активных пакетов',
      status: projectEstimates.length ? 'перейти к сметам' : 'нужно загрузить смету',
      color: projectEstimates.length ? C.success : C.warning,
      bg: projectEstimates.length ? C.successLight : C.warningLight,
      border: projectEstimates.length ? C.successBorder : C.warningBorder,
    },
    {
      key: 'measurements',
      tab: 'Проект / Обмеры',
      icon: '📐',
      label: 'Обмеры',
      count: measurementDocs.length + projectRooms.length,
      hint: projectRooms.length + ' помещений, ' + measurementDocs.length + ' исходников',
      status: missingRooms ? 'неполных помещений: ' + missingRooms : (measurementDrafts.length ? 'черновиков ИИ: ' + measurementDrafts.length : 'обмеры без критики'),
      color: missingRooms ? C.warning : C.success,
      bg: missingRooms ? C.warningLight : C.bg,
      border: missingRooms ? C.warningBorder : C.border,
    },
    {
      key: 'journal',
      tab: 'Производство работ',
      icon: '📖',
      label: 'ЖПР',
      count: projectWorks.length,
      hint: pendingWorks ? pendingWorks + ' на проверке' : 'журнал работ',
      status: pendingWorks ? 'требуется подтверждение' : '',
      color: pendingWorks ? C.warning : C.accent,
      bg: pendingWorks ? C.warningLight : C.bg,
      border: pendingWorks ? C.warningBorder : C.border,
    },
    {
      key: 'materials',
      tab: 'Материалы',
      icon: '📦',
      label: 'Материалы',
      count: materialSummary.rows.length,
      hint: 'план ' + materialSummary.planRows.length + ', поставлено ' + materialSummary.suppliedRows.length,
      status: materialIssues ? 'вопросов: ' + materialIssues : 'сопоставление без критики',
      color: materialIssues ? C.warning : C.success,
      bg: materialIssues ? C.warningLight : C.bg,
      border: materialIssues ? C.warningBorder : C.border,
    },
    {
      key: 'journals',
      tab: 'Главный',
      icon: '📚',
      label: 'Журналы',
      count: hiddenCount + inspections.length + cables.length,
      hint: 'АОСР ' + hiddenCount + ', входной ' + inspections.length + ', кабель ' + cables.length,
      status: (inspectionPending || cablePending) ? 'ожидают проверки/монтажа: ' + (inspectionPending + cablePending) : '',
      color: (inspectionPending || cablePending) ? C.warning : C.accent,
      bg: (inspectionPending || cablePending) ? C.warningLight : C.bg,
      border: (inspectionPending || cablePending) ? C.warningBorder : C.border,
    },
    {
      key: 'estimate-reconciliations',
      tab: 'Сверки смет',
      icon: '🧾',
      label: 'Сверки смет',
      count: estimateRecs.length,
      hint: estimateRecChecks ? 'проверить строк: ' + estimateRecChecks : 'акты сверки редакций',
      status: estimateRecChecks ? 'есть спорные позиции' : '',
      color: estimateRecChecks ? C.warning : C.info,
      bg: estimateRecChecks ? C.warningLight : C.bg,
      border: estimateRecChecks ? C.warningBorder : C.border,
    },
    {
      key: 'documents',
      tab: '📁 Реестр',
      icon: '🗂',
      label: 'Документы',
      count: docs.length + letters.length,
      hint: 'реестр ' + docs.length + ', переписка ' + letters.length,
      color: C.info,
      bg: C.bg,
      border: C.border,
    },
    {
      key: 'ai',
      tab: 'ИИ-контроль',
      icon: '🤖',
      label: 'ИИ-контроль',
      count: aiOpen + aiTasksOpen,
      hint: aiOpen + ' замечаний, ' + aiTasksOpen + ' поручений',
      status: (aiOpen || aiTasksOpen) ? 'есть вопросы к решению' : 'открытых задач нет',
      color: (aiOpen || aiTasksOpen) ? C.warning : C.success,
      bg: (aiOpen || aiTasksOpen) ? C.warningLight : C.successLight,
      border: (aiOpen || aiTasksOpen) ? C.warningBorder : C.successBorder,
    },
  ];

  if (isFinanceRole()) {
    items.push({
      key: 'finance',
      tab: 'Финансы',
      icon: '💰',
      label: 'Финансы',
      count: payments.length + objectExpenses.length,
      hint: payments.length + ' оплат, ' + objectExpenses.length + ' расходов',
      color: C.success,
      bg: C.bg,
      border: C.border,
    });
  }

  return items;
};
