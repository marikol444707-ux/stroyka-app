import React from 'react';

export default function EstimateTemplatesList({
  C,
  card,
  templates,
  setSelectedEstimate,
  estimateKind,
  estimateTotal,
}) {
  if (!templates.length) return null;

  return (
    <div style={{...card,marginBottom:'12px'}}>
      <div style={{padding:'12px 14px',backgroundColor:C.bg,borderBottom:'1.5px solid '+C.border}}>
        <b style={{color:C.text,fontSize:'13px'}}>⭐ Шаблоны смет</b>
      </div>
      <div style={{padding:'8px 12px'}}>
        {templates.map(est=>(
          <div key={est.id} onClick={()=>setSelectedEstimate(est)} style={{padding:'10px 8px',borderBottom:'1px solid '+C.border,display:'flex',justifyContent:'space-between',alignItems:'center',cursor:'pointer'}}>
            <div>
              <b style={{color:C.text,fontSize:'13px'}}>{est.name}</b>
              <p style={{color:C.textSec,margin:'2px 0',fontSize:'12px'}}>{estimateKind(est)}</p>
            </div>
            <b style={{color:C.success,fontSize:'13px'}}>{Math.round(estimateTotal(est)).toLocaleString('ru-RU')+' ₽'}</b>
          </div>
        ))}
      </div>
    </div>
  );
}
