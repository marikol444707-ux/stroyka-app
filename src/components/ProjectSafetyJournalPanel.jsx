import React from 'react';
import { Bot, Check, Eye, Plus, Search, X } from 'lucide-react';
import { API } from '../api';

const EMPTY_TB_ENTRY = {
  project: '',
  type: 'Вводный инструктаж',
  participants: [],
  date: '',
  program: '',
  instructionText: '',
  aiLoading: false,
};

export default function ProjectSafetyJournalPanel({
  projectName,
  tbJournal = [],
  showForm,
  setShowForm,
  newTbEntry,
  setNewTbEntry,
  newParticipant,
  setNewParticipant,
  listSearch,
  setListSearch,
  tbTypes = [],
  tbInstructions = {},
  saveTbEntry,
  matchSearch,
  showPreview,
  buildTBContent,
  C,
  card,
  inp,
  btnO,
  btnG,
  btnB,
  btnR,
}) {
  const formOpen = showForm === 'tb';
  const projectEntries = tbJournal.filter(entry => entry.project === projectName);
  const visibleEntries = projectEntries.filter(entry => (
    matchSearch(listSearch, entry.type, entry.instructionText, entry.masterName, entry.instructor)
  ));

  const selectedTypeMeta = tbTypes.find(item => item.value === newTbEntry.type);
  const extraInstructionTypes = Object.keys(tbInstructions).filter(key => !tbTypes.find(item => item.value === key));

  const generateInstruction = async () => {
    setNewTbEntry(prev => ({...prev, aiLoading: true}));
    try {
      const res = await fetch(API + '/tb-journal/ai-generate', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({instructionType: newTbEntry.type, projectName, workContext: ''}),
      });
      if (!res.ok) {
        const error = await res.json().catch(() => ({}));
        throw new Error(error.detail || 'Ошибка');
      }
      const data = await res.json();
      setNewTbEntry(prev => ({...prev, instructionText: data.instructionText || '', aiLoading: false}));
    } catch (error) {
      alert('AI: ' + error.message);
      setNewTbEntry(prev => ({...prev, aiLoading: false}));
    }
  };

  const addParticipant = (allowEmpty = false) => {
    if (!newParticipant && !allowEmpty) return;
    setNewTbEntry({
      ...newTbEntry,
      participants: [...(newTbEntry.participants || []), newParticipant],
    });
    setNewParticipant('');
  };

  const saveEntry = async () => {
    await saveTbEntry({...newTbEntry, project: projectName});
    setShowForm(false);
    setNewTbEntry(EMPTY_TB_ENTRY);
  };

  return (
    <div>
      <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px'}}>
        <b style={{color: C.text}}>Журнал ТБ</b>
        <button onClick={() => setShowForm(formOpen ? false : 'tb')} style={btnO}>
          <Plus size={14}/>Добавить
        </button>
      </div>

      {formOpen && (
        <div style={{...card, padding: '16px', marginBottom: '16px', backgroundColor: C.bg}}>
          <select
            value={newTbEntry.type}
            onChange={event => setNewTbEntry({...newTbEntry, type: event.target.value})}
            style={inp}
          >
            {tbTypes.map(item => <option key={item.value} value={item.value}>{item.value}</option>)}
            {extraInstructionTypes.map(type => <option key={type}>{type}</option>)}
          </select>

          {selectedTypeMeta && (
            <p style={{fontSize: '10px', color: C.textMuted, margin: '0 0 8px', padding: '4px 8px', backgroundColor: C.bg, borderRadius: '4px'}}>
              📋 Периодичность: <b>{selectedTypeMeta.freq}</b> · {selectedTypeMeta.legal}
            </p>
          )}

          <input
            type="date"
            value={newTbEntry.date}
            onChange={event => setNewTbEntry({...newTbEntry, date: event.target.value})}
            style={inp}
          />
          <textarea
            placeholder="Программа инструктажа (3-5 пунктов)"
            value={newTbEntry.program || ''}
            onChange={event => setNewTbEntry({...newTbEntry, program: event.target.value})}
            style={{...inp, minHeight: '50px', resize: 'vertical'}}
          />

          <div style={{display: 'flex', gap: '8px', alignItems: 'center', marginBottom: '6px'}}>
            <textarea
              placeholder="Текст инструктажа (можно сгенерировать ИИ →)"
              value={newTbEntry.instructionText || ''}
              onChange={event => setNewTbEntry({...newTbEntry, instructionText: event.target.value})}
              style={{...inp, minHeight: '80px', flex: 1, marginBottom: 0, resize: 'vertical'}}
            />
            <button
              disabled={newTbEntry.aiLoading}
              onClick={generateInstruction}
              style={{
                ...btnB,
                backgroundColor: '#10b981',
                color: 'white',
                borderColor: '#059669',
                padding: '10px 12px',
                fontSize: '11px',
                opacity: newTbEntry.aiLoading ? 0.6 : 1,
              }}
              title="Сгенерировать текст по ГОСТ через ИИ"
            >
              <Bot size={14}/>{newTbEntry.aiLoading ? '…' : '🤖 ИИ'}
            </button>
          </div>

          <div style={{display: 'flex', gap: '8px', marginBottom: '10px'}}>
            <input
              placeholder="ФИО участника"
              value={newParticipant}
              onChange={event => setNewParticipant(event.target.value)}
              onKeyDown={event => {
                if (event.key === 'Enter') addParticipant(true);
              }}
              style={{...inp, marginBottom: 0, flex: 1}}
            />
            <button onClick={() => addParticipant(false)} style={btnO}>
              <Plus size={14}/>
            </button>
          </div>

          {(newTbEntry.participants || []).map((participant, index) => (
            <div key={index} style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '6px 10px', backgroundColor: C.bg, borderRadius: '6px', marginBottom: '4px', border: '1px solid ' + C.border}}>
              <span style={{fontSize: '12px'}}>{participant}</span>
              <button
                onClick={() => setNewTbEntry({...newTbEntry, participants: (newTbEntry.participants || []).filter((_, idx) => idx !== index)})}
                style={{...btnR, padding: '2px 6px'}}
              >
                <X size={10}/>
              </button>
            </div>
          ))}

          <div style={{display: 'flex', gap: '8px', marginTop: '10px'}}>
            <button onClick={saveEntry} style={btnO}>
              <Check size={14}/>Сохранить
            </button>
            <button onClick={() => setShowForm(false)} style={btnG}>
              <X size={14}/>Отмена
            </button>
          </div>
        </div>
      )}

      <div style={{position: 'relative', marginBottom: '10px'}}>
        <Search size={13} style={{position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: C.textMuted}}/>
        <input
          placeholder="🔍 Поиск инструктажа"
          value={listSearch}
          onChange={event => setListSearch(event.target.value)}
          style={{...inp, marginBottom: 0, paddingLeft: '30px', fontSize: '12px', padding: '6px 8px 6px 30px'}}
        />
      </div>

      {visibleEntries.map(entry => (
        <div key={entry.id} style={{...card, padding: '14px', marginBottom: '8px'}}>
          <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
            <div>
              <b style={{color: C.text, fontSize: '13px'}}>{entry.type}</b>
              <p style={{color: C.textSec, margin: '2px 0', fontSize: '12px'}}>
                {entry.date + ' · ' + (entry.participants || []).length + ' участников'}
              </p>
            </div>
            <button onClick={() => showPreview(buildTBContent(entry), 'Журнал ТБ')} style={btnB}>
              <Eye size={14}/>ЖТБ
            </button>
          </div>
        </div>
      ))}

      {projectEntries.length === 0 && (
        <p style={{color: C.textMuted, textAlign: 'center', padding: '20px'}}>Записей нет</p>
      )}
    </div>
  );
}
