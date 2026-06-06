import React from 'react';

export default function EstimateTotalCard({C, card, total}) {
  return (
    <div style={{...card,padding:'16px',backgroundColor:C.accentLight,border:'1.5px solid '+C.accentBorder}}>
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
        <b style={{color:C.text,fontSize:'14px'}}>ИТОГО по смете:</b>
        <b style={{color:C.accent,fontSize:'18px'}}>{Math.round(total).toLocaleString('ru-RU')+' ₽'}</b>
      </div>
    </div>
  );
}
