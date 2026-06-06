import React from 'react';
import { X } from 'lucide-react';

export default function MaterialNormNotice({C, card, btnG, materialNormNotice, setMaterialNormNotice}) {
  if (!materialNormNotice) return null;

  const ok = materialNormNotice.tone === 'success';

  return (
    <div style={{...card,padding:'12px 14px',marginBottom:'14px',backgroundColor:ok?C.successLight:C.infoLight,border:'1.5px solid '+(ok?C.successBorder:C.infoBorder),display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'12px'}}>
      <div>
        <b style={{color:C.text,fontSize:'13px',display:'block',marginBottom:'3px'}}>{materialNormNotice.title}</b>
        <p style={{color:C.textSec,margin:0,fontSize:'12px',lineHeight:1.45}}>{materialNormNotice.text}</p>
      </div>
      <button onClick={()=>setMaterialNormNotice(null)} style={{...btnG,padding:'4px 8px',fontSize:'11px',flex:'0 0 auto'}}>
        <X size={12}/>
      </button>
    </div>
  );
}
