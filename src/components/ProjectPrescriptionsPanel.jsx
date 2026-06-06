import React from 'react';
import { Check, Plus, X } from 'lucide-react';
import { API } from '../api';

export default function ProjectPrescriptionsPanel({
  projectName,
  prescriptionsList = [],
  showForm,
  setShowForm,
  newPrescription,
  setNewPrescription,
  savePrescription,
  loadAll,
  canClose = false,
  C,
  card,
  inp,
  btnO,
  btnG,
  btnGr,
  badge,
}) {
  const prescriptions = prescriptionsList.filter(item => item.projectName === projectName);
  const formOpen = showForm === 'prescription';

  const markFixed = async (id) => {
    await fetch(API + '/prescriptions/' + id, {
      method: 'PUT',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({status: 'На проверке', fixNotes: 'Устранено'}),
    });
    await loadAll();
  };

  const closePrescription = async (id) => {
    await fetch(API + '/prescriptions/' + id, {
      method: 'PUT',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({status: 'Закрыто'}),
    });
    await loadAll();
  };

  const statusColor = (status) => (
    status === 'Закрыто' ? C.success : status === 'На проверке' ? C.warning : C.danger
  );

  const statusLight = (status) => (
    status === 'Закрыто' ? C.successLight : status === 'На проверке' ? C.warningLight : C.dangerLight
  );

  const statusBorder = (status) => (
    status === 'Закрыто' ? C.successBorder : status === 'На проверке' ? C.warningBorder : C.dangerBorder
  );

  return (
    <div>
      <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px'}}>
        <b style={{color: C.text}}>Предписания</b>
        <button onClick={() => setShowForm(formOpen ? false : 'prescription')} style={btnO}>
          <Plus size={14}/>Выдать
        </button>
      </div>

      {formOpen && (
        <div style={{...card, padding: '16px', marginBottom: '16px', backgroundColor: C.bg}}>
          <input
            placeholder="Номер предписания"
            value={newPrescription.number}
            onChange={event => setNewPrescription({...newPrescription, number: event.target.value})}
            style={inp}
          />
          <textarea
            placeholder="Описание нарушения *"
            value={newPrescription.violation}
            onChange={event => setNewPrescription({...newPrescription, violation: event.target.value})}
            style={{...inp, height: '80px', resize: 'vertical'}}
          />
          <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px'}}>
            <input
              type="date"
              placeholder="Устранить до"
              value={newPrescription.deadline}
              onChange={event => setNewPrescription({...newPrescription, deadline: event.target.value})}
              style={{...inp, marginBottom: 0}}
            />
            <input
              placeholder="Ответственный"
              value={newPrescription.responsible}
              onChange={event => setNewPrescription({...newPrescription, responsible: event.target.value})}
              style={{...inp, marginBottom: 0}}
            />
          </div>
          <div style={{display: 'flex', gap: '8px', marginTop: '10px'}}>
            <button onClick={() => savePrescription(projectName)} style={btnO}>
              <Check size={14}/>Выдать
            </button>
            <button onClick={() => setShowForm(false)} style={btnG}>
              <X size={14}/>Отмена
            </button>
          </div>
        </div>
      )}

      {prescriptions.map(item => (
        <div key={item.id} style={{...card, padding: '14px', marginBottom: '8px', borderLeft: '3px solid ' + statusColor(item.status)}}>
          <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start'}}>
            <div>
              <b style={{fontSize: '13px', color: C.text}}>{'Предписание ' + (item.number ? '№' + item.number : '')}</b>
              <p style={{color: C.textSec, margin: '2px 0', fontSize: '12px'}}>{item.violation}</p>
              <p style={{color: C.textMuted, margin: '0', fontSize: '11px'}}>
                {'Выдал: ' + item.issuedBy + (item.deadline ? ' · До: ' + item.deadline : '') + (item.responsible ? ' · Ответственный: ' + item.responsible : '')}
              </p>
            </div>
            <div style={{display: 'flex', gap: '6px', alignItems: 'center'}}>
              <span style={badge(statusColor(item.status), statusLight(item.status), statusBorder(item.status))}>{item.status}</span>
              {item.status === 'Открыто' && (
                <button onClick={() => markFixed(item.id)} style={{...btnGr, padding: '4px 8px', fontSize: '11px'}}>
                  Устранено
                </button>
              )}
              {item.status === 'На проверке' && canClose && (
                <button onClick={() => closePrescription(item.id)} style={{...btnGr, padding: '4px 8px', fontSize: '11px'}}>
                  Закрыть
                </button>
              )}
            </div>
          </div>
        </div>
      ))}

      {prescriptions.length === 0 && (
        <p style={{color: C.textMuted, textAlign: 'center', padding: '20px'}}>Предписаний нет</p>
      )}
    </div>
  );
}
