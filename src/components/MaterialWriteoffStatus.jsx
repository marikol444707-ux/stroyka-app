import React from 'react';

export default function MaterialWriteoffStatus({
  rows = [],
  C,
  fmtMeasure,
  isMobile = false,
  isPersonalMaterialRole,
  onSourceChange,
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
            {row.materialAccountingVersion === 2 && <div style={{gridColumn:'1 / -1',display:'flex',flexWrap:'wrap',gap:'8px',color:C.text}}>
              <span>С остатка мастера: <b>{fmtMeasure(row.personalQuantity,row.unit)}</b></span>
              <span>Со склада: <b>{fmtMeasure(row.warehouseQuantity,row.unit)}</b></span>
              {onSourceChange && <label>Источник:{' '}
                <select aria-label={'Источник материала «'+row.name+'»'} value={row.sourcePreference || 'auto'}
                  onChange={event => onSourceChange(row.name,event.target.value)}>
                  <option value="auto">Сначала остаток мастера, затем склад</option>
                  <option value="personal">Только остаток мастера</option>
                  <option value="warehouse">Только склад объекта</option>
                </select>
              </label>}
              {row.sourceConflict && <span role="alert">Уточните складскую позицию и единицу материала.</span>}
            </div>}
          </div>
        );
      })}
    </div>
  );
}
