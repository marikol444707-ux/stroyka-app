import React from 'react';
import { Printer } from 'lucide-react';
import { C, badge, btnB, btnG, btnO, card, tbl, tblC, tblH } from '../constants/uiTheme';
import { fmtMeasure } from '../utils/measureUtils';
import { measurementEstimateStatusMeta } from '../utils/statusMetaUtils';

export default function EstimateMeasurementComparisonPanel({
  project,
  summary,
  totals,
  estimateChangeForComparisonRow,
  onCreateEstimateChange,
  onOpenChangesTab,
  onPrint,
}) {
  const s = summary || {rows: [], overRows: [], missingRows: [], manualRows: []};
  const t = totals || {};
  const rows = (s.rows || []).slice(0, 12);

  return (
    <div style={{...card,padding:'14px',marginBottom:'14px',backgroundColor:C.bgWhite,border:'1.5px solid '+((s.overRows || []).length?C.dangerBorder:(s.missingRows || []).length||(s.manualRows || []).length?C.warningBorder:C.successBorder)}}>
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:'8px',flexWrap:'wrap',marginBottom:'12px'}}>
        <div>
          <b style={{color:C.text,fontSize:'14px'}}>📏 Смета ↔ обмеры помещений</b>
          <p style={{color:C.textSec,fontSize:'11px',margin:'2px 0 0'}}>Сравнение активной сметы заказчика с площадями помещений: стены, пол, потолок, откосы, окна и двери.</p>
        </div>
        <button onClick={() => onPrint(project)} style={{...btnB,fontSize:'12px',padding:'6px 12px'}}><Printer size={13}/>Печать</button>
      </div>
      <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(120px,1fr))',gap:'8px',marginBottom:'12px'}}>
        <div style={{padding:'10px',backgroundColor:C.bg,borderRadius:'8px',border:'1px solid '+C.border}}><p style={{color:C.textSec,fontSize:'10px',margin:'0 0 3px'}}>Строк</p><b style={{color:C.text,fontSize:'15px'}}>{(s.rows || []).length}</b></div>
        <div style={{padding:'10px',backgroundColor:(s.overRows || []).length?C.dangerLight:C.successLight,borderRadius:'8px',border:'1px solid '+((s.overRows || []).length?C.dangerBorder:C.successBorder)}}><p style={{color:(s.overRows || []).length?C.danger:C.success,fontSize:'10px',margin:'0 0 3px'}}>Сверх сметы</p><b style={{color:(s.overRows || []).length?C.danger:C.success,fontSize:'15px'}}>{(s.overRows || []).length}</b></div>
        <div style={{padding:'10px',backgroundColor:(s.missingRows || []).length?C.warningLight:C.bg,borderRadius:'8px',border:'1px solid '+((s.missingRows || []).length?C.warningBorder:C.border)}}><p style={{color:(s.missingRows || []).length?C.warning:C.textSec,fontSize:'10px',margin:'0 0 3px'}}>Нет обмера</p><b style={{color:(s.missingRows || []).length?C.warning:C.text,fontSize:'15px'}}>{(s.missingRows || []).length}</b></div>
        <div style={{padding:'10px',backgroundColor:(s.manualRows || []).length?C.infoLight:C.bg,borderRadius:'8px',border:'1px solid '+((s.manualRows || []).length?C.infoBorder:C.border)}}><p style={{color:(s.manualRows || []).length?C.info:C.textSec,fontSize:'10px',margin:'0 0 3px'}}>Ед. изм.</p><b style={{color:(s.manualRows || []).length?C.info:C.text,fontSize:'15px'}}>{(s.manualRows || []).length}</b></div>
        <div style={{padding:'10px',backgroundColor:C.bg,borderRadius:'8px',border:'1px solid '+C.border}}><p style={{color:C.textSec,fontSize:'10px',margin:'0 0 3px'}}>Оценка доп.</p><b style={{color:s.overSum>0?C.danger:C.text,fontSize:'15px'}}>{Math.round(s.overSum || 0).toLocaleString('ru-RU')+' ₽'}</b></div>
      </div>
      <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(150px,1fr))',gap:'8px',marginBottom:'12px'}}>
        <div style={{padding:'10px',backgroundColor:C.bg,borderRadius:'8px',border:'1px solid '+C.border}}><p style={{color:C.textSec,fontSize:'10px',margin:'0 0 3px'}}>Стены общие</p><b style={{color:C.text,fontSize:'14px'}}>{fmtMeasure(t.wall_gross_area,'м2')}</b></div>
        <div style={{padding:'10px',backgroundColor:C.dangerLight,borderRadius:'8px',border:'1px solid '+C.dangerBorder}}><p style={{color:C.danger,fontSize:'10px',margin:'0 0 3px'}}>Вычет окон</p><b style={{color:C.danger,fontSize:'14px'}}>{'- '+fmtMeasure(t.window_area,'м2')}</b></div>
        <div style={{padding:'10px',backgroundColor:C.dangerLight,borderRadius:'8px',border:'1px solid '+C.dangerBorder}}><p style={{color:C.danger,fontSize:'10px',margin:'0 0 3px'}}>Вычет дверей</p><b style={{color:C.danger,fontSize:'14px'}}>{'- '+fmtMeasure(t.door_area,'м2')}</b></div>
        <div style={{padding:'10px',backgroundColor:C.successLight,borderRadius:'8px',border:'1px solid '+C.successBorder}}><p style={{color:C.success,fontSize:'10px',margin:'0 0 3px'}}>Стены чистые</p><b style={{color:C.success,fontSize:'14px'}}>{fmtMeasure(t.wall_net_area,'м2')}</b></div>
      </div>
      {(s.rows || []).length===0 ? (
        <p style={{color:C.textMuted,fontSize:'12px',textAlign:'center',padding:'14px'}}>Нет активной сметы заказчика или рабочих строк для сравнения.</p>
      ) : (
        <div style={{overflowX:'auto'}}>
          <table style={{...tbl,fontSize:'11px',minWidth:'1080px'}}>
            <thead><tr><th style={tblH}>Статус</th><th style={tblH}>Раздел / позиция</th><th style={tblH}>Основание</th><th style={tblH}>Смета</th><th style={tblH}>Обмер</th><th style={tblH}>Разница</th><th style={tblH}>Оценка</th><th style={tblH}>Действие</th></tr></thead>
            <tbody>
              {rows.map(r => {
                const st = measurementEstimateStatusMeta(r.status);
                const unit = r.expectedUnit || r.planUnit;
                const existing = estimateChangeForComparisonRow(project.name, r);
                const canCreate = ['Сверх сметы','В смете больше'].includes(r.status) && r.supported && r.unitOk;
                return (
                  <tr key={r.key}>
                    <td style={tblC}><span style={badge(st.color,st.bg,st.border)}>{r.status}</span></td>
                    <td style={tblC}><b style={{fontSize:'12px'}}>{r.itemName}</b><p style={{color:C.textMuted,fontSize:'10px',margin:'2px 0 0'}}>{(r.packageName&&r.packageName!=='Основная'?r.packageName+' / ':'')+r.sectionName}</p></td>
                    <td style={tblC}>{r.basisIcon+' '+r.basisLabel}{r.supported&&!r.unitOk&&<p style={{color:C.warning,fontSize:'10px',margin:'2px 0 0'}}>ожидается {r.expectedUnit}, в смете {r.planUnit||'—'}</p>}</td>
                    <td style={tblC}>{fmtMeasure(r.planQty,r.planUnit)}</td>
                    <td style={tblC}>{r.supported&&r.unitOk?fmtMeasure(r.measuredQty,unit):'—'}</td>
                    <td style={{...tblC,fontWeight:'700',color:r.diff>0?C.danger:r.diff<0?C.warning:C.success}}>{r.supported&&r.unitOk?((r.diff>0?'+':'')+fmtMeasure(r.diff,unit)):'—'}</td>
                    <td style={{...tblC,fontWeight:'700',color:r.overSum>0?C.danger:C.textMuted}}>{r.overSum>0?Math.round(r.overSum).toLocaleString('ru-RU')+' ₽':'—'}</td>
                    <td style={tblC}>{existing?<button onClick={onOpenChangesTab} style={{...btnG,padding:'4px 8px',fontSize:'11px'}}>Уже оформлено</button>:canCreate?<button onClick={()=>onCreateEstimateChange(project,r)} style={{...(r.status==='Сверх сметы'?btnO:btnB),padding:'4px 8px',fontSize:'11px'}}>Оформить</button>:<span style={{color:C.textMuted}}>—</span>}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {(s.rows || []).length>rows.length&&<p style={{color:C.textMuted,fontSize:'11px',margin:'8px 0 0'}}>Показаны первые {rows.length} строк. Полный список — в печатном отчёте.</p>}
        </div>
      )}
    </div>
  );
}
