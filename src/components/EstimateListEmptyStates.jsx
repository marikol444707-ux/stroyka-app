import React from 'react';
import { Calculator } from 'lucide-react';

export default function EstimateListEmptyStates({C, card, normalCount, templatesCount, groupedCount}) {
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
        В активном списке только архивные сметы
      </div>
    );
  }

  return null;
}
