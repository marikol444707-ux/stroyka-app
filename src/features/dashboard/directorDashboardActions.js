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
  const activeDirectorProjects = () => activeProjectsOnly(projects);

  const buildDirectorBriefReportContent = (date) => buildDirectorBriefReportContentForDate(date, {
    companyName,
    user,
    projects,
    workJournal,
    inspectionOrders,
    ownExpenses,
    supplierInvoices,
    lowStock,
    lowMainStock,
    projectBudgetSpent,
  });

  const estimateControlIssues = (sourceEstimates = estimateList) => buildDirectorEstimateControlIssues({
    sourceEstimates,
    projects,
    activeProjects: activeDirectorProjects(),
    activeEstimatesForProject,
  });

  const buildEstimateControlReportContent = (sourceEstimates = estimateList) => {
    const issues = estimateControlIssues(sourceEstimates);
    return buildDirectorEstimateControlReportContent({
      sourceEstimates,
      issues,
      companyName,
      generatedBy: user?.name || '',
    });
  };

  const loadEstimatesForDirectorReport = async () => {
    if ((estimateList || []).length) return estimateList;
    try {
      const token = localStorage.getItem('authToken');
      const res = await fetch(API + '/estimates?summary=true', token ? {headers: {Authorization: 'Bearer ' + token}} : undefined);
      if (!res.ok) return estimateList || [];
      const data = await res.json();
      const list = Array.isArray(data) ? data : [];
      if (list.length) setEstimatesList(normalizeEstimateList(list));
      return list;
    } catch (e) {
      return estimateList || [];
    }
  };

  const openEstimateControlReport = async () => {
    const list = await loadEstimatesForDirectorReport();
    showPreview(buildEstimateControlReportContent(list), 'Проверка смет директора');
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
