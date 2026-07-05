import React from 'react';
import AppEntryRoutes from '../../components/AppEntryRoutes';
import AppMasterCabinetRoute from '../../components/AppMasterCabinetRoute';
import AppRoleCabinetRoutes from '../../components/AppRoleCabinetRoutes';
import AppSupplierCabinetRoute from '../../components/AppSupplierCabinetRoute';

export function renderAppEarlyRoleRoute({
  constants = {},
  data = {},
  pageFallback,
  selectors = {},
  ui = {},
} = {}) {
  const {
    API,
    C,
    badge,
    btnB,
    btnG,
    btnGr,
    btnO,
    btnR,
    card,
    inp,
    isMobile,
    tbl,
    tblC,
    tblH,
  } = ui;
  const {
    EXPENSE_CATEGORIES,
    PD_CONSENT_TEXT,
    ROLE_LABELS,
    SURFACES,
    UNITS,
  } = constants;
  const {
    actions,
    appMainState,
    authEntryState,
    builders,
    materialRuntime,
    paymentUiState,
    projectRuntime,
    supplyWorkflowState,
    user,
  } = data;
  const currentRole = user?.role || '';
  const isMasterRoleSafe = ['мастер', 'субподрядчик', 'бригадир'].includes(currentRole);

  if (user && isMasterRoleSafe) {
    return (
      <AppMasterCabinetRoute
        pageFallback={pageFallback}
        constants={{ EXPENSE_CATEGORIES, PD_CONSENT_TEXT, ROLE_LABELS, SURFACES, UNITS }}
        ui={{ API, C, badge, btnB, btnG, btnGr, btnO, btnR, card, inp, isMobile }}
        data={{
          accountablePayments: appMainState.accountablePayments,
          activePage: appMainState.activePage,
          aiTasks: appMainState.aiTasks,
          brigadeContracts: appMainState.brigadeContracts,
          brigadeContractItems: appMainState.allBrigadeItems,
          cableJournal: appMainState.cableJournal,
          companyChatMessage: appMainState.companyChatMessage,
          companyMessages: appMainState.companyMessages,
          consentChecked: appMainState.consentChecked,
          contracts: appMainState.contracts,
          estimateDoneDrafts: appMainState.estimateDoneDrafts,
          estimateItemDoneTotal: selectors.estimateItemDoneTotal,
          estimateWorkKey: selectors.estimateWorkKey,
          estimateWorkMaterials: appMainState.estimateWorkMaterials,
          estimateWorkParams: appMainState.estimateWorkParams,
          estimatesList: appMainState.estimatesList,
          expandedProject: appMainState.expandedProject,
          fileSrc: selectors.fileSrc,
          hiddenActs: appMainState.hiddenActs,
          interimActs: appMainState.interimActs,
          isPersonalMaterialRole: materialRuntime.isPersonalMaterialRole,
          listSearch: appMainState.listSearch,
          masterProfile: appMainState.masterProfile,
          masterProfiles: appMainState.masterProfiles,
          masterProjectId: appMainState.masterProjectId,
          materialAvailabilityMapForWork: materialRuntime.materialAvailabilityMapForWork,
          materialControlStatus: selectors.materialControlStatus,
          materialHintForProject: materialRuntime.materialHintForProject,
          materialNameKey: materialRuntime.materialNameKey,
          materialNormForWork: materialRuntime.materialNormForWork,
          materialNormStatus: selectors.materialNormStatus,
          materialRowsAvailableForWork: materialRuntime.materialRowsAvailableForWork,
          materialSuggestionsForWork: materialRuntime.materialSuggestionsForWork,
          materialTransfers: appMainState.materialTransfers,
          myNotifications: actions.myNotifications,
          newOwnExpense: paymentUiState.newOwnExpense,
          newSupplyReq: supplyWorkflowState.newSupplyReq,
          notifications: appMainState.notifications,
          ownExpenses: appMainState.ownExpenses,
          pdConsents: appMainState.pdConsents,
          personalMaterialRowsForProject: materialRuntime.personalMaterialRowsForProject,
          piecework: appMainState.piecework,
          previewContent: appMainState.previewContent,
          previewTitle: appMainState.previewTitle,
          priceHints: appMainState.priceHints,
          pricelistItems: appMainState.pricelistItems,
          pricelists: appMainState.pricelists,
          profileData: appMainState.profileData,
          projects: appMainState.projects,
          rooms: appMainState.rooms,
          selectableActiveProjects: actions.selectableActiveProjects,
          selectedBrigadeContract: appMainState.selectedBrigadeContract,
          selectedWorks: appMainState.selectedWorks,
          showNotifications: appMainState.showNotifications,
          showOwnExpenseForm: paymentUiState.showOwnExpenseForm,
          showPhotoModal: appMainState.showPhotoModal,
          showProfileForm: appMainState.showProfileForm,
          showSupplyForm: supplyWorkflowState.showSupplyForm,
          supplyCollapsedProjects: supplyWorkflowState.supplyCollapsedProjects,
          supplyRequestOrigin: selectors.supplyRequestOrigin,
          supplyRequests: appMainState.supplyRequests,
          supplyTemplates: appMainState.supplyTemplates,
          tools: appMainState.tools,
          unreadNotifications: selectors.unreadNotifications,
          user,
          users: appMainState.users,
          visibleEstimatesForCurrentUser: actions.visibleEstimatesForCurrentUser,
          workJournal: appMainState.workJournal,
          workNeedsThicknessParam: materialRuntime.workNeedsThicknessParam,
        }}
        actions={{
          acceptAiTask: actions.acceptAiTask,
          addMasterWorks: actions.addMasterWorks,
          appendPhotos: actions.appendPhotos,
          applySupplyTemplate: actions.applySupplyTemplate,
          autoFillNormMaterialsForWork: actions.autoFillNormMaterialsForWork,
          buildActContent: builders.buildActContent,
          buildCableJournalContent: builders.buildCableJournalContent,
          buildContractContent: builders.buildContractContent,
          buildHiddenActContent: builders.buildHiddenActContent,
          cableTypeOf: selectors.cableTypeOf,
          checkinGeo: actions.checkinGeo,
          closeNotifications: actions.closeNotifications,
          confirmMaterialReceipt: actions.confirmMaterialReceipt,
          closeAiTask: actions.closeAiTask,
          createAiTask: actions.createAiTask,
          createSupplyReq: actions.createSupplyReq,
          deleteSupplyTemplate: actions.deleteSupplyTemplate,
          doPrint: selectors.doPrint,
          fetchPriceHint: actions.fetchPriceHint,
          fmtMeasure: selectors.fmtMeasure,
          getNotifPage: actions.getNotifPage,
          handleLogout: actions.handleLogout,
          loadAll: actions.loadAll,
          loadPricelistItems: actions.loadPricelistItems,
          markMyNotificationsRead: actions.markMyNotificationsRead,
          matchSearch: selectors.matchSearch,
          navigateTo: actions.navigateTo,
          normalizeMeasure: selectors.normalizeMeasure,
          notify: actions.notify,
          openAiTaskAction: actions.openAiTaskAction,
          parseSupplyItems: selectors.parseSupplyItems,
          refreshData: actions.refreshData,
          removeEstimateWorkMaterial: actions.removeEstimateWorkMaterial,
          removeSelectedWorkMaterial: actions.removeSelectedWorkMaterial,
          renderMaterialWriteoffStatus: actions.renderMaterialWriteoffStatus,
          renderSupplyPlanningHint: actions.renderSupplyPlanningHint,
          renderSupplyRequestOrigin: actions.renderSupplyRequestOrigin,
          returnMaterialToProject: actions.returnMaterialToProject,
          roleColor: actions.roleColor,
          roomMeasurementCheck: projectRuntime.roomMeasurementCheck,
          roomMeasurementMessage: projectRuntime.roomMeasurementMessage,
          saveProfile: actions.saveProfile,
          saveSupplyTemplate: actions.saveSupplyTemplate,
          sendCompanyChatMessage: actions.sendCompanyChatMessage,
          setActivePage: appMainState.setActivePage,
          setCableJournal: appMainState.setCableJournal,
          setCompanyChatMessage: appMainState.setCompanyChatMessage,
          setConsentChecked: appMainState.setConsentChecked,
          setEstimateDoneDrafts: appMainState.setEstimateDoneDrafts,
          setEstimateWorkMaterials: appMainState.setEstimateWorkMaterials,
          setEstimateWorkParams: appMainState.setEstimateWorkParams,
          setEditingAct: appMainState.setEditingAct,
          setExpandedProject: appMainState.setExpandedProject,
          setHiddenActs: appMainState.setHiddenActs,
          setListSearch: appMainState.setListSearch,
          setMasterProjectId: appMainState.setMasterProjectId,
          setNewOwnExpense: paymentUiState.setNewOwnExpense,
          setNewSupplyReq: supplyWorkflowState.setNewSupplyReq,
          setNotifications: appMainState.setNotifications,
          setPreviewContent: appMainState.setPreviewContent,
          setProfileData: appMainState.setProfileData,
          setReportingPayment: paymentUiState.setReportingPayment,
          setSelectedWorks: appMainState.setSelectedWorks,
          setShowNotifications: appMainState.setShowNotifications,
          setShowOwnExpenseForm: paymentUiState.setShowOwnExpenseForm,
          setShowPhotoModal: appMainState.setShowPhotoModal,
          setShowProfileForm: appMainState.setShowProfileForm,
          setShowSupplyForm: supplyWorkflowState.setShowSupplyForm,
          setSupplyCollapsedProjects: supplyWorkflowState.setSupplyCollapsedProjects,
          setUser: authEntryState.setUser,
          showPreview: actions.showPreview,
          submitAiTaskReport: actions.submitAiTaskReport,
          submitEstimateWorkDone: actions.submitEstimateWorkDone,
          toNum: selectors.toNum,
          toggleNotifications: actions.toggleNotifications,
          updateEstimateWorkMaterialQty: actions.updateEstimateWorkMaterialQty,
          updateProjectProgress: actions.updateProjectProgress,
          updateSelectedWorkMaterialQty: actions.updateSelectedWorkMaterialQty,
          uploadPhoto: actions.uploadPhoto,
          upsertEstimateWorkMaterial: actions.upsertEstimateWorkMaterial,
          upsertSelectedWorkMaterial: actions.upsertSelectedWorkMaterial,
        }}
      />
    );
  }

  const isEntryRoute = !user || ['system_owner', 'platform_admin', 'platform_support', 'billing_admin', 'account_owner', 'account_admin'].includes(user.role);
  if (isEntryRoute) {
    return (
      <AppEntryRoutes
        user={user}
        page={authEntryState.page}
        pageFallback={pageFallback}
        ui={{ API, C, badge, btnG, btnGr, btnO, btnR, card, inp }}
        constants={{ ROLE_LABELS }}
        state={{
          email: authEntryState.email,
          loginError: authEntryState.loginError,
          password: authEntryState.password,
          regCode: authEntryState.regCode,
          regEmail: authEntryState.regEmail,
          regInviteInfo: authEntryState.regInviteInfo,
          regName: authEntryState.regName,
          regPassword: authEntryState.regPassword,
          regSupplierData: authEntryState.regSupplierData,
        }}
        actions={{
          handleLogin: actions.handleLogin,
          handleLogout: actions.handleLogout,
          handleRegister: actions.handleRegister,
          handleTwoFactorLogin: actions.handleTwoFactorLogin,
          setEmail: authEntryState.setEmail,
          setLoginError: authEntryState.setLoginError,
          setPage: authEntryState.setPage,
          setPassword: authEntryState.setPassword,
          setRegCode: authEntryState.setRegCode,
          setRegEmail: authEntryState.setRegEmail,
          setRegName: authEntryState.setRegName,
          setRegPassword: authEntryState.setRegPassword,
          setRegSupplierData: authEntryState.setRegSupplierData,
          setUser: authEntryState.setUser,
        }}
      />
    );
  }

  if (user && user.role === 'поставщик') {
    return (
      <AppSupplierCabinetRoute
        constants={{ UNITS }}
        ui={{ API, C, badge, btnB, btnG, btnGr, btnO, btnR, card, inp, tbl, tblC, tblH }}
        data={{
          invoicingOfferId: supplyWorkflowState.invoicingOfferId,
          newCatalogItem: appMainState.newCatalogItem,
          newKpResponse: supplyWorkflowState.newKpResponse,
          newOfferInvoice: supplyWorkflowState.newOfferInvoice,
          respondingOfferId: supplyWorkflowState.respondingOfferId,
          shipmentForm: supplyWorkflowState.shipmentForm,
          shippingOfferId: supplyWorkflowState.shippingOfferId,
          showCatalogForm: appMainState.showCatalogForm,
          supplierCatalog: appMainState.supplierCatalog,
          supplierInvoices: appMainState.supplierInvoices,
          supplierOffers: appMainState.supplierOffers,
          supplierRequisites: appMainState.supplierRequisites,
          supplierTab: appMainState.supplierTab,
          suppliers: appMainState.suppliers,
          supplyClaims: appMainState.supplyClaims,
          supplyDeliveries: appMainState.supplyDeliveries,
          supplyRequests: appMainState.supplyRequests,
          user,
        }}
        actions={{
          createInvoiceFromOffer: actions.createInvoiceFromOffer,
          createShipmentFromOffer: actions.createShipmentFromOffer,
          fileSrc: selectors.fileSrc,
          handleLogout: actions.handleLogout,
          notify: actions.notify,
          parseSupplyItems: selectors.parseSupplyItems,
          refreshData: actions.refreshData,
          setInvoicingOfferId: supplyWorkflowState.setInvoicingOfferId,
          setNewCatalogItem: appMainState.setNewCatalogItem,
          setNewKpResponse: supplyWorkflowState.setNewKpResponse,
          setNewOfferInvoice: supplyWorkflowState.setNewOfferInvoice,
          setRespondingOfferId: supplyWorkflowState.setRespondingOfferId,
          setShipmentForm: supplyWorkflowState.setShipmentForm,
          setShippingOfferId: supplyWorkflowState.setShippingOfferId,
          setShowCatalogForm: appMainState.setShowCatalogForm,
          setSupplierCatalog: appMainState.setSupplierCatalog,
          setSupplierRequisites: appMainState.setSupplierRequisites,
          setSupplierTab: appMainState.setSupplierTab,
          uploadPhoto: actions.uploadPhoto,
        }}
      />
    );
  }

  if (user && ['технадзор', 'стройконтроль', 'заказчик'].includes(user.role)) {
    return (
      <AppRoleCabinetRoutes
        user={user}
        pageFallback={pageFallback}
        ui={{ C, card, btnG, btnB, btnO, btnGr, btnR, inp }}
        state={{
          listSearch: appMainState.listSearch,
          showForm: appMainState.showForm,
          newSupervisorAct: appMainState.newSupervisorAct,
          supervisorActPhoto: appMainState.supervisorActPhoto,
          prescriptionPhoto: appMainState.prescriptionPhoto,
          editingAct: appMainState.editingAct,
          showPhotoModal: appMainState.showPhotoModal,
          previewContent: appMainState.previewContent,
          previewTitle: appMainState.previewTitle,
        }}
        data={{
          projects: appMainState.projects,
          workJournal: appMainState.workJournal,
          checklists: appMainState.checklists,
          prescriptionsList: appMainState.prescriptionsList,
          supervisorActs: appMainState.supervisorActs,
          materialInspections: appMainState.materialInspections,
          hiddenActs: appMainState.hiddenActs,
          unexpectedWorksList: appMainState.unexpectedWorksList,
          projectStages: appMainState.projectStages,
          projectPayments: appMainState.projectPayments,
          contracts: appMainState.contracts,
        }}
        actions={{
          handleLogout: actions.handleLogout,
          setListSearch: appMainState.setListSearch,
          showPreview: actions.showPreview,
          setShowPhotoModal: appMainState.setShowPhotoModal,
          setPrescriptionPhoto: appMainState.setPrescriptionPhoto,
          appendPhotos: actions.appendPhotos,
          refreshData: actions.refreshData,
          setShowForm: appMainState.setShowForm,
          setNewSupervisorAct: appMainState.setNewSupervisorAct,
          setSupervisorActPhoto: appMainState.setSupervisorActPhoto,
          setEditingAct: appMainState.setEditingAct,
          setHiddenActs: appMainState.setHiddenActs,
          setPreviewContent: appMainState.setPreviewContent,
        }}
        selectors={{
          matchSearch: selectors.matchSearch,
          projectRealProgress: selectors.projectRealProgress,
          projectPlanDone: projectRuntime.projectPlanDone,
          computeNotifications: projectRuntime.computeNotifications,
          fmtMeasure: selectors.fmtMeasure,
          fileSrc: selectors.fileSrc,
          activeEstimatesForCurrentUser: projectRuntime.activeEstimatesForProject,
          activeEstimatesForProject: projectRuntime.activeEstimatesForProject,
          estimatePackage: selectors.estimatePackage,
          sectionsOfEstimate: selectors.sectionsOfEstimate,
          estimateItemMaterialSum: selectors.estimateItemMaterialSum,
          estimateItemTotal: selectors.estimateItemTotal,
          isApprovedEstimateChangeStatus: selectors.isApprovedEstimateChangeStatus,
        }}
        builders={{
          buildSupervisorMonthlyReport: builders.buildSupervisorMonthlyReport,
          buildPrescriptionContent: builders.buildPrescriptionContent,
          buildSupplementaryAgreementContent: builders.buildSupplementaryAgreementContent,
          showKS2: builders.showKS2,
          buildKS3Content: builders.buildKS3Content,
          doPrint: selectors.doPrint,
        }}
      />
    );
  }

  return null;
}
