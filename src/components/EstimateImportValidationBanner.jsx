import React from 'react';

export default function EstimateImportValidationBanner({
  C,
  card,
  importValidating,
  importValidationWarnings,
  setImportValidationWarnings,
}) {
  if (!importValidating && !(importValidationWarnings||[]).length) return null;

  const hasCritical = (importValidationWarnings||[]).some(w => w.severity === 'критично');
  const toneColor = importValidating ? C.info : (hasCritical ? C.danger : C.warning);

  return (
    <div
      style={{
        ...card,
        padding:'14px',
        marginBottom:'14px',
        backgroundColor: importValidating ? C.infoLight : (hasCritical ? C.dangerLight : C.warningLight),
        border: '1.5px solid '+(importValidating ? C.infoBorder : (hasCritical ? C.dangerBorder : C.warningBorder)),
      }}
    >
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'8px'}}>
        <b style={{fontSize:'13px',color:toneColor}}>
          {importValidating ? '🤖 ИИ проверяет смету...' : ('⚠️ Найдено замечаний: '+importValidationWarnings.length)}
        </b>
        {!importValidating&&<button onClick={()=>setImportValidationWarnings([])} style={{background:'none',border:'none',cursor:'pointer',fontSize:'16px',color:C.textSec}}>×</button>}
      </div>
      {(importValidationWarnings||[]).length>0&&(
        <div>
          {importValidationWarnings.map((w,i)=>(
            <div
              key={i}
              style={{
                padding:'6px 8px',
                marginBottom:'4px',
                backgroundColor:'rgba(255,255,255,0.6)',
                borderRadius:'6px',
                borderLeft:'3px solid '+(w.severity==='критично'?C.danger:w.severity==='внимание'?C.warning:C.info),
              }}
            >
              <b style={{fontSize:'11px',color:C.text}}>{(w.severity==='критично'?'🔴 ':w.severity==='внимание'?'🟡 ':'💡 ')+(w.where||'?')}</b>
              <p style={{fontSize:'11px',color:C.textSec,margin:'2px 0 0'}}>{w.message||''}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
