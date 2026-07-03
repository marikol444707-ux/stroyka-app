import React from 'react';
import MaterialReconciliationPanel from '../../components/MaterialReconciliationPanel';
import { buildDirectorMapContract, getDirectorMapActionTarget } from '../director-map';
import {
  buildProjectEconomy,
  projectBudgetSpentSummary,
  projectExpenseCategories,
  projectRealProgressValue,
  workExecutionTotalValue,
} from '../../utils/projectEconomyUtils';
import { buildProjectObjectLinks } from '../../utils/projectObjectLinksUtils';
import { buildComputedNotifications } from '../../utils/notificationUtils';
import { actStatusForJournalWork } from '../../utils/hiddenActUtils';

export function createProjectDashboardRuntime({
  C,
  EXPENSE_CATEGORIES,
  accountablePayments,
  activeEstimatesForProject,
  aiFindingsForProject,
  aiTasksForProject,
  allBrigadeItems,
  badge,
  btnB,
  buildMaterialRequirementContent,
  cableJournal,
  calcSalary,
  card,
  estimatePackage,
  estimateReconciliationsForProject,
  estimatesList,
  expenseReports,
  fmtMeasure,
  hiddenActs,
  invoices,
  isApprovedEstimateChangeStatus,
  isArchivedEstimate,
  isFinanceRole,
  isLeadership,
  manualExpenses,
  materialControlStatus,
  materialControlSummaryForProject,
  materialInspections,
  materials,
  measurementRoomDrafts,
  ownExpenses,
  piecework,
  projectDocuments,
  projectFactSpent,
  projectLetters,
  projectMeasurements,
  projectPayments,
  projectPlanDone,
  projectStages,
  prescriptionsList,
  renderMaterialAliasControls,
  renderMaterialSupplyAction,
  roomCompleteness,
  rooms,
  showPreview,
  staff,
  supplierInvoices,
  supplyDeliveries,
  supplyRequests,
  tbl,
  tblC,
  tblH,
  unexpectedWorksList,
  user,
  visibleEstimatesForCurrentUser,
  workJournal,
}) {
  const expByCategory = (projectName) => projectExpenseCategories({
    projectName,
    expenseCategories: EXPENSE_CATEGORIES,
    materialControlSummaryForProject,
    allBrigadeItems,
    staff,
    piecework,
    calcSalary,
    manualExpenses,
    unexpectedWorksList,
    accountablePayments,
    isApprovedEstimateChangeStatus,
  });

  const projectBudgetSpent = (project) => {
    if (!project) return projectBudgetSpentSummary(null);
    return projectBudgetSpentSummary(project, expByCategory(project.name));
  };

  const projectRealProgress = (project) => projectRealProgressValue({
    project,
    projectPlanDone,
    projectFactSpent,
  });

  const workExecutionTotal = (work) => workExecutionTotalValue(work);

  const projectEconomy = (project) => buildProjectEconomy({
    project,
    projectPlanDone,
    activeEstimatesForProject,
    estimatePackage,
    materialControlSummaryForProject,
    projectBudgetSpent,
    workJournal,
  });

  const projectObjectLinks = (project) => buildProjectObjectLinks({
    project,
    C,
    estimatesList,
    rooms,
    projectMeasurements,
    measurementRoomDrafts,
    workJournal,
    hiddenActs,
    materialInspections,
    cableJournal,
    projectDocuments,
    projectLetters,
    projectPayments,
    ownExpenses,
    visibleEstimatesForCurrentUser,
    isArchivedEstimate,
    activeEstimatesForProject,
    roomCompleteness,
    materialControlSummaryForProject,
    estimateReconciliationsForProject,
    aiFindingsForProject,
    aiTasksForProject,
    isFinanceRole,
  });

  const directorMapActionTarget = ({ item, action } = {}) => getDirectorMapActionTarget({
    item,
    action,
    isFinanceRole,
  });

  const directorMapContractForProject = (project) => buildDirectorMapContract({
    project,
    stages: projectStages,
    estimates: activeEstimatesForProject(project, 'Заказчик').map(estimate => ({
      ...estimate,
      workPackage: estimatePackage(estimate),
    })),
    workJournal,
    materials,
    supplyRequests,
    supplyDeliveries,
    supplierInvoices,
    warehouseInvoices: invoices,
    materialInspections,
    hiddenActs,
    projectPayments,
    materialSummary: materialControlSummaryForProject(project.name),
    planDone: projectPlanDone(project),
    projectProgress: projectRealProgress(project),
  });

  const computeNotifications = () => buildComputedNotifications({
    user,
    expenseReports,
    ownExpenses,
    supplierInvoices,
    unexpectedWorksList,
    hiddenActs,
    prescriptionsList,
    accountablePayments,
  });

  const renderMaterialReconciliationPanel = (projectName, options = {}) => (
    <MaterialReconciliationPanel
      projectName={projectName}
      options={options}
      C={C}
      card={card}
      btnB={btnB}
      tbl={tbl}
      tblH={tblH}
      tblC={tblC}
      badge={badge}
      fmtMeasure={fmtMeasure}
      materialControlSummaryForProject={materialControlSummaryForProject}
      materialControlStatus={materialControlStatus}
      renderMaterialAliasControls={renderMaterialAliasControls}
      renderMaterialSupplyAction={renderMaterialSupplyAction}
      showPreview={showPreview}
      buildMaterialRequirementContent={buildMaterialRequirementContent}
      isFinanceRole={isFinanceRole}
      isLeadership={isLeadership}
      user={user}
    />
  );

  const getActStatusForJournal = (work) => actStatusForJournalWork(work, hiddenActs);

  return {
    computeNotifications,
    directorMapActionTarget,
    directorMapContractForProject,
    expByCategory,
    getActStatusForJournal,
    projectBudgetSpent,
    projectEconomy,
    projectObjectLinks,
    projectRealProgress,
    renderMaterialReconciliationPanel,
    workExecutionTotal,
  };
}
