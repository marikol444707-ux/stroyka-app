import React from 'react';
import {
  ProjectCableJournalEditModal,
  ProjectHiddenWorksActEditModal,
  ProjectMaterialInspectionEditModal,
  ProjectWorkJournalEditModal,
  ProjectWorkJournalTableModal,
} from '../app/lazyComponents';

export default function AppProjectEditModals({ ui, state, actions }) {
  const { C, aiNotice, aiNoticeIcon, aiNoticeText, btnB, btnG, btnO, btnR, card, inp, tbl, tblC, tblH } = ui;
  const {
    editingAct,
    editingCable,
    editingInspection,
    editingJournal,
    hiddenActs,
    journalFilter,
    showJournalTableModal,
    users,
    weatherLog,
    workJournal,
  } = state;
  const {
    appendPhotos,
    buildCableJournalContent,
    buildHiddenActContent,
    buildMaterialInspectionContent,
    buildWorkJournalContent,
    cableTypeOf,
    fileSrc,
    fmtMeasure,
    getActStatusForJournal,
    setCableJournal,
    setEditingAct,
    setEditingCable,
    setEditingInspection,
    setEditingJournal,
    setHiddenActs,
    setJournalFilter,
    setMaterialInspections,
    setShowJournalTableModal,
    setShowPhotoModal,
    setWorkJournal,
    showPreview,
    uploadPhoto,
  } = actions;

  return (
    <>
      {editingAct && <ProjectHiddenWorksActEditModal act={editingAct} setEditingAct={setEditingAct} setHiddenActs={setHiddenActs} setShowPhotoModal={setShowPhotoModal} uploadPhoto={uploadPhoto} fileSrc={fileSrc} showPreview={showPreview} buildHiddenActContent={buildHiddenActContent} C={C} card={card} inp={inp} btnB={btnB} btnG={btnG} btnO={btnO} btnR={btnR} aiNotice={aiNotice} aiNoticeIcon={aiNoticeIcon} aiNoticeText={aiNoticeText} />}
      {editingJournal && <ProjectWorkJournalEditModal journal={editingJournal} setEditingJournal={setEditingJournal} setWorkJournal={setWorkJournal} weatherLog={weatherLog} users={users} hiddenActs={hiddenActs} setEditingAct={setEditingAct} showPreview={showPreview} buildWorkJournalContent={buildWorkJournalContent} fmtMeasure={fmtMeasure} C={C} card={card} inp={inp} btnB={btnB} btnG={btnG} btnO={btnO} appendPhotos={appendPhotos} fileSrc={fileSrc} setShowPhotoModal={setShowPhotoModal} aiNotice={aiNotice} aiNoticeIcon={aiNoticeIcon} aiNoticeText={aiNoticeText} />}
      {showJournalTableModal && <ProjectWorkJournalTableModal projectName={showJournalTableModal} workJournal={workJournal} journalFilter={journalFilter} setJournalFilter={setJournalFilter} setShowJournalTableModal={setShowJournalTableModal} setEditingJournal={setEditingJournal} getActStatusForJournal={getActStatusForJournal} setEditingAct={setEditingAct} showPreview={showPreview} buildWorkJournalContent={buildWorkJournalContent} fmtMeasure={fmtMeasure} C={C} card={card} inp={inp} tbl={tbl} tblH={tblH} tblC={tblC} btnB={btnB} btnG={btnG} />}
      {editingInspection && <ProjectMaterialInspectionEditModal inspection={editingInspection} setEditingInspection={setEditingInspection} setMaterialInspections={setMaterialInspections} showPreview={showPreview} buildMaterialInspectionContent={buildMaterialInspectionContent} C={C} card={card} inp={inp} btnB={btnB} btnG={btnG} btnO={btnO} aiNotice={aiNotice} aiNoticeIcon={aiNoticeIcon} aiNoticeText={aiNoticeText} />}
      {editingCable && <ProjectCableJournalEditModal cable={editingCable} setEditingCable={setEditingCable} setCableJournal={setCableJournal} users={users} cableTypeOf={cableTypeOf} showPreview={showPreview} buildCableJournalContent={buildCableJournalContent} C={C} card={card} inp={inp} btnB={btnB} btnG={btnG} btnO={btnO} aiNotice={aiNotice} aiNoticeIcon={aiNoticeIcon} aiNoticeText={aiNoticeText} />}
    </>
  );
}
