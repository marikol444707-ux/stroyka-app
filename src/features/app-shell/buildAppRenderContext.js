import { buildAppMenuItems } from '../../components/AppMenuItems';
import AppPageFallback from '../../components/AppPageFallback';
import { ESTIMATE_PACKAGES, EXPENSE_CATEGORIES, SURFACES, UNITS } from '../../constants/catalogs';
import { PD_CONSENT_TEXT } from '../../constants/documentTemplates';
import { ROLE_LABELS } from '../../constants/roles';
import { createEstimatePageActions } from '../estimates/estimatePageActions';
import { parseAiTaskPayload } from '../../utils/aiControlDescriptionUtils';
import { calcVat, daysInMonth, doPrint, generateQR, readApiResult } from '../../utils/appRuntimeUtils';
import { cableTypeOf, isCableName } from '../../utils/cableUtils';
import { normalizeDocDate, workDocDate } from '../../utils/documentFormatUtils';
import { EMPTY_ESTIMATE_CHANGE, isApprovedEstimateChangeStatus, signedEstimateChangeTotal } from '../../utils/estimateChangeUtils';
import {
  activeEstimateFromList,
  applyEstimateActivationState,
  buildEstimateWorkSummary,
  enrichEstimateMeasurementBasis,
  estimateDisplayVersion,
  estimateGroupKey,
  estimateImportedPlanMeasure,
  estimateIssueDomId,
  estimateItemDoneTotal,
  estimateItemMaterialSum,
  estimateItemTotal,
  estimateItemTypeMeta,
  estimateItemWorkSum,
  estimateKind,
  estimateMaterialPlanIssue,
  estimateMeasurementBasisMeta,
  estimateMeasurementBasisOf,
  estimatePackage,
  estimateSectionsOf as _sectionsOfEst,
  estimateTotal,
  estimateTypeIcon,
  estimateUpdatedTs,
  estimateVersionChain,
  estimateWorkKey,
  isArchivedEstimate,
  isEstimateMaterialItem,
  isEstimatePricelist,
  isEstimateWorkItem,
  isGlobalEstimateTemplate,
  normalizeEstimateImportSections,
  normalizeEstimateItemType,
  sameEstimateGroup
} from '../../utils/estimateUtils';
import { estimateQualityRows } from '../../utils/estimateReviewUtils';
import { exportToExcelFile } from '../../utils/exportUtils';
import {
  convertUnits,
  materialNormCanCreateSupply,
  materialNormCoverageComment,
  materialNormCoverageDisplayRows,
  materialNormCoverageExportRows,
  materialNormRuleForCalc,
  materialTitleForNormRule
} from '../../utils/materialNormUtils';
import { _normalizeUnit, denormalizeMeasure, fmtMeasure, normalizeMeasure, toNum } from '../../utils/measureUtils';
import { calcDoorArea, calcDoorReveals, calcWindowArea, calcWindowReveals } from '../../utils/roomMeasurementUtils';
import { estimateStatusView, materialControlStatus, materialNormCoverageMeta, materialNormStatus } from '../../utils/statusMetaUtils';
import { isSameSupplyMaterial, parseOfferItems, parseSupplyItems, supplyRequestOrigin, supplyUnitKey } from '../../utils/supplyUtils';
import { buildAppShellProps } from './buildAppShellProps';
import { buildEstimatesPageContext } from './buildEstimatesPageContext';
import { buildProjectsPageContext } from './buildProjectsPageContext';
import { renderAppEarlyRoleRoute } from './renderAppEarlyRoleRoute';

export function buildAppRenderContext({
  API,
  actionGroups = {},
  aiAssistantState = {},
  appBusinessRuntime = {},
  appCoreRuntime = {},
  appMainState = {},
  authEntryState = {},
  estimateWorkflowState = {},
  layout = {},
  materialNormsState = {},
  pageActions = {},
  paymentUiState = {},
  refs = {},
  shellOverlayState = {},
  supplyWorkflowState = {},
  ui = {},
  user
}) {
  const {
    activePage,
    brigadeContracts,
    contracts,
    estimatesList,
    materials,
    notifications,
    projects,
    selectedEstimate,
    staff,
    setEstimatesList,
    setEstimatesTab,
    setSelectedEstimate
  } = appMainState;
  const {
    aiMessages,
    setAiInput,
    setAiLoading,
    setAiMessages
  } = aiAssistantState;
  const {
    estimateChatInput,
    estimateChatLoading,
    estimateChatMessages,
    executionPriceFillPercent,
    newEstimate,
    setDistributeAssignments,
    setDistributeBrigades,
    setEstimateChatInput,
    setEstimateChatLoading,
    setEstimateChatMessages,
    setEstimateVersions,
    setExecutionPriceFillPercent,
    setImportValidating,
    setImportValidationWarnings,
    setSelectedVersionsToCompare,
    setShowDistribute,
    setShowEstimateChat,
    setShowVersionHistory,
    setShowWorkAssignment
  } = estimateWorkflowState;
  const {
    setShowAiChat
  } = shellOverlayState;
  const {
    myNotifications,
    appendPhotos,
    checkinGeo,
    closeNotifications,
    confirmMaterialReceipt,
    getNotifPage,
    handleLogin,
    handleLogout,
    handleRegister,
    handleTwoFactorLogin,
    loadAll,
    loadPricelistItems,
    markMyNotificationsRead,
    navigateTo,
    notify,
    refreshData,
    returnMaterialToProject,
    saveProfile,
    selectableActiveProjects,
    sendCompanyChatMessage,
    toggleNotifications,
    uploadPhoto,
    visibleEstimatesForCurrentUser
  } = appCoreRuntime;
  const readMyNotifications = typeof myNotifications === 'function' ? myNotifications : () => [];
  const {
    activeEstimatesForProject,
    acceptAiTask,
    autoFillNormMaterialsForWork,
    autoReconcileEstimateChanges,
    buildEstimateDiffContent,
    closeAiTask,
    computeNotifications,
    createAiTask,
    createEstimateReconciliation,
    estimateDiffBaseFor,
    estimateItemOptionsForProject,
    estimateListWithUpdatedEstimate,
    formatSignedRub,
    isLeadership,
    isMasterRole,
    isPersonalMaterialRole,
    materialAvailabilityMapForWork,
    materialHintForProject,
    materialNameKey,
    materialNormForWork,
    materialRowsAvailableForWork,
    materialSuggestionsForWork,
    openAiTaskAction,
    personalMaterialRowsForProject,
    projectPlanDone,
    projectRealProgress,
    queueEstimateDiffReviewTask,
    queueEstimateNormReviewTask,
    queueEstimateQualityReviewTask,
    removeEstimateWorkMaterial,
    removeSelectedWorkMaterial,
    renderMaterialWriteoffStatus,
    roleColor,
    roomMeasurementCheck,
    roomMeasurementMessage,
    submitAiTaskReport,
    updateEstimateWorkMaterialQty,
    updateSelectedWorkMaterialQty,
    upsertEstimateWorkMaterial,
    upsertSelectedWorkMaterial,
    workNeedsThicknessParam
  } = appBusinessRuntime;
  const {
    documentActions,
    personnelActions,
    pricelistActions,
    projectCrudActions,
    projectOperationActions,
    supplyActions,
    supplyPlanningUi,
    userAccessActions,
    warehouseActions,
    workJournalActions
  } = actionGroups;
  const {
    buildActContent,
    buildCableJournalContent,
    buildContractContent,
    buildHiddenActContent,
    buildKS3Content,
    buildPrescriptionContent,
    buildSupervisorMonthlyReport,
    buildSupplementaryAgreementContent,
    showKS2
  } = documentActions;
  const { updateProjectProgress } = projectCrudActions;
  const { addMasterWorks, submitEstimateWorkDone } = workJournalActions;
  const {
    createInvoiceFromOffer,
    createShipmentFromOffer,
    createSupplyReq,
    deleteSupplyTemplate,
    fetchPriceHint,
    saveSupplyTemplate,
    applySupplyTemplate
  } = supplyActions;
  const {
    renderSupplyPlanningHint,
    renderSupplyRequestOrigin
  } = supplyPlanningUi;
  const {
    fileSrc,
    matchSearch,
    nextEstimateVersionFor
  } = pageActions;
  const {
    persistEstimate,
    showPreview
  } = pageActions;
  const {
    chatEndRef,
    sidebarRef
  } = refs;
  const {
    isCompactHeader,
    isMobile
  } = layout;
  const {
    C,
    aiNotice,
    aiNoticeIcon,
    aiNoticeText,
    badge,
    btnB,
    btnG,
    btnGr,
    btnO,
    btnR,
    btnState,
    card,
    darkMode,
    setDarkMode,
    inp,
    tbl,
    tblC,
    tblH
  } = ui;
  const notificationItems = readMyNotifications(notifications);
  const unreadNotifications = (Array.isArray(notificationItems) ? notificationItems : []).filter((n) => !n.read).length;
  const exportToExcel = exportToExcelFile;
  const allMenuItems = buildAppMenuItems();
  const pageFallback = <AppPageFallback C={C} card={card} isMobile={isMobile} />;

  const estimatePageActions = createEstimatePageActions({
    API,
    ROLE_LABELS,
    applyEstimateActivationState,
    aiMessages,
    autoReconcileEstimateChanges,
    brigadeContracts,
    buildEstimateDiffContent,
    contracts,
    createEstimateReconciliation,
    enrichEstimateMeasurementBasis,
    estimateDiffBaseFor,
    estimateItemMaterialSum,
    estimateItemTotal,
    estimateItemTypeMeta,
    estimateItemWorkSum,
    estimateChatInput,
    estimateChatLoading,
    estimateChatMessages,
    estimateListWithUpdatedEstimate,
    estimateMeasurementBasisMeta,
    estimateMeasurementBasisOf,
    estimateQualityRows,
    executionPriceFillPercent,
    exportToExcel,
    estimatesList,
    isGlobalEstimateTemplate,
    isLeadership,
    isEstimateWorkItem,
    materials,
    newEstimate,
    nextEstimateVersionFor,
    normalizeEstimateImportSections,
    normalizeEstimateItemType,
    projects,
    queueEstimateDiffReviewTask,
    queueEstimateNormReviewTask,
    queueEstimateQualityReviewTask,
    readApiResult,
    sameEstimateGroup,
    selectedEstimate,
    setAiInput,
    setAiLoading,
    setAiMessages,
    setDistributeAssignments,
    setDistributeBrigades,
    setEstimateChatInput,
    setEstimateChatLoading,
    setEstimateChatMessages,
    setEstimateVersions,
    setEstimatesList,
    setEstimatesTab,
    setExecutionPriceFillPercent,
    setImportValidating,
    setImportValidationWarnings,
    setSelectedEstimate,
    setSelectedVersionsToCompare,
    setShowAiChat,
    setShowDistribute,
    setShowEstimateChat,
    setShowVersionHistory,
    setShowWorkAssignment,
    showPreview,
    staff,
    toNum,
    user
  });

  const appShellUi = {
    C,
    aiNotice,
    aiNoticeIcon,
    aiNoticeText,
    badge,
    btnB,
    btnG,
    btnGr,
    btnO,
    btnR,
    btnState,
    card,
    darkMode,
    setDarkMode,
    inp,
    isCompactHeader,
    isMobile,
    tbl,
    tblC,
    tblH
  };

  const appShellSelectors = {
    EMPTY_ESTIMATE_CHANGE,
    ESTIMATE_PACKAGES,
    _normalizeUnit,
    _sectionsOfEst,
    activeEstimateFromList,
    applyEstimateActivationState,
    buildEstimateWorkSummary,
    cableTypeOf,
    calcDoorArea,
    calcDoorReveals,
    calcVat,
    calcWindowArea,
    calcWindowReveals,
    convertUnits,
    daysInMonth,
    denormalizeMeasure,
    doPrint,
    enrichEstimateMeasurementBasis,
    estimateDisplayVersion,
    estimateGroupKey,
    estimateImportedPlanMeasure,
    estimateIssueDomId,
    estimateItemDoneTotal,
    estimateItemMaterialSum,
    estimateItemOptionsForProject,
    estimateItemTotal,
    estimateItemTypeMeta,
    estimateItemWorkSum,
    estimateKind,
    estimateMaterialPlanIssue,
    estimateMeasurementBasisMeta,
    estimateMeasurementBasisOf,
    estimatePackage,
    estimateQualityRows,
    estimateStatusView,
    estimateTotal,
    estimateTypeIcon,
    estimateUpdatedTs,
    estimateVersionChain,
    estimateWorkKey,
    exportToExcel,
    fileSrc,
    fmtMeasure,
    formatSignedRub,
    generateQR,
    isApprovedEstimateChangeStatus,
    isArchivedEstimate,
    isCableName,
    isEstimateMaterialItem,
    isEstimatePricelist,
    isEstimateWorkItem,
    isGlobalEstimateTemplate,
    isSameSupplyMaterial,
    materialControlStatus,
    materialNormCanCreateSupply,
    materialNormCoverageComment,
    materialNormCoverageDisplayRows,
    materialNormCoverageExportRows,
    materialNormCoverageMeta,
    materialNormRuleForCalc,
    materialNormStatus,
    materialTitleForNormRule,
    matchSearch,
    nextEstimateVersionFor,
    normalizeDocDate,
    normalizeEstimateImportSections,
    normalizeEstimateItemType,
    normalizeMeasure,
    parseAiTaskPayload,
    parseOfferItems,
    parseSupplyItems,
    readApiResult,
    sameEstimateGroup,
    signedEstimateChangeTotal,
    supplyRequestOrigin,
    supplyUnitKey,
    toNum,
    workDocDate
  };

  const earlyRoleRoute = renderAppEarlyRoleRoute({
    constants: { EXPENSE_CATEGORIES, PD_CONSENT_TEXT, ROLE_LABELS, SURFACES, UNITS },
    data: {
      actions: {
        acceptAiTask, addMasterWorks, appendPhotos, applySupplyTemplate, autoFillNormMaterialsForWork,
        checkinGeo, closeAiTask, closeNotifications, confirmMaterialReceipt, createAiTask,
        createInvoiceFromOffer, createShipmentFromOffer, createSupplyReq, deleteSupplyTemplate, fetchPriceHint,
        getNotifPage, handleLogin, handleLogout, handleRegister, handleTwoFactorLogin,
        loadAll, loadPricelistItems, markMyNotificationsRead, myNotifications: readMyNotifications, navigateTo,
        notify, openAiTaskAction, refreshData, removeEstimateWorkMaterial, removeSelectedWorkMaterial,
        renderMaterialWriteoffStatus, renderSupplyPlanningHint, renderSupplyRequestOrigin,
        returnMaterialToProject, roleColor, saveProfile, saveSupplyTemplate,
        selectableActiveProjects, sendCompanyChatMessage, showPreview, submitEstimateWorkDone,
        submitAiTaskReport,
        toggleNotifications, updateEstimateWorkMaterialQty, updateProjectProgress,
        updateSelectedWorkMaterialQty, uploadPhoto, upsertEstimateWorkMaterial,
        upsertSelectedWorkMaterial, visibleEstimatesForCurrentUser
      },
      appMainState,
      authEntryState,
      builders: {
        buildActContent, buildCableJournalContent, buildContractContent, buildHiddenActContent,
        buildKS3Content, buildPrescriptionContent, buildSupervisorMonthlyReport,
        buildSupplementaryAgreementContent, showKS2
      },
      materialRuntime: {
        isPersonalMaterialRole, materialAvailabilityMapForWork, materialHintForProject,
        materialNameKey, materialNormForWork, materialRowsAvailableForWork,
        materialSuggestionsForWork, personalMaterialRowsForProject, workNeedsThicknessParam
      },
      paymentUiState,
      projectRuntime: {
        activeEstimatesForProject, computeNotifications, projectPlanDone, roomMeasurementCheck,
        roomMeasurementMessage
      },
      supplyWorkflowState,
      user
    },
    pageFallback,
    selectors: {
      cableTypeOf, doPrint, estimateItemDoneTotal, estimateItemMaterialSum, estimateItemTotal,
      estimatePackage, estimateWorkKey, fileSrc, fmtMeasure, isApprovedEstimateChangeStatus,
      isMasterRole, matchSearch, materialControlStatus, materialNormStatus, normalizeMeasure,
      parseSupplyItems, projectRealProgress, sectionsOfEstimate: _sectionsOfEst,
      supplyRequestOrigin, toNum, unreadNotifications
    },
    ui: { API, C, badge, btnB, btnG, btnGr, btnO, btnR, card, inp, isMobile, tbl, tblC, tblH }
  });

  if (earlyRoleRoute) {
    return {
      appShellProps: null,
      earlyRoleRoute
    };
  }

  const estimatesPageContext = buildEstimatesPageContext({
    API,
    actions: { exportToExcel, persistEstimate, showPreview },
    appMainState,
    businessRuntime: appBusinessRuntime,
    coreRuntime: appCoreRuntime,
    estimatePageActions,
    estimateWorkflowState,
    layout: { isMobile },
    materialNormsState,
    selectors: appShellSelectors,
    ui: appShellUi
  });

  const projectsPageContext = buildProjectsPageContext({
    API,
    actions: { showPreview },
    appMainState,
    businessRuntime: appBusinessRuntime,
    coreRuntime: appCoreRuntime,
    documentActions,
    layout: { isMobile },
    paymentUiState,
    projectCrudActions,
    projectOperationActions,
    selectors: appShellSelectors,
    ui: appShellUi,
    warehouseActions,
    workJournalActions
  });

  const appShellProps = buildAppShellProps({
    API,
    activePage,
    aiAssistantState,
    allMenuItems,
    appMainState,
    authEntryState,
    businessRuntime: appBusinessRuntime,
    coreRuntime: appCoreRuntime,
    dashboardActions: { showPreview },
    documentActions,
    estimatePageActions,
    estimateWorkflowState,
    estimatesPageContext,
    layout: { isCompactHeader, isMobile },
    materialNormsState,
    pageFallback,
    paymentUiState,
    personnelActions,
    pricelistActions,
    projectCrudActions,
    projectOperationActions,
    projectsPageContext,
    refs: { chatEndRef, sidebarRef },
    selectors: appShellSelectors,
    shellOverlayState,
    supplyActions,
    supplyPlanningUi,
    supplyWorkflowState,
    ui: appShellUi,
    user,
    userAccessActions,
    warehouseActions,
    workJournalActions
  });

  return {
    appShellProps,
    earlyRoleRoute
  };
}
