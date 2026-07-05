import {
  activeProjectsOnly,
} from '../../utils/accessUtils';
import {
  buildDirectorBriefReportContentForDate,
  buildDirectorEstimateControlIssues,
  buildDirectorEstimateControlReportContent,
  buildDirectorSupplyControlIssues,
  buildDirectorSupplyControlReportContent,
} from '../../utils/directorReportWorkflowUtils';

export function createDirectorDashboardActions({
  API,
  activeEstimatesForProject,
  companyName,
  estimateList,
  fmtDocMoney,
  fmtMeasure,
  inspectionOrders,
  invoiceControlMaterialName,
  invoiceControlNeedsReview,
  invoiceControlProjectName,
  invoiceControlReviewReason,
  invoices,
  lowMainStock,
  lowStock,
  materialNormControlSummaryForProject,
  materialReconciliationRows,
  normalizeEstimateList,
  ownExpenses,
  projectBudgetSpent,
  projects,
  setEstimatesList,
  showPreview,
  supplierInvoices,
  supplierOffers,
  supplyRequests,
  user,
  warehouseInvoiceEstimateControl,
  workJournal,
}) {
  const noop = () => {};
  const safeProjects = Array.isArray(projects) ? projects : [];
  const safeEstimateList = Array.isArray(estimateList) ? estimateList : [];
  const safeSetEstimatesList = typeof setEstimatesList === 'function' ? setEstimatesList : noop;
  const safeShowPreview = typeof showPreview === 'function' ? showPreview : noop;
  const safeNormalizeEstimateList = typeof normalizeEstimateList === 'function' ? normalizeEstimateList : (list) => list;
  const getActiveEstimatesForProject = typeof activeEstimatesForProject === 'function'
    ? activeEstimatesForProject
    : () => [];
  const safeProjectBudgetSpent = typeof projectBudgetSpent === 'function'
    ? projectBudgetSpent
    : () => ({ works: 0, materials: 0, unexpected: 0, total: 0 });
  const activeDirectorProjects = () => activeProjectsOnly(safeProjects);

  const buildDirectorBriefReportContent = (date) => buildDirectorBriefReportContentForDate(date, {
    companyName,
    user,
    projects: safeProjects,
    workJournal,
    inspectionOrders,
    ownExpenses,
    supplierInvoices,
    lowStock,
    lowMainStock,
    projectBudgetSpent: safeProjectBudgetSpent,
  });

  const estimateControlIssues = (sourceEstimates = safeEstimateList) => buildDirectorEstimateControlIssues({
    sourceEstimates: Array.isArray(sourceEstimates) ? sourceEstimates : [],
    projects: safeProjects,
    activeProjects: activeDirectorProjects(),
    activeEstimatesForProject: getActiveEstimatesForProject,
  });

  const buildEstimateControlReportContent = (sourceEstimates = safeEstimateList) => {
    const safeSourceEstimates = Array.isArray(sourceEstimates) ? sourceEstimates : [];
    const issues = estimateControlIssues(safeSourceEstimates);
    return buildDirectorEstimateControlReportContent({
      sourceEstimates: safeSourceEstimates,
      issues,
      companyName,
      generatedBy: user?.name || '',
    });
  };

  const loadEstimatesForDirectorReport = async () => {
    const allEstimateSectionsLoaded = safeEstimateList.every(estimate => estimate?.sectionsLoaded !== false);
    if (safeEstimateList.length && allEstimateSectionsLoaded) return safeEstimateList;
    try {
      const token = localStorage.getItem('authToken');
      const res = await fetch(API + '/estimates', token ? {headers: {Authorization: 'Bearer ' + token}} : undefined);
      if (!res.ok) return safeEstimateList;
      const data = await res.json();
      const list = Array.isArray(data) ? data : [];
      if (list.length) safeSetEstimatesList(safeNormalizeEstimateList(list));
      return list;
    } catch (e) {
      return safeEstimateList;
    }
  };

  const openEstimateControlReport = async () => {
    const list = await loadEstimatesForDirectorReport();
    safeShowPreview(buildEstimateControlReportContent(list), 'Проверка смет директора');
  };

  const supplyControlIssues = () => buildDirectorSupplyControlIssues({
    lowMainStock,
    lowStock,
    supplyRequests,
    supplierInvoices,
    invoices,
    activeProjects: activeDirectorProjects(),
    warehouseInvoiceEstimateControl,
    invoiceControlNeedsReview,
    invoiceControlProjectName,
    invoiceControlMaterialName,
    invoiceControlReviewReason,
    materialReconciliationRows,
    materialNormControlSummaryForProject,
    fmtMeasure,
    fmtMoney: fmtDocMoney,
  });

  const buildSupplyControlReportContent = () => {
    const issues = supplyControlIssues();
    return buildDirectorSupplyControlReportContent({
      issues,
      supplyRequests,
      supplierOffers,
      supplierInvoices,
      companyName,
      generatedBy: user?.name || '',
    });
  };

  return {
    activeDirectorProjects,
    buildDirectorBriefReportContent,
    buildEstimateControlReportContent,
    buildSupplyControlReportContent,
    estimateControlIssues,
    loadEstimatesForDirectorReport,
    openEstimateControlReport,
    supplyControlIssues,
  };
}
