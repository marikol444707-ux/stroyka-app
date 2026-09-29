import React, {useRef, useState} from 'react';
import { Check, Eye, Plus, Trash2, Upload, X } from 'lucide-react';
import { API } from '../api';
import { createProjectLetterForm } from '../features/documents/projectDocumentInitialForms';

export default function ProjectLettersPanel({
  projectId,
  projectCompanyId,
  projectName,
  projectLetters = [],
  newLetter,
  setNewLetter,
  showLetterForm,
  setShowLetterForm,
  uploadingLetter,
  setUploadingLetter,
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
  const [correctionLetterId,setCorrectionLetterId]=useState(null);
  const [correctionReason,setCorrectionReason]=useState('');
  const [correctionError,setCorrectionError]=useState('');
  const [savingLetter,setSavingLetter]=useState(false);
  const [letterError,setLetterError]=useState('');
  const publicationRequestId=useRef('');
  const freshRequestId=()=>window.crypto?.randomUUID?.() ||
    'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g,c=>{
      const value=Math.floor(Math.random()*16);return (c==='x'?value:(value&3)|8).toString(16);
    });
  const uploadLetterFile = async (file) => {
    if (!file) return;
    setUploadingLetter(true);
    const url = await uploadPhoto(file, {
      projectId,
      projectName,
      context: 'project-letters',
      preferProtectedUrl: true,
      companyId: projectCompanyId,
    });
    setUploadingLetter(false);
    if (url) {
      setNewLetter(prev => ({...prev, fileUrl: url}));
    }
  };

  const saveLetter = async () => {
    if (!newLetter.subject.trim()) {
      alert('Укажите тему письма');
      return;
    }

    setLetterError('');setSavingLetter(true);
    try {
      const customerPublication=newLetter.side==='customer' && newLetter.direction==='outgoing';
      let path='/project-letters';
      let payload={...newLetter,projectId,projectName,author:user.name};
      if(customerPublication){
        const fileMatch=newLetter.fileUrl ? /^\/tenant-files\/([1-9]\d*)\/content$/.exec(newLetter.fileUrl) : null;
        if(newLetter.fileUrl && !fileMatch)throw new Error('Вложение нужно загрузить заново в этот объект');
        publicationRequestId.current ||= freshRequestId();
        path='/project-letters/customer-publications';
        payload={requestId:publicationRequestId.current,projectId,subject:newLetter.subject.trim(),
          body:(newLetter.body || '').trim(),letterDate:newLetter.letterDate || null,
          ...(fileMatch?{fileId:Number(fileMatch[1])}:{})};
      }
      const response=await fetch(API+path,{method:'POST',credentials:'include',
        headers:{'Content-Type':'application/json',...(projectCompanyId?{
          'X-Company-Id':String(projectCompanyId),'X-Company-Mode':'company'}:{})},body:JSON.stringify(payload)});
      const data=await response.json().catch(()=>({}));
      if(!response.ok)throw new Error(data.detail || 'Письмо не отправлено');
      publicationRequestId.current='';
      setNewLetter(createProjectLetterForm());setShowLetterForm(false);await loadAll();
    } catch(error){setLetterError(error.message || 'Письмо не отправлено');}
    finally {setSavingLetter(false);}
  };

  const deleteLetter = async (letterId) => {
    if (!window.confirm('Удалить письмо?')) return;
    await fetch(API + '/project-letters/' + letterId, {method: 'DELETE'});
    await loadAll();
  };

  const requestCorrection = async letterId => {
    if(correctionReason.trim().length<3)return;
    setCorrectionError('');
    try {
      const response=await fetch(API+`/project-letters/${letterId}/request-correction`,{
        method:'POST',credentials:'include',headers:{'Content-Type':'application/json',
          ...(projectCompanyId?{'X-Company-Id':String(projectCompanyId),'X-Company-Mode':'company'}:{})},
        body:JSON.stringify({reason:correctionReason.trim()}),
      });
      const data=await response.json();
      if(!response.ok)throw new Error(data.detail || 'Запрос не отправлен');
      setCorrectionLetterId(null);setCorrectionReason('');await loadAll();
    } catch(error) { setCorrectionError(error.message || 'Запрос не отправлен'); }
  };

  const letters = (projectLetters || []).filter(l => l.projectId
    ? Number(l.projectId) === Number(projectId) : l.projectName === projectName);

  return (
    <div>
      <div style={{...card, padding: '14px', marginBottom: '12px', backgroundColor: C.accentLight, border: '1.5px solid ' + C.accentBorder}}>
        <p style={{margin: 0, color: C.text, fontSize: '12px', lineHeight: 1.5}}>
          Здесь хранятся файлы и письма по объекту. Отправленный заказчику файл сразу появится в его кабинете и останется в истории.
        </p>
      </div>

      <div style={{display: 'flex', justifyContent: 'flex-end', marginBottom: '12px'}}>
        <button onClick={() => setShowLetterForm(!showLetterForm)} style={btnO}>
          <Plus size={14}/>Добавить письмо
        </button>
      </div>

      {showLetterForm && (
        <div style={{...card, padding: '18px', marginBottom: '14px'}}>
          <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px'}}>
            <select value={newLetter.side} onChange={e => setNewLetter({...newLetter, side: e.target.value,
              ...(e.target.value==='customer'?{direction:'outgoing'}:{})})} style={{...inp, marginBottom: 0}}>
              <option value="customer">С заказчиком</option>
              <option value="contractor">С подрядчиками</option>
            </select>
            {newLetter.side==='customer' ? <div style={{...inp,marginBottom:0,display:'flex',alignItems:'center'}}>Получатель: заказчик этого объекта</div> :
            <select value={newLetter.direction} onChange={e => setNewLetter({...newLetter, direction: e.target.value})} style={{...inp, marginBottom: 0}}>
              <option value="outgoing">📤 Исходящее</option>
              <option value="incoming">📥 Входящее</option>
            </select>}
            <input placeholder="Тема письма *" value={newLetter.subject} onChange={e => setNewLetter({...newLetter, subject: e.target.value})} style={{...inp, marginBottom: 0}}/>
            <input type="date" value={newLetter.letterDate} onChange={e => setNewLetter({...newLetter, letterDate: e.target.value})} style={{...inp, marginBottom: 0}}/>
            {newLetter.side!=='customer' && <input placeholder="Контрагент (ФИО / организация)" value={newLetter.counterparty} onChange={e => setNewLetter({...newLetter, counterparty: e.target.value})} style={{...inp, marginBottom: 0}}/>}
          </div>
          <textarea placeholder="Текст письма" value={newLetter.body} onChange={e => setNewLetter({...newLetter, body: e.target.value})} style={{...inp, marginTop: '10px', height: '90px'}}/>
          <div style={{display: 'flex', alignItems: 'center', gap: '10px', marginTop: '4px', flexWrap: 'wrap'}}>
            <label style={{...btnG, cursor: 'pointer', margin: 0}}>
              <Upload size={14}/>{uploadingLetter ? 'Загрузка...' : (newLetter.fileUrl ? '✅ Файл прикреплён' : '📎 Прикрепить скан/файл')}
              <input type="file" style={{display: 'none'}} onChange={e => uploadLetterFile(e.target.files[0])}/>
            </label>
            {newLetter.fileUrl && <a href={fileSrc(newLetter.fileUrl)} target="_blank" rel="noreferrer" style={{fontSize: '12px', color: C.accent}}>посмотреть</a>}
          </div>
          <div style={{display: 'flex', gap: '8px', marginTop: '12px'}}>
            <button onClick={saveLetter} disabled={savingLetter} style={btnO}><Check size={14}/>{savingLetter?'Отправка…':newLetter.side==='customer'&&newLetter.direction==='outgoing'?'Отправить заказчику':'Сохранить'}</button>
            <button onClick={() => setShowLetterForm(false)} style={btnG}><X size={14}/>Отмена</button>
          </div>
          {letterError && <p role="alert" style={{color:C.danger || '#b91c1c'}}>{letterError}</p>}
        </div>
      )}

      {letters.length === 0 ? (
        <p style={{color: C.textMuted, fontSize: '12px', textAlign: 'center', padding: '20px'}}>
          Писем пока нет. Добавьте первое письмо по объекту.
        </p>
      ) : letters.map(letter => {
        const outgoing = letter.direction === 'outgoing';

        return (
          <div key={letter.id} style={{...card, padding: '12px 14px', marginBottom: '8px', borderLeft: '3px solid ' + (outgoing ? C.accent : C.warning)}}>
            <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '8px', flexWrap: 'wrap'}}>
              <div style={{flex: 1, minWidth: 0}}>
                <b style={{fontSize: '13px', color: C.text}}>{outgoing ? '📤 ' : '📥 '}{letter.subject}</b>
                <p style={{color: C.textSec, margin: '2px 0', fontSize: '11px'}}>
                  {[outgoing ? 'Исходящее' : 'Входящее', letter.side === 'customer' ? 'заказчик' : 'подрядчик', letter.counterparty, letter.letterDate, letter.author].filter(Boolean).join(' · ')}
                </p>
                {outgoing && letter.side==='customer' && letter.deliveryStatus==='sent' &&
                  <p style={{color:C.success,margin:'5px 0',fontSize:12,fontWeight:700}}>Отправлено заказчику{letter.publishedByName?` · ${letter.publishedByName}`:''}</p>}
                {letter.body && <p style={{color: C.text, margin: '4px 0 0', fontSize: '12px', whiteSpace: 'pre-wrap'}}>{letter.body}</p>}
                {letter.replacesLetterId && <p style={{color:C.textSec,margin:'6px 0 0',fontSize:12,fontWeight:700}}>Исправленная версия</p>}
                {letter.correctionReason && <div style={{marginTop:8,padding:10,border:`1px solid ${C.warning}`,borderRadius:8}}>
                  <b style={{fontSize:12}}>Запрошено исправление</b>
                  <p style={{margin:'4px 0 0',fontSize:12}}>{letter.correctionReason}</p>
                  {letter.correctedByLetterId && <p style={{margin:'4px 0 0',fontSize:12}}>Новая версия получена</p>}
                </div>}
                {correctionLetterId===letter.id && <div style={{marginTop:8}}>
                  <label style={{display:'block',fontSize:12}}>Что нужно исправить
                    <textarea value={correctionReason} maxLength={2000} onChange={event=>setCorrectionReason(event.target.value)}
                      style={{...inp,display:'block',width:'100%',boxSizing:'border-box',marginTop:6,minHeight:70}}/>
                  </label>
                  <div style={{display:'flex',gap:8,flexWrap:'wrap'}}>
                    <button type="button" style={btnO} disabled={correctionReason.trim().length<3}
                      onClick={()=>requestCorrection(letter.id)}>Отправить заказчику</button>
                    <button type="button" style={btnG} onClick={()=>{setCorrectionLetterId(null);setCorrectionReason('');setCorrectionError('');}}>Отмена</button>
                  </div>
                  {correctionError && <p role="alert" style={{color:C.danger}}>{correctionError}</p>}
                </div>}
              </div>
              <div style={{display: 'flex', gap: '6px', alignItems: 'center'}}>
                {letter.fileUrl && (
                  <a href={fileSrc(letter.fileUrl)} target="_blank" rel="noreferrer" style={{...btnB, padding: '4px 8px', fontSize: '11px', textDecoration: 'none'}}>
                    <Eye size={11}/>Файл
                  </a>
                )}
                {!outgoing && letter.side==='customer' && letter.fileUrl && !letter.correctionRequestedAt &&
                  <button type="button" onClick={()=>{setCorrectionLetterId(letter.id);setCorrectionReason('');setCorrectionError('');}}
                    style={{...btnG,padding:'4px 8px',fontSize:11}}>Запросить исправление</button>}
                {!letter.correctionRequestedAt && !letter.replacesLetterId && !letter.publishedAt &&
                  <button aria-label="Удалить письмо" onClick={() => deleteLetter(letter.id)} style={{...btnR, padding: '4px 8px'}}>
                    <Trash2 size={11}/>
                  </button>}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
