import React from 'react';
import {
  CustomerCabinetPage,
  SupervisorCabinetPage,
} from '../app/lazyComponents';

export default function AppRoleCabinetRoutes({
  user,
  pageFallback,
  ui,
  state,
  actions,
  data,
  builders,
  selectors,
}) {
  const { C, card, btnG, btnB, btnO, btnGr, btnR, inp } = ui;
  const {
    listSearch,
    showForm,
    newSupervisorAct,
    supervisorActPhoto,
    prescriptionPhoto,
    editingAct,
    showPhotoModal,
    previewContent,
    previewTitle,
  } = state;
  const {
    projects,
    workJournal,
    checklists,
    prescriptionsList,
    supervisorActs,
    materialInspections,
    hiddenActs,
    unexpectedWorksList,
    projectStages,
    projectPayments,
    contracts,
  } = data;
  const {
    handleLogout,
    setListSearch,
    showPreview,
    setShowPhotoModal,
    setPrescriptionPhoto,
    appendPhotos,
    refreshData,
    setShowForm,
    setNewSupervisorAct,
    setSupervisorActPhoto,
    setEditingAct,
    setHiddenActs,
    setPreviewContent,
  } = actions;
  const {
    matchSearch,
    projectRealProgress,
    projectPlanDone,
    computeNotifications,
    fmtMeasure,
    fileSrc,
    activeEstimatesForProject,
    estimatePackage,
    sectionsOfEstimate,
    estimateItemMaterialSum,
    estimateItemTotal,
    isApprovedEstimateChangeStatus,
  } = selectors;
  const {
    buildSupervisorMonthlyReport,
    buildPrescriptionContent,
    buildSupplementaryAgreementContent,
    showKS2,
    buildKS3Content,
    doPrint,
  } = builders;

  if (user?.role === 'технадзор') {
    return (
      <React.Suspense fallback={pageFallback}>
        <SupervisorCabinetPage
          user={user}
          projects={projects}
          handleLogout={handleLogout}
          C={C}
          card={card}
          btnG={btnG}
          btnB={btnB}
          btnO={btnO}
          inp={inp}
          listSearch={listSearch}
          setListSearch={setListSearch}
          matchSearch={matchSearch}
          projectRealProgress={projectRealProgress}
          projectPlanDone={projectPlanDone}
          showPreview={showPreview}
          buildSupervisorMonthlyReport={buildSupervisorMonthlyReport}
          computeNotifications={computeNotifications}
          workJournal={workJournal}
          fmtMeasure={fmtMeasure}
          setShowPhotoModal={setShowPhotoModal}
          fileSrc={fileSrc}
          checklists={checklists}
          prescriptionsList={prescriptionsList}
          buildPrescriptionContent={buildPrescriptionContent}
          prescriptionPhoto={prescriptionPhoto}
          setPrescriptionPhoto={setPrescriptionPhoto}
          appendPhotos={appendPhotos}
          refreshData={refreshData}
          showForm={showForm}
          setShowForm={setShowForm}
          newSupervisorAct={newSupervisorAct}
          setNewSupervisorAct={setNewSupervisorAct}
          supervisorActPhoto={supervisorActPhoto}
          setSupervisorActPhoto={setSupervisorActPhoto}
          supervisorActs={supervisorActs}
          materialInspections={materialInspections}
          hiddenActs={hiddenActs}
          editingAct={editingAct}
          setEditingAct={setEditingAct}
          setHiddenActs={setHiddenActs}
          showPhotoModal={showPhotoModal}
          previewContent={previewContent}
          previewTitle={previewTitle}
          setPreviewContent={setPreviewContent}
          doPrint={doPrint}
        />
      </React.Suspense>
    );
  }

  if (user?.role === 'заказчик') {
    return (
      <React.Suspense fallback={pageFallback}>
        <CustomerCabinetPage
          user={user}
          projects={projects}
          handleLogout={handleLogout}
          C={C}
          card={card}
          btnG={btnG}
          btnB={btnB}
          btnO={btnO}
          btnGr={btnGr}
          btnR={btnR}
          inp={inp}
          listSearch={listSearch}
          setListSearch={setListSearch}
          matchSearch={matchSearch}
          computeNotifications={computeNotifications}
          workJournal={workJournal}
          fmtMeasure={fmtMeasure}
          setShowPhotoModal={setShowPhotoModal}
          fileSrc={fileSrc}
          projectRealProgress={projectRealProgress}
          projectStages={projectStages}
          hiddenActs={hiddenActs}
          editingAct={editingAct}
          setEditingAct={setEditingAct}
          setHiddenActs={setHiddenActs}
          unexpectedWorksList={unexpectedWorksList}
          isApprovedEstimateChangeStatus={isApprovedEstimateChangeStatus}
          refreshData={refreshData}
          showPreview={showPreview}
          buildSupplementaryAgreementContent={buildSupplementaryAgreementContent}
          activeEstimatesForProject={activeEstimatesForProject}
          projectPlanDone={projectPlanDone}
          estimatePackage={estimatePackage}
          sectionsOfEstimate={sectionsOfEstimate}
          estimateItemMaterialSum={estimateItemMaterialSum}
          estimateItemTotal={estimateItemTotal}
          showKS2={showKS2}
          buildKS3Content={buildKS3Content}
          projectPayments={projectPayments}
          contracts={contracts}
          prescriptionsList={prescriptionsList}
          showPhotoModal={showPhotoModal}
          previewContent={previewContent}
          previewTitle={previewTitle}
          setPreviewContent={setPreviewContent}
          doPrint={doPrint}
        />
      </React.Suspense>
    );
  }

  return null;
}
