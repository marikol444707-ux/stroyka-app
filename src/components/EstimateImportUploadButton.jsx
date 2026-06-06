import React from 'react';
import { Upload } from 'lucide-react';

export default function EstimateImportUploadButton({C, onFileChange}) {
  return (
    <label style={{display:'inline-flex',alignItems:'center',gap:'10px',cursor:'pointer',backgroundColor:C.accentLight,padding:'14px 24px',borderRadius:'10px',border:'1.5px dashed '+C.accent,fontSize:'14px',color:C.accent,fontWeight:'600'}}>
      <Upload size={20}/>Загрузить Excel файл (.xlsx)
      <input type="file" accept=".xlsx,.xls" style={{display:'none'}} onChange={onFileChange}/>
    </label>
  );
}
