import React from 'react';
import { Plus } from 'lucide-react';

export default function CrmHeader({C, btnO, onNewLead}) {
  return (
    <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'20px'}}>
      <h3 style={{color:C.text,margin:0,fontSize:'16px',fontWeight:'700'}}>CRM — Лиды</h3>
      <button onClick={onNewLead} style={btnO}><Plus size={14}/>Новый лид</button>
    </div>
  );
}
