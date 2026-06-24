import React from 'react';
import CrmHeader from './CrmHeader';
import CrmLeadForm from './CrmLeadForm';
import CrmStageBoard from './CrmStageBoard';

export default function CrmPage({
  C,
  CRM_STAGES,
  btnG,
  btnO,
  btnR,
  card,
  createProjectFromLead,
  deleteLead,
  editingItem,
  inp,
  leads,
  newLead,
  saveLead,
  setEditingItem,
  setNewLead,
  setShowForm,
  showForm,
  isMobile = false,
  appendPhotos,
  fileSrc,
  setShowPhotoModal,
}) {
  const emptyLead = {name:'',phone:'',email:'',source:'',budget:'',notes:'',stage:'Новый',photoUrl:''};

  return (
    <div style={{width:'100%',maxWidth:'100%',minWidth:0,overflowX:'hidden'}}>
      <CrmHeader
        C={C}
        btnO={btnO}
        isMobile={isMobile}
        onNewLead={() => {
          setShowForm(!showForm);
          setEditingItem(null);
          setNewLead(emptyLead);
        }}
      />
      {showForm && (
        <CrmLeadForm
          C={C}
          card={card}
          inp={inp}
          btnO={btnO}
          btnG={btnG}
          isMobile={isMobile}
          newLead={newLead}
          setNewLead={setNewLead}
          crmStages={CRM_STAGES}
          editingItem={editingItem}
          onSave={() => {
            saveLead(editingItem ? {...newLead, id: editingItem.id} : newLead);
            setShowForm(false);
            setEditingItem(null);
          }}
          onCancel={() => {
            setShowForm(false);
            setEditingItem(null);
          }}
          appendPhotos={appendPhotos}
          fileSrc={fileSrc}
          setShowPhotoModal={setShowPhotoModal}
        />
      )}
      <CrmStageBoard
        C={C}
        card={card}
        btnG={btnG}
        btnR={btnR}
        crmStages={CRM_STAGES}
        leads={leads}
        saveLead={saveLead}
        deleteLead={deleteLead}
        createProjectFromLead={createProjectFromLead}
        setEditingItem={setEditingItem}
        setNewLead={setNewLead}
        setShowForm={setShowForm}
        isMobile={isMobile}
        fileSrc={fileSrc}
        setShowPhotoModal={setShowPhotoModal}
      />
    </div>
  );
}
