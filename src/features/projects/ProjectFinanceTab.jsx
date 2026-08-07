import React, { useState } from 'react';
import ProjectEventsPanel from './ProjectEventsPanel';

export default function ProjectFinanceTab({
  C,
  EXPENSE_CATEGORIES,
  ProjectFinancePanel,
  accountablePayments,
  btnB,
  btnG,
  btnO,
  btnR,
  card,
  expByCategory,
  fileSrc,
  formatSignedRub,
  isFinanceRole,
  isLeadership,
  inp,
  loadAll,
  manualExpenses,
  ownExpenses,
  project,
  projectPaymentInAmount,
  projectPaymentSignedAmount,
  projectPayments,
  setAddExpenseProject,
  setNewAccountable,
  setNewManualExpense,
  setShowAccountableForm,
  setShowBalanceDetails,
  setShowPhotoModal,
  showBalanceDetails,
  user,
}) {
  const [view, setView] = useState('finance');
  if (!isFinanceRole) return <div />;

  return (
    <div>
      <div style={{display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12}}>
        <button onClick={() => setView('finance')} style={{...btnG, opacity: view === 'finance' ? 1 : 0.68}}>Финансы</button>
        <button onClick={() => setView('events')} style={{...btnG, opacity: view === 'events' ? 1 : 0.68}}>События объекта</button>
      </div>
      {view === 'finance' && <ProjectFinancePanel
        C={C}
        accountablePayments={accountablePayments}
        btnB={btnB}
        btnG={btnG}
        btnO={btnO}
        btnR={btnR}
        canAddExpense={isFinanceRole || user.role === 'прораб'}
        card={card}
        expByCategory={expByCategory}
        expenseCategories={EXPENSE_CATEGORIES}
        fileSrc={fileSrc}
        formatSignedRub={formatSignedRub}
        inp={inp}
        loadAll={loadAll}
        manualExpenses={manualExpenses}
        ownExpenses={ownExpenses}
        project={project}
        projectName={project.name}
        projectPaymentInAmount={projectPaymentInAmount}
        projectPaymentSignedAmount={projectPaymentSignedAmount}
        projectPayments={projectPayments}
        setAddExpenseProject={setAddExpenseProject}
        setNewAccountable={setNewAccountable}
        setNewManualExpense={setNewManualExpense}
        setShowAccountableForm={setShowAccountableForm}
        setShowBalanceDetails={setShowBalanceDetails}
        setShowPhotoModal={setShowPhotoModal}
        showBalanceDetails={showBalanceDetails}
        showProfit={isLeadership}
        user={user}
      />}
      {view === 'events' && <ProjectEventsPanel
        C={C}
        card={card}
        btnG={btnG}
        fileSrc={fileSrc}
        projectName={project.name}
        setShowPhotoModal={setShowPhotoModal}
      />}
    </div>
  );
}
