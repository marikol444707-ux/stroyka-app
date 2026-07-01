import React from 'react';
import {
  ActPaymentModal,
  AiAssistantDrawer,
  BrigadePaymentModal,
  ConfirmWorkAcceptanceModal,
  QrModal,
  RejectEntryModal,
  ToolIssueModal,
  ToolReturnModal,
} from '../app/lazyComponents';

export default function AppActionModals({ ui, constants, state, actions }) {
  const { C, btnG, btnGr, btnO, btnR, card, inp } = ui;
  const { PAYMENT_TYPES, ROLE_LABELS } = constants;
  const {
    actPayments,
    aiChat,
    aiLoading,
    aiMessage,
    chatEndRef,
    confirmAcceptedQty,
    confirmComment,
    confirmingEntry,
    financeUsers,
    issueToolData,
    masterProfiles,
    newBrigadePayment,
    newPayment,
    projects,
    rejectComment,
    rejectingEntry,
    returnToolCondition,
    selectedBrigadeContract,
    showAiAssistant,
    showBrigadePayModal,
    showIssueToolModal,
    showPayActModal,
    showQRModal,
    showReturnToolModal,
  } = state;
  const {
    confirmJ,
    generateQR,
    issueTool,
    normalizeMeasure,
    rejectJ,
    returnTool,
    saveActPayment,
    saveBrigadePayment,
    sendAiMessage,
    setAiMessage,
    setConfirmAcceptedQty,
    setConfirmComment,
    setConfirmingEntry,
    setIssueToolData,
    setNewBrigadePayment,
    setNewPayment,
    setRejectComment,
    setRejectingEntry,
    setReturnToolCondition,
    setShowAiAssistant,
    setShowBrigadePayModal,
    setShowIssueToolModal,
    setShowPayActModal,
    setShowQRModal,
    setShowReturnToolModal,
    toNum,
  } = actions;

  return (
    <>
      {showQRModal && <QrModal showQRModal={showQRModal} setShowQRModal={setShowQRModal} generateQR={generateQR} C={C} btnG={btnG} />}
      {rejectingEntry && <RejectEntryModal rejectingEntry={rejectingEntry} rejectComment={rejectComment} setRejectComment={setRejectComment} setRejectingEntry={setRejectingEntry} rejectJ={rejectJ} C={C} card={card} inp={inp} btnR={btnR} btnG={btnG} />}
      {confirmingEntry && <ConfirmWorkAcceptanceModal confirmingEntry={confirmingEntry} confirmAcceptedQty={confirmAcceptedQty} setConfirmAcceptedQty={setConfirmAcceptedQty} confirmComment={confirmComment} setConfirmComment={setConfirmComment} setConfirmingEntry={setConfirmingEntry} confirmJ={confirmJ} normalizeMeasure={normalizeMeasure} toNum={toNum} C={C} card={card} inp={inp} btnO={btnO} btnG={btnG} />}
      {showIssueToolModal && <ToolIssueModal showIssueToolModal={showIssueToolModal} setShowIssueToolModal={setShowIssueToolModal} C={C} card={card} inp={inp} btnO={btnO} btnG={btnG} issueToolData={issueToolData} setIssueToolData={setIssueToolData} masterProfiles={masterProfiles} projects={projects} issueTool={issueTool} />}
      {showReturnToolModal && <ToolReturnModal showReturnToolModal={showReturnToolModal} setShowReturnToolModal={setShowReturnToolModal} C={C} card={card} inp={inp} btnG={btnG} btnGr={btnGr} returnToolCondition={returnToolCondition} setReturnToolCondition={setReturnToolCondition} returnTool={returnTool} />}
      {showBrigadePayModal && <BrigadePaymentModal showBrigadePayModal={showBrigadePayModal} setShowBrigadePayModal={setShowBrigadePayModal} selectedBrigadeContract={selectedBrigadeContract} C={C} card={card} inp={inp} btnO={btnO} btnG={btnG} newBrigadePayment={newBrigadePayment} setNewBrigadePayment={setNewBrigadePayment} saveBrigadePayment={saveBrigadePayment} />}
      {showPayActModal && <ActPaymentModal showPayActModal={showPayActModal} setShowPayActModal={setShowPayActModal} C={C} card={card} inp={inp} btnO={btnO} btnG={btnG} newPayment={newPayment} setNewPayment={setNewPayment} paymentTypes={PAYMENT_TYPES} financeUsers={financeUsers} roleLabels={ROLE_LABELS} saveActPayment={saveActPayment} actPayments={actPayments} />}
      {showAiAssistant && <AiAssistantDrawer showAiAssistant={showAiAssistant} setShowAiAssistant={setShowAiAssistant} C={C} inp={inp} btnG={btnG} btnO={btnO} aiChat={aiChat} aiLoading={aiLoading} aiMessage={aiMessage} setAiMessage={setAiMessage} sendAiMessage={sendAiMessage} chatEndRef={chatEndRef} />}
    </>
  );
}
