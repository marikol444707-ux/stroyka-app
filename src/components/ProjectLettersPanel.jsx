import React from 'react';
import { Check, Eye, Plus, Trash2, Upload, X } from 'lucide-react';
import { API } from '../api';
import { createProjectLetterForm } from '../features/documents/projectDocumentInitialForms';

export default function ProjectLettersPanel({
  projectId,
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
  const uploadLetterFile = async (file) => {
    if (!file) return;
    setUploadingLetter(true);
    const url = await uploadPhoto(file, {
      projectId,
      projectName,
      context: 'project-letters',
      preferProtectedUrl: true,
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

    await fetch(API + '/project-letters', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({...newLetter, projectName, author: user.name}),
    });
    setNewLetter(createProjectLetterForm());
    setShowLetterForm(false);
    await loadAll();
  };

  const deleteLetter = async (letterId) => {
    if (!window.confirm('Удалить письмо?')) return;
    await fetch(API + '/project-letters/' + letterId, {method: 'DELETE'});
    await loadAll();
  };

  const letters = (projectLetters || []).filter(l => l.projectName === projectName);

  return (
    <div>
      <div style={{...card, padding: '14px', marginBottom: '12px', backgroundColor: C.accentLight, border: '1.5px solid ' + C.accentBorder}}>
        <p style={{margin: 0, color: C.text, fontSize: '12px', lineHeight: 1.5}}>
          ✉️ Переписка по объекту: письма, уведомления, претензии между компанией и заказчиком / подрядчиками. Привязана к объекту и сохранится в архиве.
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
            <select value={newLetter.side} onChange={e => setNewLetter({...newLetter, side: e.target.value})} style={{...inp, marginBottom: 0}}>
              <option value="customer">С заказчиком</option>
              <option value="contractor">С подрядчиками</option>
            </select>
            <select value={newLetter.direction} onChange={e => setNewLetter({...newLetter, direction: e.target.value})} style={{...inp, marginBottom: 0}}>
              <option value="outgoing">📤 Исходящее</option>
              <option value="incoming">📥 Входящее</option>
            </select>
            <input placeholder="Тема письма *" value={newLetter.subject} onChange={e => setNewLetter({...newLetter, subject: e.target.value})} style={{...inp, marginBottom: 0}}/>
            <input type="date" value={newLetter.letterDate} onChange={e => setNewLetter({...newLetter, letterDate: e.target.value})} style={{...inp, marginBottom: 0}}/>
            <input placeholder="Контрагент (ФИО / организация)" value={newLetter.counterparty} onChange={e => setNewLetter({...newLetter, counterparty: e.target.value})} style={{...inp, marginBottom: 0}}/>
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
            <button onClick={saveLetter} style={btnO}><Check size={14}/>Сохранить</button>
            <button onClick={() => setShowLetterForm(false)} style={btnG}><X size={14}/>Отмена</button>
          </div>
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
                {letter.body && <p style={{color: C.text, margin: '4px 0 0', fontSize: '12px', whiteSpace: 'pre-wrap'}}>{letter.body}</p>}
              </div>
              <div style={{display: 'flex', gap: '6px', alignItems: 'center'}}>
                {letter.fileUrl && (
                  <a href={fileSrc(letter.fileUrl)} target="_blank" rel="noreferrer" style={{...btnB, padding: '4px 8px', fontSize: '11px', textDecoration: 'none'}}>
                    <Eye size={11}/>Файл
                  </a>
                )}
                <button onClick={() => deleteLetter(letter.id)} style={{...btnR, padding: '4px 8px'}}>
                  <Trash2 size={11}/>
                </button>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
