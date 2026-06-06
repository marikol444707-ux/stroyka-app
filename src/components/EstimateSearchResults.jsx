import React from 'react';

const parseEstimateSections = (estimate) => {
  if (estimate.sections) return estimate.sections;
  if (typeof estimate.sectionsJson === 'string') {
    try {
      return JSON.parse(estimate.sectionsJson || '[]');
    } catch {
      return [];
    }
  }
  return estimate.sectionsJson || [];
};

export default function EstimateSearchResults({
  C,
  card,
  btnG,
  estimateSearch,
  estimatesList,
  setEstimateSearch,
  setSelectedEstimate,
  fmtMeasure,
  estimateItemTotal,
}) {
  if (!estimateSearch || estimateSearch.trim().length < 2) return null;

  const q = estimateSearch.toLowerCase().trim();
  const results = [];
  (estimatesList||[]).forEach(est => {
    const sects = parseEstimateSections(est);
    sects.forEach(sec => {
      (sec.items||[]).forEach(it => {
        const name = String(it.name||'').toLowerCase();
        if (name.includes(q)) results.push({estimate: est, section: sec, item: it});
      });
    });
  });

  return (
    <div style={{...card,padding:'14px',marginBottom:'16px',backgroundColor:C.bg}}>
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'10px'}}>
        <b style={{color:C.text,fontSize:'13px'}}>🔍 Найдено: {results.length} позиций по запросу «{estimateSearch}»</b>
        <button onClick={() => setEstimateSearch('')} style={{...btnG,padding:'4px 10px',fontSize:'11px'}}>Очистить</button>
      </div>
      {results.length===0 ? (
        <p style={{color:C.textMuted,fontSize:'12px',textAlign:'center',padding:'14px'}}>Ничего не найдено. Попробуйте другое слово.</p>
      ) : (
        <div style={{maxHeight:'400px',overflowY:'auto'}}>
          {results.slice(0,200).map((r,i) => (
            <div
              key={i}
              onClick={() => {
                setSelectedEstimate(r.estimate);
                setEstimateSearch('');
                setTimeout(() => {
                  const el = document.querySelector('[data-estitem="'+(r.item.id||r.item.name)+'"]');
                  if (el) el.scrollIntoView({behavior:'smooth',block:'center'});
                }, 300);
              }}
              style={{padding:'10px 12px',borderRadius:'8px',marginBottom:'6px',backgroundColor:C.bgWhite,border:'1.5px solid '+C.border,cursor:'pointer'}}
            >
              <b style={{fontSize:'13px',color:C.text,display:'block'}}>{r.item.name}</b>
              <p style={{color:C.textSec,margin:'3px 0 0',fontSize:'11px'}}>{'📋 '+r.estimate.name+' · '+(r.estimate.projectName||'—')+' · 📂 '+r.section.name}</p>
              <p style={{color:C.textMuted,margin:'2px 0 0',fontSize:'11px'}}>{fmtMeasure(r.item.quantity,r.item.unit)+' · 💰 '+Math.round(estimateItemTotal(r.item)).toLocaleString('ru-RU')+' ₽'}</p>
            </div>
          ))}
          {results.length>200&&<p style={{color:C.textMuted,fontSize:'11px',textAlign:'center',padding:'8px'}}>Показано первые 200 результатов. Уточните запрос.</p>}
        </div>
      )}
    </div>
  );
}
