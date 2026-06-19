import React from 'react';
import { Plus } from 'lucide-react';

export default function CrmHeader({C, btnO, onNewLead, isMobile=false}) {
  return (
    <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:'10px',flexWrap:'wrap',marginBottom:'20px'}}>
      <h3 style={{color:C.text,margin:0,fontSize:isMobile?'15px':'16px',fontWeight:'700',minWidth:0,overflowWrap:'anywhere'}}>CRM — Лиды</h3>
      <button onClick={onNewLead} style={{...btnO,width:isMobile?'100%':'auto',justifyContent:'center',minHeight:isMobile?'44px':undefined}}>
        <Plus size={14}/>Новый лид
      </button>
    </div>
  );
}
