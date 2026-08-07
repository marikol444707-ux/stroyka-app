import React from 'react';
import { ChevronDown, Clock3 } from 'lucide-react';
import { C, btnG, card } from '../constants/uiTheme';

export default function ProjectBudgetAdjustmentHistory({
  error,
  formatDate,
  formatMoney,
  items,
  loading,
  nextBeforeId,
  onLoadMore,
}) {
  return (
    <div style={{marginTop:'12px'}}>
      {loading&&items.length===0&&<p style={{color:C.textSec,fontSize:'12px',margin:'8px 0'}}>Загружаем историю…</p>}
      {error&&<p role="alert" style={{color:C.danger,fontSize:'12px',margin:'8px 0'}}>{error}</p>}
      {!loading&&!error&&items.length===0&&(
        <p style={{color:C.textMuted,fontSize:'12px',margin:'8px 0'}}>Подтверждённых изменений бюджета пока нет.</p>
      )}
      {items.length>0&&(
        <div style={{display:'grid',gap:'8px'}}>
          {items.map(item=>(
            <article key={item.id} style={{...card,padding:'11px',backgroundColor:C.bg}}>
              <div style={{display:'flex',justifyContent:'space-between',gap:'10px',flexWrap:'wrap'}}>
                <div>
                  <b style={{color:C.text,fontSize:'12px'}}>Сверка № {item.reconciliationId}</b>
                  <p style={{color:C.textSec,fontSize:'11px',margin:'3px 0 0'}}>{item.approvedByName+' · '+item.approvedByRole}</p>
                </div>
                <b style={{color:item.adjustmentAmount.startsWith('-')?C.danger:C.success,fontSize:'13px'}}>{formatMoney(item.adjustmentAmount,{signed:true})}</b>
              </div>
              <p style={{color:C.textMuted,fontSize:'11px',margin:'7px 0 0',display:'flex',alignItems:'center',gap:'5px'}}>
                <Clock3 size={12}/>{formatDate(item.approvedAt)} · {formatMoney(item.projectBudgetBefore)} → {formatMoney(item.projectBudgetAfter)}
              </p>
            </article>
          ))}
        </div>
      )}
      {nextBeforeId&&(
        <button disabled={loading} onClick={onLoadMore} style={{...btnG,marginTop:'9px',fontSize:'12px'}}>
          <ChevronDown size={13}/>{loading?'Загрузка…':'Показать ещё'}
        </button>
      )}
    </div>
  );
}
