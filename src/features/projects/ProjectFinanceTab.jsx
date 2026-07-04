import React from 'react';

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
  if (!isFinanceRole) return <div />;

  return (
    <div>
      <ProjectFinancePanel
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
        loadAll={loadAll}
        manualExpenses={manualExpenses}
        ownExpenses={ownExpenses}
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
      />
    </div>
  );
}
