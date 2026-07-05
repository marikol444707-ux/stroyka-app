import React from 'react';
import {
  ActivityLogPage,
  AnalyticsPage,
  CompanyChatPage,
  CrmPage,
  MyExpensesPage,
  SettingsPage,
  WeatherPage,
} from '../app/lazyComponents';

export default function AppSecondaryPages({ activePage, ui, constants, state, actions }) {
  const { API, C, badge, btnB, btnG, btnO, btnR, card, inp, isMobile, tbl, tblC, tblH } = ui;
  const { CRM_STAGES, EXPENSE_CATEGORIES, ROLE_LABELS, WEATHER_CONDITIONS } = constants;
  const {
    accountablePayments,
    activityLog,
    auditLog,
    companyChatMessage,
    companyDocuments,
    companyMessages,
    companyReqForm,
    companyRequisites,
    contracts,
    editingItem,
    expByCategory,
    fileSrc,
    leads,
    newCompanyDoc,
    newLead,
    newWeather,
    ownExpenses,
    projects,
    settingsTab,
    showForm,
    staff,
    suppliers,
    user,
    users,
    weatherLog,
    weatherTab,
    workJournal,
  } = state;
  const {
    appendPhotos,
    buildJPRContent,
    createProjectFromLead,
    deleteLead,
    isFinanceRole,
    loadAll,
    roleColor,
    saveCompanyRequisites,
    saveLead,
    saveWeather,
    sendCompanyChatMessage,
    setCompanyChatMessage,
    setCompanyReqForm,
    setCompanyRequisites,
    setEditingItem,
    setLeads,
    setNewCompanyDoc,
    setNewLead,
    setNewWeather,
    setReportingPayment,
    setSettingsTab,
    setShowForm,
    setShowOwnExpenseForm,
    setShowPhotoModal,
    setWeatherTab,
    showPreview,
    uploadPhoto,
  } = actions;
  const isFinanceUser = typeof isFinanceRole === 'function' ? isFinanceRole() : Boolean(isFinanceRole);

  return (
    <>
      {activePage === 'weather' && (
        <WeatherPage
          C={C}
          WEATHER_CONDITIONS={WEATHER_CONDITIONS}
          btnB={btnB}
          btnG={btnG}
          btnO={btnO}
          buildJPRContent={buildJPRContent}
          card={card}
          inp={inp}
          newWeather={newWeather}
          projects={projects}
          saveWeather={saveWeather}
          setNewWeather={setNewWeather}
          setShowForm={setShowForm}
          setWeatherTab={setWeatherTab}
          showForm={showForm}
          showPreview={showPreview}
          weatherLog={weatherLog}
          weatherTab={weatherTab}
          workJournal={workJournal}
        />
      )}

      {activePage === 'myexpenses' && (
        <MyExpensesPage
          C={C}
          EXPENSE_CATEGORIES={EXPENSE_CATEGORIES}
          accountablePayments={accountablePayments}
          btnO={btnO}
          card={card}
          fileSrc={fileSrc}
          ownExpenses={ownExpenses}
          projectOptions={projects}
          setReportingPayment={setReportingPayment}
          setShowOwnExpenseForm={setShowOwnExpenseForm}
          setShowPhotoModal={setShowPhotoModal}
          user={user}
        />
      )}

      {activePage === 'settings' && isFinanceUser && (
        <SettingsPage
          API={API}
          C={C}
          btnB={btnB}
          btnG={btnG}
          btnO={btnO}
          btnR={btnR}
          card={card}
          companyDocuments={companyDocuments}
          companyReqForm={companyReqForm}
          companyRequisites={companyRequisites}
          inp={inp}
          loadAll={loadAll}
          newCompanyDoc={newCompanyDoc}
          saveCompanyRequisites={saveCompanyRequisites}
          setCompanyReqForm={setCompanyReqForm}
          setCompanyRequisites={setCompanyRequisites}
          setNewCompanyDoc={setNewCompanyDoc}
          setShowForm={setShowForm}
          setShowPhotoModal={setShowPhotoModal}
          settingsTab={settingsTab}
          setSettingsTab={setSettingsTab}
          showForm={showForm}
          uploadPhoto={uploadPhoto}
          user={user}
        />
      )}

      {activePage === 'analytics' && (
        <AnalyticsPage
          C={C}
          badge={badge}
          card={card}
          contracts={contracts}
          expByCategory={expByCategory}
          projects={projects}
          staff={staff}
          suppliers={suppliers}
          tbl={tbl}
          tblC={tblC}
          tblH={tblH}
          workJournal={workJournal}
        />
      )}

      {activePage === 'crm' && (
        <CrmPage
          API={API}
          C={C}
          CRM_STAGES={CRM_STAGES}
          btnG={btnG}
          btnB={btnB}
          btnO={btnO}
          btnR={btnR}
          card={card}
          createProjectFromLead={createProjectFromLead}
          deleteLead={deleteLead}
          editingItem={editingItem}
          inp={inp}
          leads={leads}
          newLead={newLead}
          saveLead={saveLead}
          setEditingItem={setEditingItem}
          setLeads={setLeads}
          setNewLead={setNewLead}
          setShowForm={setShowForm}
          showForm={showForm}
          isMobile={isMobile}
          appendPhotos={appendPhotos}
          uploadPhoto={uploadPhoto}
          fileSrc={fileSrc}
          setShowPhotoModal={setShowPhotoModal}
          users={users}
        />
      )}

      {activePage === 'activitylog' && (
        <ActivityLogPage
          C={C}
          tbl={tbl}
          tblH={tblH}
          tblC={tblC}
          activityLog={activityLog}
          auditLog={auditLog}
          roleLabels={ROLE_LABELS}
          isMobile={isMobile}
        />
      )}

      {activePage === 'companychat' && (
        <CompanyChatPage
          C={C}
          card={card}
          inp={inp}
          btnO={btnO}
          companyMessages={companyMessages}
          user={user}
          roleColor={roleColor}
          fileSrc={fileSrc}
          setShowPhotoModal={setShowPhotoModal}
          companyChatMessage={companyChatMessage}
          setCompanyChatMessage={setCompanyChatMessage}
          uploadPhoto={uploadPhoto}
          sendCompanyChatMessage={sendCompanyChatMessage}
        />
      )}
    </>
  );
}
