import React from 'react';
import { Printer } from 'lucide-react';
import { C, badge, btnB, card, tbl, tblC, tblH } from '../constants/uiTheme';
import { fmtMeasure, toNum } from '../utils/measureUtils';
import { workJournalEstimateStatusMeta } from '../utils/statusMetaUtils';

export default function WorkJournalEstimateReconciliationPanel({
  project,
  summary,
  onPrint,
}) {
  const s = summary || {rows: [], linkedRows: [], reviewRows: [], outsideRows: [], overRows: []};
  const rows = (s.rows || []).slice(0, 80);
  const pct = s.estimatePlan > 0 ? Math.round(s.estimateDone / s.estimatePlan * 1000) / 10 : 0;
  const cardMini = (label, value, color=C.text, bg=C.bg, border=C.border) => (
    <div style={{padding:'10px',backgroundColor:bg,borderRadius:'8px',border:'1px solid '+border}}>
      <p style={{color:C.textSec,fontSize:'10px',margin:'0 0 3px'}}>{label}</p>
      <b style={{color,fontSize:'15px'}}>{value}</b>
    </div>
  );

  return (
    <div>
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:'8px',flexWrap:'wrap',marginBottom:'14px'}}>
        <div>
          <b style={{color:C.text,fontSize:'15px'}}>🔎 Сверка ЖПР ↔ смета</b>
          <p style={{color:C.textSec,fontSize:'12px',margin:'3px 0 0'}}>Показывает, какие фактические работы найдены в активной смете заказчика, а какие надо проверить или оформить как изменение.</p>
        </div>
        <button onClick={() => onPrint(project)} style={btnB}><Printer size={14}/>Печать</button>
      </div>
      <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(145px,1fr))',gap:'8px',marginBottom:'12px'}}>
        {cardMini('Строк ЖПР', (s.rows || []).length)}
        {cardMini('Найдено в смете', (s.linkedRows || []).length, C.success, C.successLight, C.successBorder)}
        {cardMini('На проверку', (s.reviewRows || []).length, C.warning, C.warningLight, C.warningBorder)}
        {cardMini('Вне сметы', (s.outsideRows || []).length, C.danger, C.dangerLight, C.dangerBorder)}
        {cardMini('Превышение', (s.overRows || []).length, C.danger, C.dangerLight, C.dangerBorder)}
      </div>
      <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(170px,1fr))',gap:'8px',marginBottom:'14px'}}>
        {cardMini('Активная смета', Math.round(s.estimatePlan || 0).toLocaleString('ru-RU')+' ₽', C.text, C.bgWhite, C.border)}
        {cardMini('Закрыто в смете', Math.round(s.estimateDone || 0).toLocaleString('ru-RU')+' ₽ · '+pct+'%', C.success, C.successLight, C.successBorder)}
        {cardMini('Сумма ЖПР', Math.round(s.journalTotal || 0).toLocaleString('ru-RU')+' ₽', C.accent, C.accentLight, C.accentBorder)}
        {cardMini('ЖПР вне сметы', Math.round(s.outsideTotal || 0).toLocaleString('ru-RU')+' ₽', C.danger, C.dangerLight, C.dangerBorder)}
      </div>
      <div style={{padding:'10px 12px',backgroundColor:C.infoLight,border:'1px solid '+C.infoBorder,borderRadius:'10px',color:C.info,fontSize:'12px',marginBottom:'12px'}}>
        Сверка не переносит работы автоматически. Она даёт сметчику список: что уже похоже сидит в смете, что спорно, и что нужно внести в следующую редакцию или оформить изменением.
      </div>
      {(s.rows || []).length===0 ? (
        <div style={{...card,padding:'30px',textAlign:'center',color:C.textMuted}}>Записей ЖПР для сверки нет</div>
      ) : (
        <div style={{overflowX:'auto'}}>
          <table style={{...tbl,fontSize:'11px',minWidth:'1220px'}}>
            <thead>
              <tr>
                <th style={tblH}>Статус</th><th style={tblH}>Дата</th><th style={tblH}>ЖПР</th><th style={tblH}>Объём</th><th style={tblH}>Сумма ЖПР</th><th style={tblH}>Совпадение в смете</th><th style={tblH}>План</th><th style={tblH}>Сделано</th><th style={tblH}>Оценка по смете</th><th style={tblH}>Увер.</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(r => {
                const st = workJournalEstimateStatusMeta(r.status);
                const m = r.match;
                return (
                  <tr key={r.key}>
                    <td style={tblC}><span style={badge(st.color,st.bg,st.border)}>{r.status}</span>{r.overQty>0&&<p style={{margin:'4px 0 0',fontSize:'10px',color:C.danger}}>сверх: {fmtMeasure(r.overQty,m?.unit||r.workUnit)}</p>}</td>
                    <td style={tblC}>{r.work.date||'—'}</td>
                    <td style={tblC}><b style={{fontSize:'12px'}}>{r.work.description}</b><p style={{color:C.textMuted,fontSize:'10px',margin:'2px 0 0'}}>{r.work.masterName||'—'}{r.work.status?' · '+r.work.status:''}</p></td>
                    <td style={tblC}>{fmtMeasure(r.workQty,r.workUnit)}</td>
                    <td style={{...tblC,fontWeight:'700',color:C.accent}}>{Math.round(toNum(r.work.total)).toLocaleString('ru-RU')+' ₽'}</td>
                    <td style={tblC}>{m?<><b style={{fontSize:'12px'}}>{m.itemName}</b><p style={{color:C.textMuted,fontSize:'10px',margin:'2px 0 0'}}>{(m.packageName&&m.packageName!=='Основная'?m.packageName+' / ':'')+m.sectionName}</p></>:<span style={{color:C.textMuted}}>—</span>}</td>
                    <td style={tblC}>{m?fmtMeasure(m.planQty,m.unit):'—'}</td>
                    <td style={tblC}>{m?fmtMeasure(m.doneQty,m.unit):'—'}</td>
                    <td style={{...tblC,fontWeight:'700',color:r.estimateValue?C.success:C.textMuted}}>{r.estimateValue?Math.round(r.estimateValue).toLocaleString('ru-RU')+' ₽':'—'}</td>
                    <td style={tblC}>{r.score?Math.round(r.score*100)+'%':'—'}{!r.unitOk&&m&&<p style={{fontSize:'10px',color:C.warning,margin:'2px 0 0'}}>ед. изм. не совпала</p>}</td>
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
