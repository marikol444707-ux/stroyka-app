import React from 'react';
import { Plus } from 'lucide-react';

export default function EstimateAddSectionForm({card, inp, btnO, newEstimateSection, setNewEstimateSection, onAdd}) {
  return (
    <div style={{...card,padding:'16px',marginBottom:'16px'}}>
      <div style={{display:'flex',gap:'8px',marginBottom:'10px',alignItems:'center'}}>
        <input
          placeholder="Новый раздел"
          value={newEstimateSection.name}
          onChange={e=>setNewEstimateSection({name:e.target.value})}
          style={{...inp,marginBottom:0,flex:1}}
        />
        <button onClick={onAdd} style={btnO}>
          <Plus size={14}/>Раздел
        </button>
      </div>
    </div>
  );
}
