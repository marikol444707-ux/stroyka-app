import React from 'react';
import { Check, Eye, GitBranch, Printer } from 'lucide-react';
import { C, badge, btnB, btnGr, btnO, card } from '../constants/uiTheme';
import { estimateReconciliationStatusView } from '../utils/statusMetaUtils';

export default function EstimateReconciliationsPanel({
  project,
  reconciliations,
  projectEstimates,
  estimateDiffBaseFor,
  estimatePackage,
  estimateTotal,
  estimateUpdatedTs,
  canApprove,
  onApprove,
  onCreate,
  onOpenPreview,
}) {
  const recs = reconciliations || [];
  const pairMap = new Map();
  (projectEstimates || []).forEach(est => {
    const base = estimateDiffBaseFor(est);
    if (!base || base.projectName !== project.name || Number(base.id) === Number(est.id)) return;
    const key = String(base.id) + '|' + String(est.id);
    if (!pairMap.has(key)) pairMap.set(key, {base, next: est});
  });
  const pairs = Array.from(pairMap.values()).sort((a,b)=>(estimateUpdatedTs(b.next)||Number(b.next.id||0))-(estimateUpdatedTs(a.next)||Number(a.next.id||0)));
  const fmtMoney = (n) => (Number(n||0)>0?'+':'')+Math.round(Number(n||0)).toLocaleString('ru-RU')+' ₽';

  return (
    <div>
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:'10px',flexWrap:'wrap',marginBottom:'15px'}}>
        <div>
          <b style={{color:C.text,fontSize:'15px'}}>Сверки смет</b>
          <p style={{color:C.textSec,margin:'2px 0 0',fontSize:'12px'}}>Сравнение редакций сметы с фиксацией спорных позиций и связью с реестром документов.</p>
        </div>
        <span style={badge(C.info,C.infoLight,C.infoBorder)}>{recs.length+' док.'}</span>
      </div>
      {pairs.length>0&&(
        <div style={{...card,padding:'12px',marginBottom:'14px',backgroundColor:C.bg}}>
          <b style={{color:C.text,fontSize:'13px',display:'block',marginBottom:'8px'}}>Создать сверку по редакциям</b>
          <div style={{display:'grid',gap:'8px'}}>
            {pairs.slice(0,6).map(({base,next})=>{
              const existing = recs.find(r=>Number(r.baseEstimateId)===Number(base.id)&&Number(r.nextEstimateId)===Number(next.id));
              const diff = estimateTotal(next)-estimateTotal(base);
              return (
                <div key={base.id+'-'+next.id} style={{padding:'10px',border:'1px solid '+C.border,borderRadius:'8px',backgroundColor:C.bgWhite,display:'flex',justifyContent:'space-between',alignItems:'center',gap:'10px',flexWrap:'wrap'}}>
                  <div style={{minWidth:'240px',flex:1}}>
                    <b style={{color:C.text,fontSize:'12px'}}>{estimatePackage(next)+' · '+(base.name||'База')+' → '+(next.name||'Новая')}</b>
                    <p style={{color:C.textSec,margin:'2px 0 0',fontSize:'11px'}}>{'v'+(base.version||'')+' → v'+(next.version||'')+' · разница '+fmtMoney(diff)}</p>
                  </div>
                  {existing
                    ? <button onClick={()=>onOpenPreview(existing)} style={{...btnB,padding:'6px 10px',fontSize:'12px'}}><Eye size={13}/>Открыть №{existing.id}</button>
                    : <button onClick={()=>onCreate(base,next)} style={{...btnO,padding:'6px 10px',fontSize:'12px'}}><GitBranch size={13}/>Создать сверку</button>}
                </div>
              );
            })}
          </div>
        </div>
      )}
      {recs.length===0?(
        <div style={{...card,padding:'26px',textAlign:'center',color:C.textMuted}}>
          Сверок смет по объекту пока нет. Загрузите новую редакцию сметы или создайте сверку из пары выше.
        </div>
      ):(
        <div style={{display:'grid',gap:'10px'}}>
          {recs.map(rec=>{
            const st = estimateReconciliationStatusView(rec.status);
            return (
              <div key={rec.id} style={{...card,padding:'14px',borderLeft:'3px solid '+st.color}}>
                <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'10px',flexWrap:'wrap'}}>
                  <div style={{minWidth:'260px',flex:1}}>
                    <div style={{display:'flex',gap:'6px',alignItems:'center',flexWrap:'wrap',marginBottom:'4px'}}>
                      <b style={{color:C.text,fontSize:'13px'}}>Сверка смет № {rec.id}</b>
                      <span style={badge(st.color,st.bg,st.border)}>{st.label}</span>
                      <span style={badge(C.textSec,C.bgGray,C.border)}>{rec.workPackage||'Основная'}</span>
                    </div>
                    <p style={{color:C.textSec,margin:'2px 0',fontSize:'12px'}}>{(rec.baseEstimateName||'База')+' v'+(rec.baseVersion||'')+' → '+(rec.nextEstimateName||'Новая')+' v'+(rec.nextVersion||'')}</p>
                    <p style={{color:C.textMuted,margin:'2px 0 0',fontSize:'11px'}}>{'Изменено: '+(rec.changedCount||0)+' · добавлено: '+(rec.addedCount||0)+' · исключено: '+(rec.removedCount||0)+' · проверить: '+(rec.reviewCount||0)}</p>
                  </div>
                  <div style={{display:'flex',gap:'6px',alignItems:'center',flexWrap:'wrap',justifyContent:'flex-end'}}>
                    <b style={{color:Number(rec.impact||0)>=0?C.warning:C.success,fontSize:'13px',whiteSpace:'nowrap'}}>{fmtMoney(rec.impact)}</b>
                    <button onClick={()=>onOpenPreview(rec)} style={{...btnB,padding:'5px 9px',fontSize:'11px'}}><Printer size={12}/>Печать</button>
                    {canApprove&&rec.status!=='Утверждена'&&<button onClick={()=>onApprove(rec)} style={{...btnGr,padding:'5px 9px',fontSize:'11px'}}><Check size={12}/>Утвердить</button>}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
