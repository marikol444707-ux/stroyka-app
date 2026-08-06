import React from 'react';
import { getDistributableWorkRows } from '../features/estimates/estimateDistributionPayload';

export default function EstimateDistributeItemsTable({
  C,
  inp,
  selectedEstimate,
  distributeAssignments,
  setDistributeAssignments,
  distributeBrigades,
}) {
  const sections = [];
  getDistributableWorkRows(selectedEstimate).forEach(row => {
    let section = sections.find(candidate => candidate.sectionIndex === row.sectionIndex);
    if (!section) {
      section = {sectionIndex: row.sectionIndex, name: row.section, items: []};
      sections.push(section);
    }
    section.items.push(row);
  });

  return (
    <div style={{maxHeight:'380px',overflowY:'auto',marginBottom:'10px'}}>
      {sections.length === 0 && <div style={{padding:'12px',color:C.textSec,fontSize:'12px'}}>В смете нет рабочих позиций для распределения.</div>}
      {sections.map((s)=>(
        <div key={s.sectionIndex} style={{marginBottom:'10px'}}>
          <div style={{padding:'4px 8px',backgroundColor:C.accentLight,borderRadius:'4px',marginBottom:'4px'}}><b style={{fontSize:'11px',color:C.accent}}>{s.name}</b></div>
          {s.items.map((item)=>(
            <div key={item.key} style={{display:'grid',gridTemplateColumns:'1fr 70px 80px 1fr',gap:'6px',padding:'4px 8px',alignItems:'center',fontSize:'11px',borderBottom:'1px solid '+C.border}}>
              <span style={{color:C.text}}>{item.name}</span>
              <span style={{color:C.textSec}}>{item.quantity} {item.unit}</span>
              <span style={{color:C.textMuted}}>{Number(item.priceSmeta||0).toLocaleString('ru-RU')}₽</span>
              <select value={distributeAssignments[item.key]||''} onChange={e=>setDistributeAssignments(prev=>({...prev,[item.key]:e.target.value}))} style={{...inp,marginBottom:0,fontSize:'11px',padding:'3px 6px'}}>
                <option value=''>— не назначено —</option>
                {distributeBrigades.map((b,bi)=><option key={bi} value={b.name}>{b.name}</option>)}
              </select>
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
