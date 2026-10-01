import React from 'react';
import { Check, Eye, Plus, Trash2, Upload, X } from 'lucide-react';
import { API } from '../api';
import DocumentRecognitionPanel from './DocumentRecognitionPanel';
import { createProjectDocumentForm } from '../features/documents/projectDocumentInitialForms';

const DOC_TYPES = ['Договор', 'Акт КС-2', 'Акт КС-3', 'АОСР', 'Доп.соглашение', 'Акт выполненных работ', 'Журнал', 'Счёт', 'Письмо', 'Другое'];
const SIGN_STATUSES = ['Не подписан', 'На подписи', 'Подписан'];
const GROUPS = [
  {key: 'customer', label: '📁 Документы с заказчиком'},
  {key: 'contractor', label: '📁 Документы с мастерами / бригадой'},
];

export default function ProjectDocumentsRegistryPanel({
  projectId,
  projectName,
  projectCustomerName = '',
  projectDocuments = [],
  newProjectDoc,
  setNewProjectDoc,
  showDocForm,
  setShowDocForm,
  uploadingDoc,
  setUploadingDoc,
  uploadPhoto,
  fileSrc,
  loadAll,
  user,
  C,
  card,
  inp,
  btnO,
  btnG,
  btnB,
  btnR,
}) {
  const saveDocument = async () => {
    if (!newProjectDoc.docType) {
      alert('Укажите тип документа');
      return;
    }

    const response = await fetch(API + '/project-documents', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({...newProjectDoc, projectId, projectName, uploadedBy: user.name}),
    });
    let result = {};
    try { result = await response.json(); } catch (_) {}
    if (!response.ok) {
      alert(result.detail || 'Не удалось сохранить документ');
      return;
    }
    setNewProjectDoc(createProjectDocumentForm());
    setShowDocForm(false);
    await loadAll();
  };

  const uploadNewScan = async (file) => {
    if (!file) return;
    setUploadingDoc(true);
    const url = await uploadPhoto(file, {
      projectId,
      projectName,
      context: 'project-documents',
      preferProtectedUrl: true,
    });
    setUploadingDoc(false);
    if (url) {
      setNewProjectDoc(prev => ({
        ...prev,
        scanUrl: url,
      }));
    }
  };

  const uploadExistingScan = async (doc, file) => {
    if (!file) return;
    const url = await uploadPhoto(file, {
      projectId,
      projectName,
      context: 'project-documents',
      preferProtectedUrl: true,
    });
    if (url) {
      await fetch(API + '/project-documents/' + doc.id, {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({scanUrl: url}),
      });
      await loadAll();
    }
  };

  const confirmSigned = async doc => {
    const response = await fetch(API + '/project-documents/' + doc.id, {
      method:'PUT',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({signStatus:'Подписан'}),
    });
    let result={};
    try { result=await response.json(); } catch (_) {}
    if (!response.ok) {
      alert(result.detail || 'Не удалось зафиксировать подписанный договор');
      return;
    }
    await loadAll();
  };

  const deleteDocument = async (docId) => {
    if (!window.confirm('Удалить документ?')) return;
    await fetch(API + '/project-documents/' + docId, {method: 'DELETE'});
    await loadAll();
  };

  const createNextVersion = doc => {
    setNewProjectDoc({
      ...createProjectDocumentForm(),
      side: doc.side,
      docType: doc.docType,
      number: doc.number,
      counterparty: doc.counterparty,
      revisesDocumentId: doc.id,
    });
    setShowDocForm(true);
  };

  const toggleNewDocument = () => {
    const next=!showDocForm;
    if (next) {
      setNewProjectDoc({
        ...createProjectDocumentForm(),
        counterparty:projectCustomerName,
      });
    }
    setShowDocForm(next);
  };

  const cancelNewDocument = () => {
    setNewProjectDoc(createProjectDocumentForm());
    setShowDocForm(false);
  };

  return (
    <div>
      <div style={{...card, padding: '14px', marginBottom: '12px', backgroundColor: C.accentLight, border: '1.5px solid ' + C.accentBorder}}>
        <p style={{margin: 0, color: C.text, fontSize: '12px', lineHeight: 1.5}}>
          📁 Реестр всех документов по объекту: договоры, акты, доп.соглашения, журналы — с загрузкой <b>скана подписанного бумажного документа</b>. Когда объект закроют в архив, документы сохранятся здесь.
        </p>
      </div>

      <div style={{display: 'flex', justifyContent: 'flex-end', marginBottom: '12px'}}>
        <button onClick={toggleNewDocument} style={btnO}>
          <Plus size={14}/>Добавить документ
        </button>
      </div>

      {showDocForm && (
        <div style={{...card, padding: '18px', marginBottom: '14px'}}>
          {newProjectDoc.revisesDocumentId&&<div style={{padding:'10px 12px',borderRadius:'10px',backgroundColor:C.accentLight,border:'1.5px solid '+C.accentBorder,color:C.text,fontSize:'12px',marginBottom:'12px'}}>Создаётся новая версия договора. Предыдущая подписанная версия останется в истории без изменений.</div>}
          <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px'}}>
            <select value={newProjectDoc.side} onChange={e => setNewProjectDoc({...newProjectDoc, side: e.target.value})} style={{...inp, marginBottom: 0}}>
              <option value="customer">📁 С заказчиком</option>
              <option value="contractor">📁 С мастерами/бригадой</option>
            </select>
            <select value={newProjectDoc.docType} onChange={e => setNewProjectDoc({...newProjectDoc, docType: e.target.value})} style={{...inp, marginBottom: 0}}>
              {DOC_TYPES.map(t => <option key={t}>{t}</option>)}
            </select>
            <input placeholder="Номер" value={newProjectDoc.number} onChange={e => setNewProjectDoc({...newProjectDoc, number: e.target.value})} style={{...inp, marginBottom: 0}}/>
            <input type="date" value={newProjectDoc.docDate} onChange={e => setNewProjectDoc({...newProjectDoc, docDate: e.target.value})} style={{...inp, marginBottom: 0}}/>
            <input placeholder="Контрагент (ФИО / организация)" value={newProjectDoc.counterparty} onChange={e => setNewProjectDoc({...newProjectDoc, counterparty: e.target.value})} style={{...inp, marginBottom: 0}}/>
            <select value={newProjectDoc.signStatus} onChange={e => setNewProjectDoc({...newProjectDoc, signStatus: e.target.value})} style={{...inp, marginBottom: 0}}>
              {SIGN_STATUSES.map(t => <option key={t}>{t}</option>)}
            </select>
          </div>
          <input placeholder="Примечание" value={newProjectDoc.notes} onChange={e => setNewProjectDoc({...newProjectDoc, notes: e.target.value})} style={{...inp, marginTop: '10px'}}/>
          <div style={{display: 'flex', alignItems: 'center', gap: '10px', marginTop: '10px', flexWrap: 'wrap'}}>
            <label style={{...btnG, cursor: 'pointer', margin: 0}}>
              <Upload size={14}/>{uploadingDoc ? 'Загрузка...' : (newProjectDoc.scanUrl ? '✅ Скан загружен' : '📎 Загрузить скан')}
              <input type="file" style={{display: 'none'}} onChange={e => uploadNewScan(e.target.files[0])}/>
            </label>
            {newProjectDoc.scanUrl && <a href={fileSrc(newProjectDoc.scanUrl)} target="_blank" rel="noreferrer" style={{fontSize: '12px', color: C.accent}}>посмотреть</a>}
          </div>
          <DocumentRecognitionPanel
            API={API}
            C={C}
            card={card}
            inp={inp}
            btnG={btnG}
            btnO={btnO}
            btnB={btnB}
            uploadPhoto={uploadPhoto}
            fileSrc={fileSrc}
            projectId={projectId}
            projectName={projectName}
            context="project-contract-documents"
            entityType="project_document"
            currentFields={newProjectDoc}
            onApplyProjectDocument={patch => setNewProjectDoc(prev => ({ ...prev, ...patch }))}
          />
          <div style={{display: 'flex', gap: '8px', marginTop: '12px'}}>
            <button onClick={saveDocument} style={btnO}><Check size={14}/>Сохранить</button>
            <button onClick={cancelNewDocument} style={btnG}><X size={14}/>Отмена</button>
          </div>
        </div>
      )}

      {GROUPS.map(group => {
        const docs = projectDocuments.filter(d => d.projectName === projectName && d.side === group.key);

        return (
          <div key={group.key} style={{...card, padding: '16px', marginBottom: '12px'}}>
            <b style={{color: C.text, fontSize: '14px', display: 'block', marginBottom: '10px'}}>
              {group.label} <span style={{color: C.textMuted, fontWeight: '400', fontSize: '12px'}}>({docs.length})</span>
            </b>
            {docs.length === 0 ? (
              <p style={{color: C.textMuted, fontSize: '12px', margin: 0}}>Документов пока нет.</p>
            ) : docs.map(doc => {
              const signed = doc.signStatus === 'Подписан' && doc.scanUrl;

              return (
                <div key={doc.id} style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '8px', padding: '8px 0', borderBottom: '1px solid ' + C.border, flexWrap: 'wrap'}}>
                  <div style={{flex: 1, minWidth: 0}}>
                    <b style={{fontSize: '12px', color: C.text}}>{doc.docType}{doc.number ? ' № ' + doc.number : ''}{doc.contractVersion ? ' · версия ' + doc.contractVersion : ''}</b>
                    <p style={{color: C.textSec, margin: '2px 0', fontSize: '11px'}}>{[doc.docDate, doc.counterparty, doc.notes].filter(Boolean).join(' · ') || '—'}</p>
                    {doc.partySnapshot&&<p style={{color:C.success,margin:'3px 0 0',fontSize:'10px',fontWeight:700}}>Реквизиты сторон зафиксированы</p>}
                  </div>
                  <span style={{
                    padding: '2px 8px',
                    borderRadius: '10px',
                    fontSize: '10px',
                    fontWeight: '600',
                    backgroundColor: signed ? C.successLight : C.warningLight,
                    color: signed ? C.success : C.warning
                  }}>
                    {signed ? '✅ Подписан' : doc.scanUrl ? '📎 Скан есть' : '⏳ ' + doc.signStatus}
                  </span>
                  {doc.scanUrl && (
                    <a href={fileSrc(doc.scanUrl)} target="_blank" rel="noreferrer" style={{...btnB, padding: '4px 8px', fontSize: '11px', textDecoration: 'none'}}>
                      <Eye size={11}/>Скан
                    </a>
                  )}
                  {!doc.scanUrl && !doc.partySnapshot && (
                    <label style={{...btnG, padding: '4px 8px', fontSize: '11px', cursor: 'pointer', margin: 0}}>
                      📎
                      <input type="file" style={{display: 'none'}} onChange={e => uploadExistingScan(doc, e.target.files[0])}/>
                    </label>
                  )}
                  {doc.partySnapshot&&<button type="button" onClick={()=>createNextVersion(doc)} style={{...btnG,padding:'4px 8px',fontSize:'11px'}}>Новая версия</button>}
                  {doc.scanUrl&&!doc.partySnapshot&&doc.signStatus!=='Подписан'&&<button type="button" onClick={()=>confirmSigned(doc)} style={{...btnO,padding:'4px 8px',fontSize:'11px'}}>Подтвердить подпись</button>}
                  {!doc.partySnapshot&&<button onClick={() => deleteDocument(doc.id)} style={{...btnR, padding: '4px 8px'}}><Trash2 size={11}/></button>}
                </div>
              );
            })}
          </div>
        );
      })}
    </div>
  );
}
