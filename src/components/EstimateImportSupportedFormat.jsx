import React from 'react';

export default function EstimateImportSupportedFormat({C}) {
  return (
    <div style={{marginTop:'20px',padding:'15px',backgroundColor:C.bg,borderRadius:'10px',border:'1.5px solid '+C.border}}>
      <b style={{color:C.text,fontSize:'13px',display:'block',marginBottom:'8px'}}>📋 Поддерживаемый формат:</b>
      <p style={{color:C.textSec,fontSize:'12px',margin:'3px 0'}}>✅ Гранд Смета версии 2024-2025</p>
      <p style={{color:C.textSec,fontSize:'12px',margin:'3px 0'}}>✅ Разделы и подразделы</p>
      <p style={{color:C.textSec,fontSize:'12px',margin:'3px 0'}}>✅ Наименование, единица, количество, стоимость</p>
      <p style={{color:C.textSec,fontSize:'12px',margin:'3px 0'}}>✅ До 5000+ позиций</p>
    </div>
  );
}
