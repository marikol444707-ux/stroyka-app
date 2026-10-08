import {brigadeBalance, balanceMoney} from './brigadeBalance';
import React, { useState } from 'react';
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
  const [showHistory, setShowHistory] = useState(false);
  const [deleteError, setDeleteError] = useState('');
  const projectContracts = brigadeContracts.filter(bc => bc.projectName === projectName);
  const historical = projectContracts.filter(bc => ['Черновик', 'Аннулирован'].includes(bc.status));
  const contracts = projectContracts.filter(bc => showHistory ? historical.includes(bc) : !historical.includes(bc));

  const deleteBrigade = async (event, brigadeId) => {
    event.stopPropagation();
    if (!window.confirm('Аннулировать черновик договора?')) return;
    setDeleteError('');
    try {
      const response = await fetch(API + '/brigade-contracts/' + brigadeId, {method: 'DELETE'});
      const data = await response.json().catch(() => ({}));
      if (!response.ok || !data.ok) throw new Error(data.detail || 'Не удалось аннулировать договор');
      setBrigadeContracts(prev => prev.map(b => b.id === brigadeId ? {...b, status: 'Аннулирован'} : b));
    } catch (error) {
      setDeleteError(error.message || 'Не удалось аннулировать договор');
    }
  };

  const activeContracts = projectContracts.filter(bc => bc.status !== 'Аннулирован');
  const balances = activeContracts.map(brigadeBalance);
  const totalsKnown = balances.every(balance => balance.known);
  const totalDue = totalsKnown ? balances.reduce((sum, balance) => sum + balance.due, 0) : null;
  const totalPaid = totalsKnown ? balances.reduce((sum, balance) => sum + balance.paid, 0) : null;
  const totalOwe = totalsKnown ? balances.reduce((sum, balance) => sum + balance.remaining, 0) : null;

  if (projectContracts.length === 0) {
    return (
      <div style={{...card, padding: '40px', textAlign: 'center', color: C.textMuted}}>
        <Users size={48} style={{marginBottom: '15px', opacity: 0.3}}/>
        <p>Бригад пока нет</p>
      </div>
    );
  }

  return (
    <div>
      <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',gap:'12px',flexWrap:'wrap',marginBottom:'12px'}}>
        <div><b style={{color:C.text,fontSize:'16px'}}>Исполнители</b><p style={{color:C.textSec,fontSize:'12px',margin:'3px 0 0'}}>Действующие договоры и расчёты по объекту</p></div>
        {(showHistory || historical.length > 0) && <button type="button" aria-pressed={showHistory} onClick={() => setShowHistory(value => !value)} style={{background:'transparent',border:'1px solid '+C.border,borderRadius:'8px',padding:'8px 12px',color:C.text,cursor:'pointer'}}>{showHistory ? 'Скрыть историю' : `История и черновики · ${historical.length}`}</button>}
      </div>
      {deleteError && <p role="alert" style={{color:C.danger,fontSize:'13px'}}>{deleteError}</p>}
      <div style={{...card, padding: '14px', marginBottom: '12px', backgroundColor: C.bg, display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: '10px'}}>
        <div>
          <p style={{color: C.textSec, fontSize: '11px', margin: '0 0 3px'}}>Всего к оплате бригадам</p>
          <b style={{color: C.accent, fontSize: '15px'}}>{balanceMoney(totalDue)}</b>
        </div>
        <div>
          <p style={{color: C.textSec, fontSize: '11px', margin: '0 0 3px'}}>Оплачено</p>
          <b style={{color: C.success, fontSize: '15px'}}>{balanceMoney(totalPaid)}</b>
        </div>
        <div>
          <p style={{color: C.textSec, fontSize: '11px', margin: '0 0 3px'}}>Остаток</p>
          <b style={{color: totalOwe > 0 ? C.danger : C.success, fontSize: '15px'}}>{balanceMoney(totalOwe)}</b>
        </div>
      </div>

      {contracts.length === 0 && <p style={{color:C.textSec}}>{showHistory ? 'В истории пока нет договоров.' : 'Действующих договоров нет. Черновики и аннулированные записи находятся в истории.'}</p>}
      <div style={{...card,padding:'0 16px',overflow:'hidden'}}>
      {contracts.map(bc => {
        const {due, paid, remaining: owe, known} = brigadeBalance(bc);

        return (
          <div key={bc.id} style={{padding:'16px 4px',borderBottom:'1px solid '+C.border,display:'flex',justifyContent:'space-between',alignItems:'center',gap:'12px',cursor:'pointer'}} onClick={() => openBrigadeContract(bc)}>
            <div style={{flex: 1}}>
              <b style={{color: C.text, fontSize: '13px'}}>{bc.brigadeName}</b>
              <p style={{color: C.textSec, margin: '3px 0', fontSize: '12px'}}>{bc.contractorType + ' · ' + bc.status}{bc.workPackage ? ' · ' + bc.workPackage : ''}</p>
              <div style={{display: 'flex', gap: '10px', flexWrap: 'wrap', marginTop: '2px'}}>
                <span style={{fontSize: '12px', color: C.accent}}>{(Number(bc.settlementVersion) === 2 ? 'По актам: ' : 'К оплате: ') + balanceMoney(due)}</span>
                <span style={{fontSize: '12px', color: C.success}}>{'Оплачено: ' + balanceMoney(paid)}</span>
                {owe > 0 && <span style={{fontSize: '12px', color: C.danger, fontWeight: '700'}}>{'Остаток: ' + balanceMoney(owe)}</span>}
                {known && due > 0 && owe <= 0 && <span style={{fontSize: '12px', color: C.success, fontWeight: '700'}}>✓ Оплачено полностью</span>}
              </div>
            </div>
            <div style={{display: 'flex', gap: '8px', alignItems: 'center'}}>
              <ChevronRight size={16} color={C.textMuted}/>
              {bc.status === 'Черновик' && <button type="button" aria-label={'Аннулировать черновик ' + bc.brigadeName} title="Аннулировать черновик" onClick={event => deleteBrigade(event, bc.id)} style={{...btnR, padding: '4px 8px'}}><Trash2 size={13}/></button>}
            </div>
          </div>
        );
      })}
      </div>
    </div>
  );
}
