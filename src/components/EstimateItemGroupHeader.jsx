import React from 'react';

export default function EstimateItemGroupHeader({title, emoji, count, total, accent}) {
  return (
    <div style={{padding:'6px 10px',backgroundColor:accent+'15',borderRadius:'6px',display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'4px',borderLeft:'3px solid '+accent}}>
      <b style={{color:accent,fontSize:'12px'}}>{emoji+' '+title+' ('+count+')'}</b>
      <b style={{color:accent,fontSize:'12px'}}>{total.toLocaleString('ru-RU')+' ₽'}</b>
    </div>
  );
}
