import { Check, Eye } from 'lucide-react';
import { C, badge, btnB, btnGr, tbl, tblC, tblH } from '../../constants/uiTheme';

export default function EstimateChangeReconcileTask({
  task,
  baseEstimate,
  nextEstimate,
  rows = [],
  fmtMeasure,
  onConfirmIncluded,
  onOpenTask,
}) {
  const scoreLabel = (score) => score ? Math.round(score * 100) + '%' : '—';

  return (
    <div style={{marginTop:'10px',padding:'10px',borderRadius:'10px',backgroundColor:C.bgWhite,border:'1.5px solid '+C.border}}>
      <div style={{display:'flex',justifyContent:'space-between',gap:'8px',flexWrap:'wrap',marginBottom:'8px'}}>
        <div>
          <b style={{color:C.text,fontSize:'12px'}}>Сверка изменений с новой сметой</b>
          <p style={{color:C.textSec,fontSize:'11px',margin:'2px 0 0'}}>{(baseEstimate?.name||'База')+' → '+(nextEstimate?.name||'Новая смета')}</p>
        </div>
        <span style={badge(rows.length?C.warning:C.success,rows.length?C.warningLight:C.successLight,rows.length?C.warningBorder:C.successBorder)}>{rows.length?rows.length+' на проверке':'закрыто'}</span>
      </div>
      {rows.length===0?<p style={{color:C.success,fontSize:'12px',margin:0}}>Спорных изменений не осталось.</p>:(
        <div style={{overflowX:'auto'}}>
          <table style={{...tbl,fontSize:'12px'}}>
            <thead><tr><th style={tblH}>Изменение</th><th style={tblH}>Кандидат в новой смете</th><th style={tblH}>Причина</th><th style={tblH}>Увер.</th><th style={tblH}></th></tr></thead>
            <tbody>{rows.map(decision=>{
              const change = decision.change||{};
              const candidate = decision.candidate||null;
              return (<tr key={change.id}>
                <td style={{...tblC,minWidth:'220px'}}>
                  <b style={{display:'block',color:C.text,fontSize:'12px'}}>{change.estimateItemName||change.description||'Изменение'}</b>
                  <span style={{color:C.textSec,fontSize:'11px'}}>{(change.changeType||'')+' · '+fmtMeasure(change.deltaQuantity||change.quantity,change.unit)}</span>
                </td>
                <td style={{...tblC,minWidth:'240px'}}>
                  {candidate?<><b style={{display:'block',color:C.text,fontSize:'12px'}}>{candidate.name}</b><span style={{color:C.textSec,fontSize:'11px'}}>{(candidate.section||'')+' · '+fmtMeasure(candidate.qty,candidate.unit)+' · '+Math.round(candidate.sum||0).toLocaleString('ru-RU')+' ₽'}</span></>:<span style={{color:C.textMuted}}>Не найден</span>}
                </td>
                <td style={{...tblC,color:decision.autoInclude?C.success:C.warning,fontWeight:'600',minWidth:'180px'}}>{decision.reason||'Нужно проверить'}</td>
                <td style={tblC}>{scoreLabel(decision.score)}</td>
                <td style={tblC}>
                  <div style={{display:'flex',gap:'5px',justifyContent:'flex-end',flexWrap:'wrap'}}>
                    {candidate&&<button onClick={()=>onConfirmIncluded(task,decision)} style={{...btnGr,padding:'4px 8px',fontSize:'11px'}}><Check size={11}/>Включить</button>}
                    <button onClick={()=>onOpenTask(task)} style={{...btnB,padding:'4px 8px',fontSize:'11px'}}><Eye size={11}/>Открыть</button>
                  </div>
                </td>
              </tr>);
            })}</tbody>
          </table>
        </div>
      )}
    </div>
  );
}
