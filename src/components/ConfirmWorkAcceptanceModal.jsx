import React from 'react';
import { Check } from 'lucide-react';

export default function ConfirmWorkAcceptanceModal({
  confirmingEntry,
  confirmAcceptedQty,
  setConfirmAcceptedQty,
  confirmComment,
  setConfirmComment,
  setConfirmingEntry,
  confirmJ,
  normalizeMeasure,
  toNum,
  C,
  card,
  inp,
  btnO,
  btnG,
}) {
  if (!confirmingEntry) return null;

  const e = confirmingEntry;
  const plan = toNum(e.quantity || 0);
  const accepted = toNum(confirmAcceptedQty || 0);
  const ppu = Number(e._ppu || e.pricePerUnit || 0) || (plan > 0 ? Number(e.total || 0) / plan : 0);
  const newTotal = Math.round(accepted * ppu);
  const diff = plan - accepted;
  const norm = normalizeMeasure(plan, e.unit);
  const planNorm = norm.qty;
  const unitNorm = norm.unit;
  const factor = norm.factor;
  const acceptedNorm = accepted * factor;
  const ppuNorm = factor > 1 ? (ppu / factor) : ppu;
  const diffNorm = diff * factor;

  return (
    <div style={{position:'fixed',top:0,left:0,right:0,bottom:0,backgroundColor:'rgba(0,0,0,0.55)',display:'flex',justifyContent:'center',alignItems:'center',zIndex:1500,padding:'20px'}}>
      <div style={{...card,padding:'24px',width:'min(480px,100%)',maxHeight:'90vh',overflowY:'auto'}}>
        <h3 style={{color:C.text,marginBottom:'8px',fontWeight:'700'}}>✅ Принять работу мастера</h3>
        <p style={{color:C.textSec,fontSize:'12px',margin:'0 0 14px'}}>{(e.masterName||e.master_name||'—')+' · '+e.project}</p>
        <div style={{padding:'10px 12px',backgroundColor:C.bg,borderRadius:'8px',marginBottom:'12px'}}>
          <b style={{color:C.text,fontSize:'13px',display:'block'}}>{e.description}</b>
          <p style={{color:C.textSec,fontSize:'11px',margin:'4px 0 0'}}>Мастер заявил: <b style={{color:C.text}}>{planNorm.toLocaleString('ru-RU',{maximumFractionDigits:3})+' '+unitNorm+' × '+Math.round(ppuNorm).toLocaleString('ru-RU')+' ₽ = '+Math.round(plan*ppu).toLocaleString('ru-RU')+' ₽'}</b></p>
          {factor>1&&<p style={{color:C.textMuted,fontSize:'10px',margin:'2px 0 0'}}>в смете единица: «{e.unit}» (коэф. ×{factor})</p>}
        </div>
        <label style={{display:'block',color:C.textSec,fontSize:'12px',marginBottom:'4px'}}>Фактически принято ({unitNorm||'шт'})</label>
        <input type='number' step='any' inputMode='decimal' value={factor>1?String(acceptedNorm):confirmAcceptedQty} onChange={ev=>{const v=toNum(ev.target.value);setConfirmAcceptedQty(String(factor>1?(v/factor):v));}} max={planNorm} min={0} style={{...inp,fontSize:'18px',fontWeight:'700'}}/>
        {diff>0&&accepted>=0&&<p style={{color:C.warning,fontSize:'12px',margin:'-4px 0 10px'}}>⚠️ Недоделано: <b>{diffNorm.toLocaleString('ru-RU',{maximumFractionDigits:3})+' '+unitNorm+' = '+Math.round(diff*ppu).toLocaleString('ru-RU')+' ₽'}</b> — мастеру нужно доделать</p>}
        {diff===0&&<p style={{color:C.success,fontSize:'12px',margin:'-4px 0 10px'}}>✅ Принято полностью</p>}
        {diff<0&&<p style={{color:C.danger,fontSize:'12px',margin:'-4px 0 10px'}}>Нельзя принять больше чем заявлено</p>}
        <div style={{padding:'10px 12px',backgroundColor:C.successLight,borderRadius:'8px',marginBottom:'12px',border:'1.5px solid '+C.successBorder}}>
          <p style={{color:C.text,fontSize:'12px',margin:0}}>К оплате мастеру: <b style={{color:C.success,fontSize:'16px'}}>{newTotal.toLocaleString('ru-RU')+' ₽'}</b></p>
        </div>
        <textarea placeholder='Комментарий (необязательно)' value={confirmComment} onChange={ev=>setConfirmComment(ev.target.value)} style={{...inp,height:'60px',resize:'vertical',marginBottom:'12px'}}/>
        <div style={{display:'flex',gap:'8px'}}>
          <button onClick={()=>confirmJ(e,accepted,confirmComment)} disabled={diff<0||accepted<=0} style={{...btnO,opacity:(diff<0||accepted<=0)?0.5:1,flex:1,justifyContent:'center'}}><Check size={14}/>Принять и подтвердить</button>
          <button onClick={()=>{setConfirmingEntry(null);setConfirmAcceptedQty('');setConfirmComment('');}} style={btnG}>Отмена</button>
        </div>
        <p style={{color:C.textMuted,fontSize:'11px',margin:'10px 0 0',lineHeight:1.4}}>После подтверждения работа уйдёт в КС-2 и в зарплатные начисления мастера. Списание материалов произойдёт автоматически.</p>
      </div>
    </div>
  );
}
