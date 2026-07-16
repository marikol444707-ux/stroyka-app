import React from 'react';
import { ChevronDown, ChevronRight, GitCompareArrows, ShieldCheck } from 'lucide-react';
import { buildLegacyMaterialProjection, buildMaterialProjectionDryRun } from '../utils/materialProjectionDryRunUtils';

const changeLabel = {
  quantity_changed: 'Изменилось количество',
  split: 'Разделено на точные позиции',
  corrected_only: 'Новая позиция',
  legacy_only: 'Осталась только в старом расчёте',
};

const countLabel = count => {
  const mod100 = count % 100;
  const mod10 = count % 10;
  const word = mod100 >= 11 && mod100 <= 14 ? 'изменений' : (mod10 === 1 ? 'изменение' : (mod10 >= 2 && mod10 <= 4 ? 'изменения' : 'изменений'));
  return `${count} ${word}`;
};

export default function MaterialProjectionDryRunPanel({projectName, rows = [], C, fmtMeasure, isMobile = false}) {
  const [expanded, setExpanded] = React.useState(false);
  const report = React.useMemo(() => {
    if (!expanded) return null;
    const correctedRows = (rows || []).filter(row => Number(row.planQty || 0) > 0);
    const legacyRows = buildLegacyMaterialProjection(correctedRows);
    return buildMaterialProjectionDryRun([{projectName, legacyRows, correctedRows}]);
  }, [expanded, projectName, rows]);
  const projectReport = report?.projects?.[0] || {changes: [], summary: {}};
  const changes = projectReport.changes || [];
  const summary = projectReport.summary || {};

  return (
    <section aria-label="Проверка расчёта материалов" style={{borderTop:'1px solid '+C.border,borderBottom:'1px solid '+C.border,margin:'0 0 12px',padding:'10px 0'}}>
      <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',gap:'10px',flexWrap:'wrap'}}>
        <div style={{display:'flex',alignItems:'center',gap:'9px',minWidth:0}}>
          <GitCompareArrows size={18} color={expanded ? (changes.length ? C.warning : C.success) : C.info}/>
          <div style={{minWidth:0}}>
            <b style={{display:'block',color:C.text,fontSize:'13px'}}>Проверка расчёта материалов</b>
            <span style={{display:'block',color:C.textSec,fontSize:'11px',marginTop:'2px'}}>
              {expanded
                ? `${changes.length ? countLabel(changes.length) : 'Расхождений не найдено'} · старых строк ${summary.legacyRows || 0} · новых ${summary.correctedRows || 0}`
                : `Строк текущего расчёта: ${(rows || []).filter(row => Number(row.planQty || 0) > 0).length}`}
            </span>
          </div>
        </div>
        <button
          type="button"
          aria-expanded={expanded}
          aria-label={expanded ? 'Закрыть проверку расчёта' : 'Открыть проверку расчёта'}
          onClick={()=>setExpanded(value=>!value)}
          style={{display:'inline-flex',alignItems:'center',gap:'6px',padding:'7px 9px',border:'1px solid '+C.border,borderRadius:'6px',backgroundColor:C.bgWhite,color:C.text,fontSize:'11px',fontWeight:'700',cursor:'pointer'}}
        >
          {expanded?<ChevronDown size={14}/>:<ChevronRight size={14}/>} {expanded?'Скрыть':'Посмотреть'}
        </button>
      </div>

      {expanded && (
        <div style={{marginTop:'10px'}}>
          <div style={{display:'flex',alignItems:'center',gap:'7px',padding:'8px 0',color:C.success,fontSize:'11px',fontWeight:'700'}}>
            <ShieldCheck size={15}/><span>Только просмотр</span>
            <span style={{color:C.textSec,fontWeight:'500'}}>Смета, заявки и склад не изменяются.</span>
          </div>
          <div style={{display:'grid',gridTemplateColumns:isMobile?'repeat(2,minmax(0,1fr))':'repeat(5,minmax(110px,1fr))',borderTop:'1px solid '+C.border,borderLeft:'1px solid '+C.border}}>
            {[
              ['Без изменений', summary.unchanged || 0],
              ['Количество', summary.quantityChanged || 0],
              ['Разделено', summary.splitRows || 0],
              ['Новые', summary.correctedOnly || 0],
              ['Только старые', summary.legacyOnly || 0],
            ].map(([label,value])=><div key={label} style={{padding:'8px',borderRight:'1px solid '+C.border,borderBottom:'1px solid '+C.border,minWidth:0}}><span style={{display:'block',color:C.textSec,fontSize:'10px'}}>{label}</span><b style={{display:'block',color:value?C.warning:C.text,fontSize:'15px',marginTop:'2px'}}>{value}</b></div>)}
          </div>

          {changes.length === 0 ? (
            <p role="status" style={{color:C.success,fontSize:'12px',margin:'10px 0 0'}}>Текущие строки совпадают с восстановленным старым расчётом.</p>
          ) : (
            <div style={{marginTop:'10px',borderTop:'1px solid '+C.border}}>
              {changes.map((change,index)=><div key={(change.key||change.legacyKey||change.status)+'-'+index} style={{display:'grid',gridTemplateColumns:isMobile?'1fr':'minmax(220px,1.4fr) minmax(130px,.7fr) minmax(180px,1fr)',gap:'8px',padding:'10px 0',borderBottom:'1px solid '+C.border,alignItems:'start'}}>
                <div style={{minWidth:0}}>
                  <b style={{display:'block',color:C.text,fontSize:'12px'}}>{change.status==='split' ? change.legacyName : change.name}</b>
                  <span style={{display:'block',color:C.warning,fontSize:'10px',fontWeight:'700',marginTop:'3px'}}>{changeLabel[change.status] || change.status}</span>
                </div>
                <div style={{fontSize:'11px',color:C.textSec}}>
                  <span style={{display:'block',fontSize:'10px'}}>Старый общий расчёт</span>
                  <b style={{display:'block',color:C.text,marginTop:'2px'}}>{change.legacyQty === undefined ? '—' : fmtMeasure(change.legacyQty, change.unit || '')}</b>
                </div>
                <div style={{fontSize:'11px',color:C.textSec,minWidth:0}}>
                  <span style={{display:'block',fontSize:'10px'}}>Новый точный расчёт</span>
                  {change.status==='split'
                    ? <div style={{marginTop:'2px'}}>{(change.correctedRows||[]).map(row=><span key={row.key} style={{display:'flex',justifyContent:'space-between',gap:'8px',color:C.text,fontWeight:'700'}}><span style={{overflowWrap:'anywhere'}}>{row.name}</span><span style={{whiteSpace:'nowrap'}}>{fmtMeasure(row.qty,row.unit)}</span></span>)}</div>
                    : <b style={{display:'block',color:C.text,marginTop:'2px'}}>{change.correctedQty === undefined ? '—' : fmtMeasure(change.correctedQty,change.unit||'')}</b>}
                </div>
              </div>)}
            </div>
          )}
        </div>
      )}
    </section>
  );
}
