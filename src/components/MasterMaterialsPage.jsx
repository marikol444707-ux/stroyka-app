import React from 'react';
import { Check } from 'lucide-react';

export default function MasterMaterialsPage({
  C,
  badge,
  btnG,
  btnGr,
  card,
  confirmMaterialReceipt,
  fmtMeasure,
  myMaterialBalances,
  myPendingMaterialTransfers,
  myTools,
  returnMaterialToProject,
  toNum,
}) {
  return (
    <div>
      <h3 style={{color:C.text,marginBottom:'14px',fontSize:'18px',fontWeight:'700'}}>📦 Мой склад</h3>
      <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(140px,1fr))',gap:'10px',marginBottom:'14px'}}>
        <div style={{...card,padding:'12px',backgroundColor:C.successLight,border:'1.5px solid '+C.successBorder}}>
          <p style={{color:C.success,fontSize:'11px',margin:'0 0 4px',fontWeight:'600'}}>📦 Материалов</p>
          <b style={{color:C.success,fontSize:'18px'}}>{myMaterialBalances.length}</b>
        </div>
        <div style={{...card,padding:'12px',backgroundColor:C.warningLight,border:'1.5px solid '+C.warningBorder}}>
          <p style={{color:C.warning,fontSize:'11px',margin:'0 0 4px',fontWeight:'600'}}>⏳ Не подтверждено</p>
          <b style={{color:C.warning,fontSize:'18px'}}>{myPendingMaterialTransfers.length}</b>
        </div>
        <div style={{...card,padding:'12px',backgroundColor:C.accentLight,border:'1.5px solid '+(C.accentBorder||C.border)}}>
          <p style={{color:C.accent,fontSize:'11px',margin:'0 0 4px',fontWeight:'600'}}>🔧 Инструментов</p>
          <b style={{color:C.accent,fontSize:'18px'}}>{myTools.length}</b>
        </div>
      </div>

      {myMaterialBalances.length>0 && (
        <div style={{...card,padding:'12px',marginBottom:'14px',backgroundColor:C.infoLight,border:'1.5px solid '+C.infoBorder}}>
          <p style={{color:C.text,fontSize:'12px',margin:0}}>
            💡 <b>Как списать материал:</b> перейди во вкладку «Работы», в форме «Добавить работы» укажи использованные материалы — спишется автоматически.
          </p>
        </div>
      )}

      <div style={{marginBottom:'18px'}}>
        <b style={{color:C.text,fontSize:'14px',display:'block',marginBottom:'10px'}}>📦 Материалы, выданные мне</b>
        {myMaterialBalances.length===0 && (
          <div style={{...card,padding:'20px',textAlign:'center',color:C.textMuted,fontSize:'13px'}}>
            Материалы пока не передавались.<br/>Заявку на материал можно сделать во вкладке «🛒 Снабжение».
          </div>
        )}
        {myMaterialBalances.map(b=>{
          const remaining = toNum(b.quantity);
          const pct = b.received>0 ? Math.min(100, Math.round((b.used/b.received)*100)) : 0;
          const remColor = remaining<=0 && b.received>0 ? C.danger : remaining<b.received*0.2 ? C.warning : C.success;
          return (
            <div key={b.id||b.key} style={{...card,padding:'14px',marginBottom:'10px',borderLeft:'4px solid '+remColor}}>
              <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'10px',flexWrap:'wrap',marginBottom:'10px'}}>
                <div style={{flex:'1 1 200px'}}>
                  <b style={{color:C.text,fontSize:'14px'}}>{b.name}</b>
                  <p style={{color:C.textSec,margin:'3px 0',fontSize:'12px'}}>
                    {'🏗 '+(b.project||'—')+(b.workPackage?' · 📁 '+b.workPackage:'')+((b.transfers||[]).length>1?' · '+b.transfers.length+' подписанных передач':'')}
                  </p>
                </div>
              </div>
              <div style={{display:'grid',gridTemplateColumns:'repeat(3,1fr)',gap:'6px',marginBottom:'8px'}}>
                <div style={{padding:'8px',backgroundColor:C.bg,borderRadius:'6px',border:'1px solid '+C.border}}>
                  <p style={{color:C.textSec,fontSize:'10px',margin:'0 0 2px'}}>Получено</p>
                  <b style={{color:C.text,fontSize:'13px'}}>{fmtMeasure(b.received,b.unit)}</b>
                  {b.pending>0&&<p style={{color:C.warning,fontSize:'10px',margin:'2px 0 0'}}>+ ждёт подписи {fmtMeasure(b.pending,b.unit)}</p>}
                </div>
                <div style={{padding:'8px',backgroundColor:C.warningLight,borderRadius:'6px',border:'1px solid '+C.warningBorder}}>
                  <p style={{color:C.warning,fontSize:'10px',margin:'0 0 2px'}}>Списано</p>
                  <b style={{color:C.warning,fontSize:'13px'}}>{fmtMeasure(b.used,b.unit)}</b>
                  {b.returned>0&&<p style={{color:C.success,fontSize:'10px',margin:'2px 0 0'}}>возврат: {fmtMeasure(b.returned,b.unit)}</p>}
                </div>
                <div style={{padding:'8px',backgroundColor:remColor===C.danger?C.dangerLight:remColor===C.warning?C.warningLight:C.successLight,borderRadius:'6px',border:'1px solid '+(remColor===C.danger?C.dangerBorder:remColor===C.warning?C.warningBorder:C.successBorder)}}>
                  <p style={{color:remColor,fontSize:'10px',margin:'0 0 2px'}}>Остаток у меня</p>
                  <b style={{color:remColor,fontSize:'13px'}}>{fmtMeasure(remaining,b.unit)}</b>
                </div>
              </div>
              <div style={{height:'6px',backgroundColor:C.bg,borderRadius:'4px',overflow:'hidden',marginBottom:'8px'}}>
                <div style={{width:pct+'%',height:'100%',backgroundColor:pct>=100?C.danger:pct>=80?C.warning:C.success}}/>
              </div>
              {remaining>0 && (
                <button onClick={()=>returnMaterialToProject(b)} style={{...btnG,padding:'6px 10px',fontSize:'12px',marginBottom:'8px'}}>
                  Вернуть остаток на склад
                </button>
              )}
              {(b.pendingTransfers||[]).length>0 && (
                <div style={{padding:'8px',backgroundColor:C.warningLight,border:'1px solid '+C.warningBorder,borderRadius:'6px',marginTop:'6px'}}>
                  <p style={{color:C.warning,fontSize:'11px',margin:'0 0 6px',fontWeight:'600'}}>⏳ Не подтверждено получение ({b.pendingTransfers.length} передач):</p>
                  {b.pendingTransfers.map(t=>(
                    <div key={t.id} style={{display:'flex',justifyContent:'space-between',alignItems:'center',padding:'4px 0'}}>
                      <span style={{fontSize:'12px',color:C.text}}>
                        {fmtMeasure(t.quantity,t.unit)}
                        {t.workPackage ? <span style={{color:C.textSec}}> · 📁 {t.workPackage}</span> : null}
                        {t.fromLocation ? <span style={{color:C.textSec}}> · {t.fromLocation}</span> : null}
                      </span>
                      <button onClick={()=>confirmMaterialReceipt(t.id)} style={{...btnGr,padding:'3px 8px',fontSize:'11px'}}><Check size={11}/>Подтвердить</button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div>
        <b style={{color:C.text,fontSize:'14px',display:'block',marginBottom:'10px'}}>🔧 Инструменты за мной</b>
        {myTools.length===0 && <div style={{...card,padding:'20px',textAlign:'center',color:C.textMuted,fontSize:'13px'}}>Инструментов нет</div>}
        {myTools.map(t=>(
          <div key={t.id} style={{...card,padding:'14px',marginBottom:'8px',borderLeft:'4px solid '+C.purple}}>
            <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'10px',flexWrap:'wrap'}}>
              <div>
                <b style={{color:C.text,fontSize:'14px'}}>{t.name}</b>
                <p style={{color:C.textSec,margin:'3px 0',fontSize:'12px'}}>{(t.inventoryNumber?'№ '+t.inventoryNumber:'')+(t.project?' · '+t.project:'')}</p>
                {t.issueType==='В счёт зарплаты' && <span style={badge(C.danger,C.dangerLight,C.dangerBorder)}>{'Удержание: '+(t.cost||0).toLocaleString()+' ₽'}</span>}
              </div>
              <span style={badge(C.accent,C.accentLight,C.accentBorder||C.border)}>{t.status}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
