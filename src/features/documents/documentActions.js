import { buildPerformerContractHtml } from '../../utils/contractTemplates';
import { buildInvoicePrintPayload } from '../../utils/accountingInvoices';
import { createAppPrintBuilders, createPrintDocContext } from '../../utils/appPrintBuilders';
import {
  buildBrigadeActDocContent,
  buildCableJournalDocContent,
  buildDailyObjectReportDocContent,
  buildHiddenActDocContent,
  buildInventoryDocContent,
  buildInvoiceDocContent,
  buildJPRDocContent,
  buildKS2DocContent,
  buildKS3DocContent,
  buildMaterialInspectionDocContent,
  buildMasterActDocContent,
  buildMovementDocContent,
  buildPassportDocContent,
  buildPositionInstructionDocContent,
  buildPrescriptionDocContent,
  buildPricelistDocContent,
  buildTBContentDoc,
  buildWorkJournalDocContent,
} from '../../utils/printDocumentBuilders';

export const createDocumentActions = ({
  accountablePayments,
  activeEstimatesForProject,
  actPayments,
  allBrigadeItems,
  calcDoorArea,
  calcDoorReveals,
  calcVat,
  calcWindowArea,
  calcWindowReveals,
  cableJournal,
  cableTypeOf,
  companyName,
  companyRequisites,
  contractRequisitesWarning,
  estimateChangeRowsForDocs,
  estimateWorkNormRequirementRows,
  expByCategory,
  generateQR,
  getRoomNetWall,
  hiddenActs,
  interimActs,
  isFinanceRole,
  isSupplyDeliveryInvoice,
  ks2ItemsFromEstimate,
  materialInspections,
  materialNormControlSummaryForProject,
  materialReconciliationRows,
  materialTransfers,
  masterProfiles,
  ownExpenses,
  prescriptionsList,
  projectPlanDone,
  projects,
  resolveContractPerformer,
  roomDoors,
  rooms,
  roomWindows,
  showPreview,
  supervisorActs,
  supplierInvoices,
  tbJournal,
  tools,
  user,
  users,
  warehouseInvoiceEstimateControl,
  warehouseInvoiceItems,
  weatherLog,
  workJournal,
}) => {
  const printDocContext = createPrintDocContext({
    companyRequisites,
    companyName,
    projects,
    hiddenActs,
    workJournal,
    projectPlanDone,
    materialInspections,
    cableJournal,
    tbJournal,
    prescriptionsList,
    supplierInvoices,
    interimActs,
    supervisorActs,
    user,
  });

  const appPrintBuilders = createAppPrintBuilders({
    printDocContext,
    projects,
    materialTransfers,
    activeEstimatesForProject,
    materialReconciliationRows,
    estimateWorkNormRequirementRows,
    materialNormControlSummaryForProject,
    workJournal,
  });

  const buildMovementDoc = (movement, items) => buildMovementDocContent(movement, items, {
    companyRequisites,
    companyName,
    userName: user?.name || '',
  });

  const buildInventoryDoc = (inv, items) => buildInventoryDocContent(inv, items, {
    companyRequisites,
    companyName,
  });

  const buildDailyObjectReportContent = (date) => buildDailyObjectReportDocContent(date, {
    companyRequisites,
    companyName,
    user,
    projects,
    workJournal,
  });

  const buildJPRContent = (projectName) => buildJPRDocContent(projectName, {
    companyRequisites,
    companyName,
    projects,
    users,
    workJournal,
    hiddenActs,
    materialInspections,
    prescriptionsList,
    tbJournal,
    cableJournal,
    weatherLog,
  });

  const buildActContent = (act) => buildMasterActDocContent(act, {
    companyRequisites,
    companyName,
    masterProfiles,
    workJournal,
    actPayments,
    tools,
    ownExpenses,
    accountablePayments,
  });

  const showKS2 = (project) => {
    let sourceItems = ks2ItemsFromEstimate(project);
    const confirmedWorks = workJournal.filter(j => j.project === project.name && j.status === 'Подтверждено');
    if (sourceItems.length === 0) sourceItems = confirmedWorks.filter(j => !j.unexpectedWorkId);
    const additionalVolumeItems = estimateChangeRowsForDocs(project.name, 'additional');
    const outsideEstimateItems = estimateChangeRowsForDocs(project.name, 'outside');
    const html = buildKS2DocContent(project, {
      sourceItems,
      additionalVolumeItems,
      outsideEstimateItems,
    }, {
      companyRequisites,
      companyName,
    });
    showPreview(html, 'КС-2 — ' + project.name);
  };

  const buildKS3Content = (project) => buildKS3DocContent(project, {
    companyRequisites,
    companyName,
    ks2ItemsFromEstimate,
    estimateChangeRowsForDocs,
  });

  const buildBrigadeActContent = (bc) => buildBrigadeActDocContent(bc, {
    companyRequisites,
    companyName,
    allBrigadeItems,
  });

  const buildContractContent = (profile, contract, items = []) => {
    const performer = resolveContractPerformer(contract, profile);
    const warning = contractRequisitesWarning(performer, contract?.contractType || contract?.contractorType || performer.contractType);
    const body = buildPerformerContractHtml({
      company: companyRequisites && companyRequisites.fullName ? companyRequisites : companyName,
      performer,
      contract,
      items,
    });
    return warning ? '<div style="border:1px solid #f59e0b;background:#fff7ed;padding:10px 12px;margin-bottom:12px;border-radius:8px;color:#92400e"><b>Внимание:</b> ' + warning + '</div>' + body : body;
  };

  const buildHiddenActContent = (act) => buildHiddenActDocContent(act, {
    companyRequisites,
    companyName,
  });

  const buildWorkJournalContent = (records, projectName, dateFrom, dateTo) => buildWorkJournalDocContent(records, projectName, dateFrom, dateTo, {
    companyRequisites,
    companyName,
    projects,
  });

  const buildMaterialInspectionContent = (records, projectName, dateFrom, dateTo) => buildMaterialInspectionDocContent(records, projectName, dateFrom, dateTo, {
    companyRequisites,
    companyName,
    projects,
  });

  const buildCableJournalContent = (records, projectName, dateFrom, dateTo) => buildCableJournalDocContent(records, projectName, dateFrom, dateTo, {
    companyRequisites,
    companyName,
    projects,
    cableTypeOf,
  });

  const buildPrescriptionContent = (pr) => buildPrescriptionDocContent(pr, {
    companyRequisites,
    companyName,
    project: projects.find(p => p.name === pr.projectName) || {},
  });

  const buildTBContent = (entry) => buildTBContentDoc(entry, {
    companyRequisites,
    companyName,
  });

  const buildPricelistContent = (pl, items) => buildPricelistDocContent(pl, items, {
    companyRequisites,
    companyName,
  });

  const buildPositionInstructionContent = (role, name) => buildPositionInstructionDocContent(role, name, {
    companyRequisites,
    companyName,
  });

  const buildPassportContent = (project) => buildPassportDocContent(project, {
    companyRequisites,
    companyName,
    rooms,
    roomWindows,
    roomDoors,
    expByCategory,
    isFinanceRole,
    getRoomNetWall,
    calcWindowArea,
    calcDoorArea,
    calcWindowReveals,
    calcDoorReveals,
  });

  const buildInvoiceContent = (inv) => {
    const invoiceRows = warehouseInvoiceItems(inv);
    const estimateControlRows = warehouseInvoiceEstimateControl(inv);
    const origin = typeof window === 'undefined' ? '' : window.location.origin;
    return buildInvoiceDocContent(buildInvoicePrintPayload({
      inv,
      invoiceRows,
      estimateControlRows,
      calcVat,
      qrUrl: generateQR(origin + '/?invoice=' + inv.id + '&number=' + inv.number),
      isSupplyDelivery: isSupplyDeliveryInvoice(inv),
    }), printDocContext());
  };

  return {
    ...appPrintBuilders,
    buildActContent,
    buildBrigadeActContent,
    buildCableJournalContent,
    buildContractContent,
    buildDailyObjectReportContent,
    buildHiddenActContent,
    buildInventoryDoc,
    buildInvoiceContent,
    buildJPRContent,
    buildKS3Content,
    buildMaterialInspectionContent,
    buildMovementDoc,
    buildPassportContent,
    buildPositionInstructionContent,
    buildPrescriptionContent,
    buildPricelistContent,
    buildTBContent,
    buildWorkJournalContent,
    printDocContext,
    showKS2,
  };
};
