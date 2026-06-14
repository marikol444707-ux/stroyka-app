import React from 'react';

function isDistributableWorkItem(item) {
  const rawType = String(item?.itemType || item?.type || item?.kind || 'work').toLowerCase();
  const priceWork = Number(item?.priceWork || 0);
  const priceMaterial = Number(item?.priceMaterial || 0);
  if (['material', 'материал', 'materials', 'материалы', 'equipment', 'оборудование', 'delivery', 'доставка', 'other', 'прочее'].some(t => rawType.includes(t))) return false;
  if (priceWork <= 0 && priceMaterial > 0) return false;
  return true;
}

export default function EstimateDistributeItemsTable({
  C,
  inp,
  selectedEstimate,
  distributeAssignments,
  setDistributeAssignments,
  distributeBrigades,
}) {
  const sections = (selectedEstimate.sections || []).map((section, sectionIndex) => ({
    ...section,
    sectionIndex,
    items: (section.items || []).map((item, itemIndex) => ({ item, itemIndex })).filter(({ item }) => isDistributableWorkItem(item)),
  })).filter(section => section.items.length > 0);

  return (
    <div style={{maxHeight:'380px',overflowY:'auto',marginBottom:'10px'}}>
      {sections.length === 0 && <div style={{padding:'12px',color:C.textSec,fontSize:'12px'}}>В смете нет рабочих позиций для распределения.</div>}
      {sections.map((s)=>(
        <div key={s.sectionIndex} style={{marginBottom:'10px'}}>
          <div style={{padding:'4px 8px',backgroundColor:C.accentLight,borderRadius:'4px',marginBottom:'4px'}}><b style={{fontSize:'11px',color:C.accent}}>{s.name}</b></div>
          {s.items.map(({item:it,itemIndex})=>{const key=s.sectionIndex+'-'+itemIndex;return(
            <div key={itemIndex} style={{display:'grid',gridTemplateColumns:'1fr 70px 80px 1fr',gap:'6px',padding:'4px 8px',alignItems:'center',fontSize:'11px',borderBottom:'1px solid '+C.border}}>
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
