import React from 'react';

export default function MaterialWriteoffStatus({
  rows = [],
  C,
  fmtMeasure,
  isMobile = false,
  isPersonalMaterialRole,
}) {
  const visibleRows = rows.filter(row => row.qty > 0 || row.normQty > 0);
  if (!visibleRows.length) return null;

  return (
    <div style={{display:'grid',gap:'5px',margin:'7px 0'}}>
      {visibleRows.map(row => {
        const tone = row.overStock ? 'danger' : row.overNorm || row.noNorm ? 'warning' : 'success';
        const color = tone === 'danger' ? C.danger : tone === 'warning' ? C.warning : C.success;
        const bg = tone === 'danger' ? C.dangerLight : tone === 'warning' ? C.warningLight : C.successLight;
        const borderColor = tone === 'danger' ? C.dangerBorder : tone === 'warning' ? C.warningBorder : C.successBorder;
        const sourceLabel = isPersonalMaterialRole() ? 'подтверждено к списанию' : 'на объекте';
        const label = row.overStock ? 'не хватает' : row.overNorm ? 'перерасход нормы' : row.noNorm ? 'без нормы' : 'в норме';

        return (
          <div key={row.key} style={{display:'grid',gridTemplateColumns:isMobile?'1fr':'minmax(0,1.3fr) repeat(3,auto)',gap:'6px 10px',alignItems:'center',padding:'6px 8px',borderRadius:'8px',border:'1px solid '+borderColor,backgroundColor:bg,fontSize:'10px'}}>
            <b style={{color:C.text,overflow:'hidden',textOverflow:'ellipsis',whiteSpace:isMobile?'normal':'nowrap'}}>{row.name}</b>
            <span style={{color:C.textSec}}>{sourceLabel+': '}<b style={{color:C.text}}>{row.stock?fmtMeasure(row.available,row.stock.unit||row.unit):'нет'}</b></span>
            <span style={{color:C.textSec}}>норма: <b style={{color:C.text}}>{row.normQty>0?fmtMeasure(row.normQty,row.unit):'—'}</b></span>
            <span style={{color}}>списать: <b>{fmtMeasure(row.qty,row.unit)}</b> · {label}</span>
          </div>
        );
      })}
    </div>
  );
}
