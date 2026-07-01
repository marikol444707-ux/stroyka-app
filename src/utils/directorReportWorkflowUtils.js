import {
  buildEstimateControlIssues,
  buildEstimateControlReportData,
} from './estimateControlUtils';
import {
  buildSupplyControlIssues,
  buildSupplyControlReportData,
} from './supplyControlReportUtils';
import {
  buildDirectorBriefReportDocContent,
  buildEstimateControlReportDocContent,
  buildSupplyControlReportDocContent,
} from './printDocumentBuilders';

export const buildDirectorBriefReportContentForDate = (date, context) => (
  buildDirectorBriefReportDocContent(date, context)
);

export const buildDirectorEstimateControlIssues = ({
  sourceEstimates,
  projects,
  activeProjects,
  activeEstimatesForProject,
}) => buildEstimateControlIssues({
  sourceEstimates,
  projects,
  activeProjects,
  activeEstimatesForProject,
});

export const buildDirectorEstimateControlReportContent = ({
  sourceEstimates,
  issues,
  companyName,
  generatedBy,
}) => buildEstimateControlReportDocContent(buildEstimateControlReportData({
  sourceEstimates,
  issues,
}), {
  companyName,
  generatedBy,
});

export const buildDirectorSupplyControlIssues = ({
  lowMainStock,
  lowStock,
  supplyRequests,
  supplierInvoices,
  invoices,
  activeProjects,
  warehouseInvoiceEstimateControl,
  invoiceControlNeedsReview,
  invoiceControlProjectName,
  invoiceControlMaterialName,
  invoiceControlReviewReason,
  materialReconciliationRows,
  materialNormControlSummaryForProject,
  fmtMeasure,
  fmtMoney,
}) => buildSupplyControlIssues({
  lowMainStock,
  lowStock,
  supplyRequests,
  supplierInvoices,
  invoices,
  activeProjects,
  warehouseInvoiceEstimateControl,
  invoiceControlNeedsReview,
  invoiceControlProjectName,
  invoiceControlMaterialName,
  invoiceControlReviewReason,
  materialReconciliationRows,
  materialNormControlSummaryForProject,
  fmtMeasure,
  fmtMoney,
});

export const buildDirectorSupplyControlReportContent = ({
  issues,
  supplyRequests,
  supplierOffers,
  supplierInvoices,
  companyName,
  generatedBy,
}) => buildSupplyControlReportDocContent(buildSupplyControlReportData({
  issues,
  supplyRequests,
  supplierOffers,
  supplierInvoices,
}), {
  companyName,
  generatedBy,
});
