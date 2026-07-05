import MaterialWriteoffStatus from '../../components/MaterialWriteoffStatus';
import { createAiReviewQueueActions } from '../ai-control/aiReviewQueueActions';
import { createAiTaskActions } from '../ai-control/aiTaskActions';
import { createDirectorDashboardActions } from '../dashboard/directorDashboardActions';
import { createProjectDashboardRuntime } from '../dashboard/projectDashboardRuntime';
import { createEstimateWorkflowActions } from '../estimates/estimateWorkflowActions';
import { createProjectEstimateRuntime } from '../estimates/projectEstimateRuntime';
import { createMaterialControlActions } from '../material-control/materialControlActions';
import { createMaterialRuntime } from '../material-control/materialRuntime';
import { createMaterialNormActions } from '../material-norms/materialNormActions';
import { createMaterialNormCoverageActions } from '../material-norms/materialNormCoverageActions';
import { createMaterialWriteoffActions } from '../material-writeoff/materialWriteoffActions';
import { createRoomMeasurementRuntime } from '../project-measurements/roomMeasurementRuntime';
import { canCreateSupplyRequestFromNormForUser, canEditMaterialNormsForUser } from '../../utils/accessUtils';
import { invoiceControlMaterialName, invoiceControlNeedsReview, invoiceControlProjectName, invoiceControlReviewReason } from '../../utils/aiControlDescriptionUtils';
import { buildEstimateDiffDocContent, buildEstimateReconciliationDocContent, fmtDocMoney } from '../../utils/printDocumentBuilders';
import { estimateChangeAutoDecision, estimateChangeReconcileDescription, estimateChangeReconcileMarker, estimateDiffReviewDescription, estimateDiffReviewMarker, estimateNormReviewDescription, estimateNormReviewIssueStatuses, estimateNormReviewMarker, estimateQualityDescription, estimateQualityReviewMarker, estimateQualityRows } from '../../utils/estimateReviewUtils';
import { buildEstimateDiff, estimateKind, estimatePackage, isArchivedEstimate, isGlobalEstimateTemplate, normalizeEstimateList, sameEstimateGroup } from '../../utils/estimateUtils';
import { isActiveSupplyRequestStatus } from '../../utils/supplyUtils';
import { isOpenAiStatus, materialControlStatus, workJournalEstimateStatusMeta } from '../../utils/statusMetaUtils';
import { _normalizeUnit, fmtMeasure, toNum } from '../../utils/measureUtils';
import { createAppRoleRuntime } from './appShellSelectors';
export function useAppBusinessRuntime({
  API,
  user: authUser,
  constants,
  appMainState,
  coreRuntime,
  estimateWorkflowState,
  materialNormsState,
  refs,
  layout,
  ui,
  utilities,
  selectors,
  showPreview,
  persistEstimate
}) {
  const {
    ESTIMATE_PACKAGES,
    EXPENSE_CATEGORIES
  } = constants;
  const {
    isMobile
  } = layout;
  const {
    C,
    badge,
    btnB,
    btnG,
    btnO,
    card,
    tbl,
    tblC,
    tblH
  } = ui;
  const {
    isApprovedEstimateChangeStatus,
    parseSupplyItems,
    visibleEstimatesForCurrentUser
  } = selectors;
  const {
    lowStockFor,
    projectFactSpent
  } = utilities;
  const {
    apiAuthHeaders,
    isFinanceRole,
    navigateTo,
    notify,
    refreshData,
    visibleActiveProjects
  } = coreRuntime;
  const {
    materialNormPreviewSuggestions,
    materialNormSuggestions,
    materialNormCoverageProject,
    newMaterialNorm,
    editingMaterialNormId,
    estimatesTab,
    setEstimatesTab,
    setMaterialNormNotice,
    setNewMaterialNorm,
    setEditingMaterialNormId,
    setMaterialNormSuggestionLoading,
    setMaterialNormPreviewSuggestions
  } = materialNormsState;
  const {
    estimateChangeReconcileQueuedRef,
    estimateDiffReviewQueuedRef,
    estimateNormReviewQueuedRef,
    estimateQualityReviewQueuedRef,
    materialControlTaskQueuedRef,
    roomControlTaskQueuedRef
  } = refs;
  const {
    setEstimateIssueFocusKey
  } = estimateWorkflowState;
  const {
    accountablePayments,
    aiFindings,
    aiTasks,
    allBrigadeItems,
    cableJournal,
    companyName,
    companyRequisites,
    estimateReconciliations,
    expenseReports,
    hiddenActs,
    history,
    inspectionOrders,
    invoices,
    manualExpenses,
    materialAliases,
    materialInspections,
    materialNormOverrides,
    materialNorms,
    materials,
    materialTransfers,
    measurementRoomDrafts,
    ownExpenses,
    piecework,
    prescriptionsList,
    projectDocuments,
    projectLetters,
    projectMeasurements,
    projectPayments,
    projectStages,
    projects,
    roomDoors,
    roomWindows,
    roomWorks,
    rooms,
    selectedEstimate,
    setActivePage,
    setActiveProjectTab,
    setActiveTabGroup,
    setAiFindings,
    setAiTasks,
    setEstimateReconciliations,
    setEstimateWorkMaterials,
    setEstimatesList,
    setExpandedProject,
    setMaterialAliases,
    setSelectedEstimate,
    setSelectedWorks,
    setShowForm,
    setUnexpectedWorksList,
    staff,
    supplierInvoices,
    supplierOffers,
    supplyDeliveries,
    supplyHistory,
    supplyRequests,
    timesheet,
    unexpectedWorksList,
    users,
    warehouseMain,
    warehouseMovements,
    workJournal,
    estimatesList
  } = appMainState;
  const user = authUser || null;
  const aiTaskActions = createAiTaskActions({
    API,
    aiFindings,
    aiTasks,
    buildEstimateDiffContent: (...args) => buildEstimateDiffContent(...args),
    estimateDiffBaseFor: (...args) => estimateDiffBaseFor(...args),
    estimatesList,
    navigateTo: (...args) => navigateTo(...args),
    openEstimateDetail: (...args) => openEstimateDetail(...args),
    projects,
    refreshData,
    setActiveProjectTab,
    setActiveTabGroup,
    setAiFindings,
    setAiTasks,
    setEstimatesTab,
    setExpandedProject,
    setMaterialNormCoverageProject: materialNormsState.setMaterialNormCoverageProject,
    setWarehouseTab: appMainState.setWarehouseTab,
    showPreview
  });
  const {
    aiFindingsForProject,
    aiTasksForProject,
    openAiTaskAction,
    patchAiFindingSilent,
    patchAiTaskSilent,
    updateAiTask
  } = aiTaskActions;
  const estimateWorkflowActions = createEstimateWorkflowActions({
    API,
    estimatesList,
    setEstimatesList,
    setSelectedEstimate,
    estimateReconciliations,
    setEstimateReconciliations,
    unexpectedWorksList,
    isApprovedEstimateChangeStatus,
    buildEstimateDiffDocContent,
    buildEstimateReconciliationDocContent,
    apiAuthHeaders,
    showPreview,
    refreshData,
    user,
    notify,
    setActiveProjectTab,
    setActiveTabGroup,
    setShowForm,
    setActivePage,
    setEstimatesTab,
    queueEstimateDiffReviewTask: (...args) => queueEstimateDiffReviewTask(...args),
    autoReconcileEstimateChanges: (...args) => autoReconcileEstimateChanges(...args),
    queueEstimateQualityReviewTask: (...args) => queueEstimateQualityReviewTask(...args),
    queueEstimateNormReviewTask: (...args) => queueEstimateNormReviewTask(...args)
  });
  const {
    openEstimateDetail,
    estimateDiffBaseFor,
    buildEstimateDiffContent,
    estimateReconciliationsForProject,
    openEstimateReconciliationPreview,
    createEstimateReconciliation,
    approveEstimateReconciliation,
    estimateChangeForComparisonRow,
    createEstimateChangeFromComparisonRow
  } = estimateWorkflowActions;
  const projectEstimateRuntime = createProjectEstimateRuntime({
    ESTIMATE_PACKAGES,
    activeTabActions: {
      openEstimateChanges: () => {
        setActiveProjectTab('Изменения к смете');
        setActiveTabGroup('work');
      }
    },
    approveEstimateReconciliation,
    createEstimateChangeFromComparisonRow,
    createEstimateReconciliation,
    estimateChangeForComparisonRow,
    estimateDiffBaseFor,
    estimateReconciliationsForProject,
    estimatesList,
    openEstimateReconciliationPreview,
    projects,
    rooms,
    roomDoors,
    roomWindows,
    showPreview,
    unexpectedWorksList,
    user,
    visibleEstimatesForCurrentUser,
    workJournal,
    workJournalEstimateStatusMeta
  });
  const {
    activeEstimatesForProject,
    includableEstimateChanges,
    projectPlanDone
  } = projectEstimateRuntime;
  const materialRuntime = createMaterialRuntime({
    activeEstimatesForProject,
    canonicalCompanyName: companyName,
    companyRequisites,
    history,
    invoices,
    materialAliases,
    materialInspections,
    materialNormOverrides,
    materialNorms,
    materials,
    materialTransfers,
    parseSupplyItems,
    projects,
    supplyDeliveries,
    supplyHistory,
    supplyRequests,
    user,
    warehouseMain,
    warehouseMovements,
    workJournal
  });
  const {
    canonicalMaterialMeta,
    estimateNormCoverageRows,
    isPersonalMaterialRole,
    materialAliasCandidates,
    materialAvailabilityMapForWork,
    materialControlSummaryForProject,
    materialNameKey,
    materialNameLookupKey,
    materialNormControlSummaryForProject,
    materialNormForWork,
    materialReconciliationRows,
    materialRowsAvailableForWork,
    warehouseInvoiceEstimateControl
  } = materialRuntime;
  const roomMeasurementRuntime = createRoomMeasurementRuntime({
    C,
    materialNameKey,
    roomDoors,
    roomWindows,
    roomWorks,
    rooms
  });
  const {
    roomCompleteness
  } = roomMeasurementRuntime;
  const aiReviewQueueActions = createAiReviewQueueActions({
    API,
    aiFindings,
    aiTasks,
    buildEstimateDiff,
    estimateChangeAutoDecision,
    estimateChangeReconcileDescription,
    estimateChangeReconcileMarker,
    estimateChangeReconcileQueuedRef,
    estimateDiffBaseFor,
    estimateDiffReviewDescription,
    estimateDiffReviewMarker,
    estimateDiffReviewQueuedRef,
    estimateKind,
    estimateNormCoverageRows,
    estimateNormReviewDescription,
    estimateNormReviewIssueStatuses,
    estimateNormReviewMarker,
    estimateNormReviewQueuedRef,
    estimatePackage,
    estimateQualityDescription,
    estimateQualityReviewMarker,
    estimateQualityReviewQueuedRef,
    estimateQualityRows,
    estimatesList,
    fmtMeasure,
    includableEstimateChanges,
    isArchivedEstimate,
    isGlobalEstimateTemplate,
    isOpenAiStatus,
    materialAliasCandidates,
    materialControlSummaryForProject,
    materialControlTaskQueuedRef,
    materialNameKey,
    materialNormControlSummaryForProject,
    openAiTaskAction,
    patchAiFindingSilent,
    patchAiTaskSilent,
    roomCompleteness,
    roomControlTaskQueuedRef,
    roomWorks,
    rooms,
    sameEstimateGroup,
    selectedEstimate,
    setAiTasks,
    setEstimateIssueFocusKey,
    setUnexpectedWorksList,
    staff,
    user,
    users,
    workJournal
  });
  const {
    aiTaskByMarker,
    autoReconcileEstimateChanges,
    hasActiveEstimator,
    queueEstimateDiffReviewTask,
    queueEstimateNormReviewTask,
    queueEstimateQualityReviewTask
  } = aiReviewQueueActions;
  const materialNormActions = createMaterialNormActions({
    API,
    user,
    projects,
    supplyRequests,
    materialNormPreviewSuggestions,
    materialNormSuggestions,
    materialNormCoverageProject,
    newMaterialNorm,
    editingMaterialNormId,
    estimatesTab,
    isActiveSupplyRequestStatus,
    materialRowsAvailableForWork,
    materialNormForWork,
    capMaterialWriteoffQty: (...args) => capMaterialWriteoffQty(...args),
    materialNameKey,
    visibleActiveProjects,
    canEditMaterialNormsForUser,
    canCreateSupplyRequestFromNormForUser,
    setSupplyRequests: appMainState.setSupplyRequests,
    setMaterialNormNotice,
    setNewMaterialNorm,
    setEditingMaterialNormId,
    setEstimatesTab,
    setMaterialNormSuggestionLoading,
    setMaterialNormPreviewSuggestions,
    setEstimatesList,
    setSelectedEstimate,
    notify,
    refreshData,
    navigateTo: (...args) => navigateTo(...args)
  });
  const {
    canEditMaterialNorms
  } = materialNormActions;
  const materialNormCoverageActions = createMaterialNormCoverageActions({
    API,
    user,
    estimatesList,
    selectedEstimate,
    canEditMaterialNorms,
    sectionsOfEstimate: selectors.sectionsOfEstimate,
    persistEstimate,
    refreshData,
    setAiTasks,
    setEstimatesList,
    setMaterialNormNotice,
    setSelectedEstimate
  });
  const materialWriteoffActions = createMaterialWriteoffActions({
    C,
    MaterialWriteoffStatus,
    canonicalMaterialMeta,
    fmtMeasure,
    isMobile,
    isPersonalMaterialRole,
    materialAvailabilityMapForWork,
    materialNameKey,
    setEstimateWorkMaterials,
    setSelectedWorks
  });
  const {
    capMaterialWriteoffQty
  } = materialWriteoffActions;
  const appRoleRuntime = createAppRoleRuntime({
    piecework,
    timesheet,
    user,
    users
  });
  const {
    calcSalary,
    isLeadership
  } = appRoleRuntime;
  const materialControlActions = createMaterialControlActions({
    API,
    C,
    btnB,
    btnG,
    btnO,
    user,
    materialAliases,
    setMaterialAliases,
    supplyRequests,
    aiTaskByMarker,
    setAiTasks,
    materialNameLookupKey,
    materialAliasCandidates,
    canonicalMaterialMeta,
    materialNameKey,
    warehouseInvoiceEstimateControl,
    openAiTaskAction,
    updateAiTask,
    hasActiveEstimator,
    notify,
    refreshData,
    fmtMeasure,
    toNum,
    _normalizeUnit,
    isLeadership
  });
  const {
    renderMaterialAliasControls,
    renderMaterialSupplyAction
  } = materialControlActions;
  const documentActionRefs = {};
  const projectDashboardRuntime = createProjectDashboardRuntime({
    C,
    EXPENSE_CATEGORIES,
    accountablePayments,
    activeEstimatesForProject,
    aiFindingsForProject,
    aiTasksForProject,
    allBrigadeItems,
    badge,
    btnB,
    buildMaterialRequirementContent: (...args) => documentActionRefs.buildMaterialRequirementContent?.(...args) || '',
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
    prescriptionsList,
    projectDocuments,
    projectFactSpent,
    projectLetters,
    projectMeasurements,
    projectPayments,
    projectPlanDone,
    projectStages,
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
    workJournal
  });
  const {
    projectBudgetSpent
  } = projectDashboardRuntime;
  const lowStock = lowStockFor(materials);
  const lowMainStock = lowStockFor(warehouseMain);
  const directorDashboardActions = createDirectorDashboardActions({
    API,
    activeEstimatesForProject,
    companyName,
    estimateList: estimatesList,
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
    workJournal
  });
  return {
    ...aiTaskActions,
    ...estimateWorkflowActions,
    ...projectEstimateRuntime,
    ...materialRuntime,
    ...roomMeasurementRuntime,
    ...aiReviewQueueActions,
    ...materialNormActions,
    ...materialNormCoverageActions,
    ...materialWriteoffActions,
    ...appRoleRuntime,
    ...materialControlActions,
    ...projectDashboardRuntime,
    ...directorDashboardActions,
    documentActionRefs,
    lowMainStock,
    lowStock
  };
}
