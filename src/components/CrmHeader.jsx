import React from 'react';
import { Plus } from 'lucide-react';

export default function CrmHeader({C, btnO, onNewLead, isMobile=false}) {
  const touchCompact = typeof window !== 'undefined'
    && (window.visualViewport?.width || window.innerWidth || 0) < 1100
    && (
      (typeof window.matchMedia === 'function' && window.matchMedia('(pointer: coarse)').matches)
      || (typeof navigator !== 'undefined' && /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent || ''))
    );
  const compact = isMobile || touchCompact;
  return (
    <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:'10px',flexWrap:'wrap',marginBottom:'20px'}}>
      <h3 style={{color:C.text,margin:0,fontSize:compact?'15px':'16px',fontWeight:'700',minWidth:0,overflowWrap:'anywhere'}}>CRM — Лиды</h3>
      <button onClick={onNewLead} style={{...btnO,width:compact?'100%':'auto',justifyContent:'center',minHeight:compact?'44px':undefined}}>
        <Plus size={14}/>Новый лид
      </button>
    </div>
  );
}
