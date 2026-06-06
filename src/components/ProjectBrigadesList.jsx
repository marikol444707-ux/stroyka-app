import React from 'react';
import { ChevronRight, Trash2, Users } from 'lucide-react';
import { API } from '../api';

export default function ProjectBrigadesList({
  projectName,
  brigadeContracts = [],
  openBrigadeContract,
  setBrigadeContracts,
  C,
  card,
  btnR,
}) {
  const contracts = brigadeContracts.filter(bc => bc.projectName === projectName);

  const deleteBrigade = async (event, brigadeId) => {
    event.stopPropagation();
    if (!window.confirm('Удалить бригаду?')) return;

    await fetch(API + '/brigade-contracts/' + brigadeId, {method: 'DELETE'});
    setBrigadeContracts(prev => prev.filter(b => b.id !== brigadeId));
  };

  const totalDue = contracts.reduce((sum, bc) => sum + Number(bc.doneAmount || 0), 0);
  const totalPaid = contracts.reduce((sum, bc) => sum + Number(bc.paidAmount || 0), 0);
  const totalOwe = Math.max(0, totalDue - totalPaid);

  if (contracts.length === 0) {
    return (
      <div style={{...card, padding: '40px', textAlign: 'center', color: C.textMuted}}>
        <Users size={48} style={{marginBottom: '15px', opacity: 0.3}}/>
        <p>Бригад пока нет</p>
      </div>
    );
  }

  return (
    <div>
      <div style={{...card, padding: '14px', marginBottom: '12px', backgroundColor: C.bg, display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: '10px'}}>
        <div>
          <p style={{color: C.textSec, fontSize: '11px', margin: '0 0 3px'}}>Всего к оплате бригадам</p>
          <b style={{color: C.accent, fontSize: '15px'}}>{Math.round(totalDue).toLocaleString('ru-RU') + ' ₽'}</b>
        </div>
        <div>
          <p style={{color: C.textSec, fontSize: '11px', margin: '0 0 3px'}}>Оплачено</p>
          <b style={{color: C.success, fontSize: '15px'}}>{Math.round(totalPaid).toLocaleString('ru-RU') + ' ₽'}</b>
        </div>
        <div>
          <p style={{color: C.textSec, fontSize: '11px', margin: '0 0 3px'}}>Остаток</p>
          <b style={{color: totalOwe > 0 ? C.danger : C.success, fontSize: '15px'}}>{Math.round(totalOwe).toLocaleString('ru-RU') + ' ₽'}</b>
        </div>
      </div>

      {contracts.map(bc => {
        const due = Math.round(Number(bc.doneAmount || 0));
        const paid = Math.round(Number(bc.paidAmount || 0));
        const owe = Math.max(0, due - paid);
        const borderColor = due > 0 && owe <= 0 ? C.success : paid > 0 ? C.warning : C.border;

        return (
          <div key={bc.id} style={{...card, padding: '14px', marginBottom: '8px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', cursor: 'pointer', borderLeft: '3px solid ' + borderColor}} onClick={() => openBrigadeContract(bc)}>
            <div style={{flex: 1}}>
              <b style={{color: C.text, fontSize: '13px'}}>{bc.brigadeName}</b>
              <p style={{color: C.textSec, margin: '2px 0', fontSize: '12px'}}>{bc.contractorType + ' · ' + bc.status}</p>
              <div style={{display: 'flex', gap: '10px', flexWrap: 'wrap', marginTop: '2px'}}>
                <span style={{fontSize: '12px', color: C.accent}}>{'К оплате: ' + due.toLocaleString('ru-RU') + ' ₽'}</span>
                <span style={{fontSize: '12px', color: C.success}}>{'Оплачено: ' + paid.toLocaleString('ru-RU') + ' ₽'}</span>
                {owe > 0 && <span style={{fontSize: '12px', color: C.danger, fontWeight: '700'}}>{'Остаток: ' + owe.toLocaleString('ru-RU') + ' ₽'}</span>}
                {due > 0 && owe <= 0 && <span style={{fontSize: '12px', color: C.success, fontWeight: '700'}}>✓ Оплачено полностью</span>}
              </div>
            </div>
            <div style={{display: 'flex', gap: '8px', alignItems: 'center'}}>
              <ChevronRight size={16} color={C.textMuted}/>
              <button onClick={event => deleteBrigade(event, bc.id)} style={{...btnR, padding: '4px 8px'}}>
                <Trash2 size={11}/>
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
}
