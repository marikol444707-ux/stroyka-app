import React from 'react';

export default function EstimateDistributeItemsTable({
  C,
  inp,
  selectedEstimate,
  distributeAssignments,
  setDistributeAssignments,
  distributeBrigades,
}) {
  return (
    <div style={{maxHeight:'380px',overflowY:'auto',marginBottom:'10px'}}>
      {(selectedEstimate.sections||[]).map((s,si)=>(
        <div key={si} style={{marginBottom:'10px'}}>
          <div style={{padding:'4px 8px',backgroundColor:C.accentLight,borderRadius:'4px',marginBottom:'4px'}}><b style={{fontSize:'11px',color:C.accent}}>{s.name}</b></div>
          {(s.items||[]).map((it,ii)=>{const key=si+'-'+ii;return(
            <div key={ii} style={{display:'grid',gridTemplateColumns:'1fr 70px 80px 1fr',gap:'6px',padding:'4px 8px',alignItems:'center',fontSize:'11px',borderBottom:'1px solid '+C.border}}>
              <span style={{color:C.text}}>{it.name}</span>
              <span style={{color:C.textSec}}>{it.quantity} {it.unit}</span>
              <span style={{color:C.textMuted}}>{Number(it.priceWork||0).toLocaleString('ru-RU')}₽</span>
              <select value={distributeAssignments[key]||''} onChange={e=>setDistributeAssignments(prev=>({...prev,[key]:e.target.value}))} style={{...inp,marginBottom:0,fontSize:'11px',padding:'3px 6px'}}>
                <option value=''>— не назначено —</option>
                {distributeBrigades.map((b,bi)=><option key={bi} value={b.name}>{b.name}</option>)}
              </select>
            </div>
          );})}
        </div>
      ))}
    </div>
  );
}
