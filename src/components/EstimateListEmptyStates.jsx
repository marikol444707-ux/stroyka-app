import React from 'react';
import { Calculator } from 'lucide-react';

export default function EstimateListEmptyStates({
  C,
  card,
  normalCount,
  templatesCount,
  groupedCount,
  showArchivedEstimates,
  setShowArchivedEstimates,
}) {
  if (normalCount===0 && templatesCount===0) {
    return (
      <div style={{...card,padding:'40px',textAlign:'center',color:C.textMuted}}>
        <Calculator size={48} style={{marginBottom:'15px',opacity:0.3}}/>
        <p>Смет нет — создайте первую!</p>
      </div>
    );
  }

  if (normalCount>0 && groupedCount===0) {
    return (
      <div style={{...card,padding:'24px',textAlign:'center',color:C.textMuted}}>
        <div style={{marginBottom:'10px'}}>В активном списке только архивные сметы</div>
        {!showArchivedEstimates && (
          <button
            onClick={()=>setShowArchivedEstimates(true)}
            style={{
              background:'transparent',
              color:C.info,
              border:'1px solid '+C.infoBorder,
              borderRadius:'10px',
              padding:'8px 12px',
              cursor:'pointer',
              fontWeight:600,
            }}
          >
            Показать архив
          </button>
        )}
      </div>
    );
  }

  return null;
}
