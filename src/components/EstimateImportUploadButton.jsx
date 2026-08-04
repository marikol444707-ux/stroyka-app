import React from 'react';
import { Upload } from 'lucide-react';

export default function EstimateImportUploadButton({C, onFileChange, disabled = false, disabledReason = '', loading = false}) {
  const label = loading ? 'Загружаю и пересчитываю...' : disabledReason || 'Загрузить Excel файл (.xlsx)';
  return (
    <label style={{display:'inline-flex',alignItems:'center',gap:'10px',cursor:disabled?'not-allowed':'pointer',backgroundColor:disabled?C.bgGray||C.accentLight:C.accentLight,padding:'14px 24px',borderRadius:'10px',border:'1.5px dashed '+(disabled?C.border||C.textMuted:C.accent),fontSize:'14px',color:disabled?C.textMuted:C.accent,fontWeight:'600',opacity:disabled?0.75:1}}>
      <Upload size={20}/>{label}
      <input aria-label={label} type="file" accept=".xlsx,.xlsm" disabled={disabled} style={{display:'none'}} onChange={onFileChange}/>
    </label>
  );
}
