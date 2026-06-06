import React from 'react';
import { Bot } from 'lucide-react';

export default function EstimateSectionHeader({C, btnG, sectionName, total, onMarkSectionBasis}) {
  return (
    <div style={{padding:'12px 16px',backgroundColor:C.bg,display:'flex',justifyContent:'space-between',alignItems:'center',borderBottom:'1.5px solid '+C.border}}>
      <b style={{color:C.accent,fontSize:'13px'}}>{'📁 '+sectionName}</b>
      <div style={{display:'flex',alignItems:'center',gap:'8px',flexWrap:'wrap',justifyContent:'flex-end'}}>
        <button onClick={onMarkSectionBasis} style={{...btnG,padding:'4px 9px',fontSize:'11px'}} title='Автоматически подобрать основание расчёта для работ раздела'>
          <Bot size={11}/>Основания
        </button>
        <b style={{color:C.text,fontSize:'13px'}}>{total.toLocaleString('ru-RU')+' ₽'}</b>
      </div>
    </div>
  );
}
