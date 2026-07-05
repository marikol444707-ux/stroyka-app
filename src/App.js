import React, { useRef } from 'react';
import './App.css';
import { API, installAuthFetch } from './api';
import { AUDIT_LOG_PAGE_LIMIT, MATERIAL_NORMS_PAGE_LIMIT, MATERIALS_PAGE_LIMIT, WORK_JOURNAL_PAGE_LIMIT } from './constants/appConfig';
import { ESTIMATE_PACKAGES, EXPENSE_CATEGORIES } from './constants/catalogs';
import { CHECKLIST_TEMPLATES } from './constants/documentTemplates';
import { ROLES, ROLE_LABELS } from './constants/roles';
import { C, aiNotice, aiNoticeIcon, aiNoticeText, badge, btnB, btnG, btnGr, btnO, btnR, btnState, card, inp, tbl, tblC, tblH } from './constants/uiTheme';
import AppAuthenticatedShell from './components/AppAuthenticatedShell';
import AppErrorBoundary from './components/AppErrorBoundary';
import { buildAppActionGroups } from './features/app-shell/buildAppActionGroups';
import { createAppUtilityRuntime } from './features/app-shell/appShellSelectors';
import { buildAppRenderContext } from './features/app-shell/buildAppRenderContext';
import { useAppBusinessRuntime } from './features/app-shell/useAppBusinessRuntime';
import { useAppCoreRuntime } from './features/app-shell/useAppCoreRuntime';
import { useAppMainState } from './features/app-shell/useAppMainState';
import { useAuthEntryState, useDarkModeState, useResponsiveLayout, useShellOverlayState } from './features/app-shell/useAppShellState';
import { useAiAssistantState } from './features/ai-assistant/useAiAssistantState';
import { persistEstimateAction } from './features/estimates/estimatePersistenceActions';
import { useEstimateExecutionFillPercentSync } from './features/estimates/useEstimateExecutionPricingState';
import { useEstimateWorkflowState } from './features/estimates/useEstimateWorkflowState';
import { useMaterialNormsState } from './features/material-norms/useMaterialNormsState';
import { usePaymentUiState } from './features/payments/usePaymentUiState';
import { useSupplierRequisitesSync } from './features/supply/useSupplierRequisitesSync';
import { useSupplyWorkflowState } from './features/supply/useSupplyWorkflowState';
import { calcVat, generateQR, readApiResult } from './utils/appRuntimeUtils';
import { cableTypeOf } from './utils/cableUtils';
import { EMPTY_ESTIMATE_CHANGE, isApprovedEstimateChangeStatus } from './utils/estimateChangeUtils';
import { estimateExecutionFillPercentOf, estimatePackage, estimateSectionsOf as _sectionsOfEst, estimateWorkKey, nextEstimateVersionFor as nextEstimateVersionForFromList } from './utils/estimateUtils';
import { denormalizeMeasure, fmtMeasure, toNum } from './utils/measureUtils';
import { contractRequisitesWarning } from './utils/performerUtils';
import { calcDoorArea, calcDoorReveals, calcWindowArea, calcWindowReveals } from './utils/roomMeasurementUtils';
import { isSameSupplyMaterial, parseSupplyItems, supplyRequestOrigin, supplyUnitKey } from './utils/supplyUtils';
installAuthFetch();
const GENERAL_WORK_ROOM_NAME = 'Без помещения';
function App() {
  const {
    isMobile,
    isCompactHeader
  } = useResponsiveLayout();
  const mobileLoadedScopesRef = useRef(new Set());
  const mobileApiRequestsRef = useRef(new Map());
  const [darkMode] = useDarkModeState();
  const authEntryState = useAuthEntryState();
  const {
    user
  } = authEntryState;
  const appMainState = useAppMainState();
  const {
    allBrigadeItems,
    estimateWorkMaterials,
    estimateWorkParams,
    estimatesList,
    materials,
    selectedEstimate,
    suppliers,
    workJournal,
    setPreviewContent,
    setPreviewTitle,
    setSupplierRequisites
  } = appMainState;
  useSupplierRequisitesSync({
    setSupplierRequisites,
    suppliers,
    user
  });
  const shellOverlayState = useShellOverlayState();
  const paymentUiState = usePaymentUiState();
  const aiAssistantState = useAiAssistantState();
  const estimateNormReviewQueuedRef = useRef(new Set());
  const estimateQualityReviewQueuedRef = useRef(new Set());
  const estimateDiffReviewQueuedRef = useRef(new Set());
  const estimateChangeReconcileQueuedRef = useRef(new Set());
  const materialControlTaskQueuedRef = useRef(new Set());
  const roomControlTaskQueuedRef = useRef(new Set());
  const supplyWorkflowState = useSupplyWorkflowState();
  const materialNormsState = useMaterialNormsState();
  const {
    fileSrc,
    lowStockFor,
    matchSearch,
    nextEstimateVersionFor,
    projectFactSpent
  } = createAppUtilityRuntime({
    API,
    allBrigadeItems,
    estimatesList,
    materials,
    nextEstimateVersionForFromList,
    workJournal
  });
  const estimateWorkflowState = useEstimateWorkflowState();
  const {
    setEstimateIssueFocusKey,
    setExecutionPriceFillPercent
  } = estimateWorkflowState;
  const selectedEstimateExecutionFillPercent = estimateExecutionFillPercentOf(selectedEstimate);
  useEstimateExecutionFillPercentSync({
    selectedEstimate,
    selectedEstimateExecutionFillPercent,
    setExecutionPriceFillPercent
  });
  const persistEstimate = async est => persistEstimateAction({
    API,
    est,
    estimateListWithUpdatedEstimate,
    estimatesList,
    queueEstimateNormReviewTask,
    queueEstimateQualityReviewTask
  });
  const sidebarRef = useRef(null);
  const chatEndRef = useRef(null);
  const showPreview = (content, title) => {
    setPreviewContent(content);
    setPreviewTitle(title);
  };
  const appCoreRuntime = useAppCoreRuntime({
    API,
    ROLES,
    aiAssistantState,
    appMainState,
    authEntryState,
    layout: {
      isMobile
    },
    limits: {
      AUDIT_LOG_PAGE_LIMIT,
      MATERIAL_NORMS_PAGE_LIMIT,
      MATERIALS_PAGE_LIMIT,
      WORK_JOURNAL_PAGE_LIMIT
    },
    materialNormsState,
    refs: {
      chatEndRef,
      mobileApiRequestsRef,
      mobileLoadedScopesRef
    },
    shellOverlayState
  });
  const {
    apiAuthHeaders,
    isFinanceRole,
    navigateTo,
    notify,
    refreshData,
    visibleActiveProjects,
    visibleEstimatesForCurrentUser
  } = appCoreRuntime;
  const appBusinessRuntime = useAppBusinessRuntime({
    API,
    user,
    constants: {
      ESTIMATE_PACKAGES,
      EXPENSE_CATEGORIES
    },
    appMainState,
    coreRuntime: {
      apiAuthHeaders,
      isFinanceRole,
      navigateTo,
      notify,
      refreshData,
      visibleActiveProjects
    },
    estimateWorkflowState: {
      setEstimateIssueFocusKey
    },
    materialNormsState,
    refs: {
      estimateChangeReconcileQueuedRef,
      estimateDiffReviewQueuedRef,
      estimateNormReviewQueuedRef,
      estimateQualityReviewQueuedRef,
      materialControlTaskQueuedRef,
      roomControlTaskQueuedRef
    },
    layout: {
      isMobile
    },
    ui: {
      C,
      badge,
      btnB,
      btnG,
      btnO,
      card,
      tbl,
      tblC,
      tblH
    },
    utilities: {
      lowStockFor,
      projectFactSpent
    },
    selectors: {
      isApprovedEstimateChangeStatus,
      parseSupplyItems,
      sectionsOfEstimate: _sectionsOfEst,
      visibleEstimatesForCurrentUser
    },
    showPreview,
    persistEstimate
  });
  const {
    estimateListWithUpdatedEstimate,
    queueEstimateNormReviewTask,
    queueEstimateQualityReviewTask
  } = appBusinessRuntime;
  const appActionGroups = buildAppActionGroups({
    API,
    appMainState,
    businessRuntime: appBusinessRuntime,
    constants: {
      CHECKLIST_TEMPLATES,
      EMPTY_ESTIMATE_CHANGE,
      GENERAL_WORK_ROOM_NAME,
      ROLE_LABELS
    },
    coreRuntime: appCoreRuntime,
    documentSelectors: {
      estimatePackage,
      estimateWorkKey,
      fmtMeasure,
      isSameSupplyMaterial,
      parseSupplyItems,
      readApiResult,
      supplyRequestOrigin,
      supplyUnitKey,
      toNum
    },
    estimateRuntime: {
      estimateWorkMaterials,
      estimateWorkParams
    },
    shellOverlayState,
    supplyWorkflowState,
    ui: {
      C,
      btnB,
      btnG
    },
    utilities: {
      calcDoorArea,
      calcDoorReveals,
      calcVat,
      calcWindowArea,
      calcWindowReveals,
      cableTypeOf,
      contractRequisitesWarning,
      denormalizeMeasure,
      generateQR,
      showPreview
    },
    user
  });
  const {
    appShellProps,
    earlyRoleRoute
  } = buildAppRenderContext({
    API,
    actionGroups: appActionGroups,
    aiAssistantState,
    appBusinessRuntime,
    appCoreRuntime,
    appMainState,
    authEntryState,
    estimateWorkflowState,
    layout: {
      isCompactHeader,
      isMobile
    },
    materialNormsState,
    pageActions: {
      fileSrc,
      matchSearch,
      nextEstimateVersionFor,
      persistEstimate,
      showPreview
    },
    paymentUiState,
    refs: {
      chatEndRef,
      sidebarRef
    },
    shellOverlayState,
    supplyWorkflowState,
    ui: {
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
      inp,
      tbl,
      tblC,
      tblH
    },
    user
  });
  const errorBoundaryKey = `${user?.role || 'guest'}:${authEntryState.page || appMainState.activePage || 'app'}`;

  if (earlyRoleRoute) {
    return (
      <AppErrorBoundary resetKey={errorBoundaryKey}>
        {earlyRoleRoute}
      </AppErrorBoundary>
    );
  }

  return (
    <AppErrorBoundary resetKey={errorBoundaryKey}>
      <AppAuthenticatedShell {...appShellProps} />
    </AppErrorBoundary>
  );
}
export default App;
