import React, { useRef, useState } from 'react';
import { Calculator, CheckCircle2, Clock3, ShieldCheck, X } from 'lucide-react';
import { C, btnB, btnG, btnGr, card } from '../constants/uiTheme';
import { budgetAdjustmentErrorMessage } from '../features/estimates/projectBudgetAdjustmentActions';
import ProjectBudgetAdjustmentHistory from './ProjectBudgetAdjustmentHistory';

const formatExactMoney = (value, {signed = false} = {}) => {
  const text = String(value || '0.00');
  const negative = text.startsWith('-');
  const [whole, decimal = '00'] = (negative ? text.slice(1) : text).split('.');
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, '\u00a0');
  const sign = negative ? '−' : (signed && text !== '0.00' ? '+' : '');
  return `${sign}${grouped},${decimal} ₽`;
};

const formatDate = (value) => {
  const date = new Date(value);
  return Number.isFinite(date.getTime())
    ? new Intl.DateTimeFormat('ru-RU',{dateStyle:'short',timeStyle:'short'}).format(date)
    : 'Дата недоступна';
};

export default function ProjectBudgetAdjustmentPanel({
  approvedReconciliations = [],
  canManage,
  onApplied,
  onApprove,
  onLoadHistory,
  onLoadPreview,
  project,
}) {
  const [preview, setPreview] = useState(null);
  const [loadingId, setLoadingId] = useState(null);
  const [approving, setApproving] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyLoaded, setHistoryLoaded] = useState(false);
  const [history, setHistory] = useState([]);
  const [historyCursor, setHistoryCursor] = useState(null);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState('');
  const approvalInFlightRef = useRef(false);

  if (!canManage) return null;
  const busy = Boolean(loadingId)||approving;

  const loadHistory = async (beforeId = null) => {
    setHistoryLoading(true);
    setHistoryError('');
    try {
      const options = beforeId ? {limit:25,beforeId} : {limit:25};
      const page = await onLoadHistory(project.id, options);
      setHistory(current => {
        const rows = beforeId ? [...current,...page.items] : page.items;
        return [...new Map(rows.map(item=>[item.id,item])).values()];
      });
      setHistoryCursor(page.nextBeforeId);
      setHistoryLoaded(true);
    } catch (failure) {
      setHistoryError(budgetAdjustmentErrorMessage(failure));
    } finally {
      setHistoryLoading(false);
    }
  };

  const requestPreview = async (reconciliationId) => {
    setLoadingId(reconciliationId);
    setPreview(null);
    setError('');
    setNotice('');
    try {
      const result = await onLoadPreview(reconciliationId);
      if (!result.readyForApproval) {
        const blocker = {code:result.blockers[0] || 'budget_adjustment_request_failed'};
        setError(budgetAdjustmentErrorMessage(blocker));
        return;
      }
      setPreview(result);
    } catch (failure) {
      setError(budgetAdjustmentErrorMessage(failure));
    } finally {
      setLoadingId(null);
    }
  };

  const approve = async () => {
    if (!preview || approvalInFlightRef.current) return;
    approvalInFlightRef.current = true;
    setApproving(true);
    setError('');
    setNotice('');
    try {
      const result = await onApprove(preview.reconciliationId, preview.planSha256);
      setPreview(null);
      setNotice(result.idempotent?'Изменение уже было применено. История обновлена.':'Бюджет изменён. Событие добавлено в историю.');
      if (onApplied) Promise.resolve().then(()=>onApplied(result)).catch(()=>{});
      if (historyOpen) await loadHistory();
    } catch (failure) {
      setError(budgetAdjustmentErrorMessage(failure));
      setPreview(null);
    } finally {
      approvalInFlightRef.current = false;
      setApproving(false);
    }
  };

  const toggleHistory = () => {
    const next = !historyOpen;
    setHistoryOpen(next);
    if (next&&!historyLoaded&&!historyLoading) loadHistory();
  };

  return (
    <section aria-label="Изменение бюджета" aria-busy={busy} style={{...card,padding:'14px',marginBottom:'14px',borderColor:C.infoBorder}}>
      <div style={{display:'flex',justifyContent:'space-between',gap:'10px',alignItems:'flex-start',flexWrap:'wrap'}}>
        <div>
          <b style={{color:C.text,fontSize:'14px',display:'flex',alignItems:'center',gap:'6px'}}><ShieldCheck size={16}/>Изменение бюджета</b>
          <p style={{color:C.textSec,fontSize:'12px',margin:'4px 0 0'}}>Отдельное подтверждение по утверждённой сверке. Сметы и финансовая история не изменяются.</p>
        </div>
        <button onClick={toggleHistory} aria-expanded={historyOpen} style={{...btnG,padding:'6px 10px',fontSize:'12px'}}>
          <Clock3 size={13}/>{historyOpen?'Скрыть историю':'Показать историю'}
        </button>
      </div>
      {approvedReconciliations.length===0?(
        <p style={{color:C.textMuted,fontSize:'12px',margin:'12px 0 0'}}>Для расчёта нужна утверждённая сверка смет.</p>
      ):(
        <div style={{display:'flex',gap:'7px',flexWrap:'wrap',marginTop:'12px'}}>
          {approvedReconciliations.map(rec=>(
            <button key={rec.id} disabled={busy} onClick={()=>requestPreview(rec.id)} style={{...btnB,padding:'6px 10px',fontSize:'12px'}}>
              <Calculator size={13}/>{loadingId===rec.id?'Расчёт…':`Рассчитать по сверке № ${rec.id}`}
            </button>
          ))}
        </div>
      )}
      {error&&<p role="alert" style={{color:C.danger,backgroundColor:C.dangerLight,border:'1px solid '+C.dangerBorder,borderRadius:'8px',padding:'9px',fontSize:'12px',margin:'10px 0 0'}}>{error}</p>}
      {notice&&<p role="status" style={{color:C.success,backgroundColor:C.successLight,border:'1px solid '+C.successBorder,borderRadius:'8px',padding:'9px',fontSize:'12px',margin:'10px 0 0'}}>{notice}</p>}
      {preview&&(
        <div aria-label="Подтверждение изменения бюджета" style={{backgroundColor:C.bg,marginTop:'12px',padding:'12px',borderRadius:'10px',border:'1px solid '+C.border}}>
          <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(145px,1fr))',gap:'8px'}}>
            {[['Бюджет до',preview.projectBudgetBefore],['Изменение',preview.adjustmentAmount],['Бюджет после',preview.projectBudgetAfter]].map(([label,value],index)=>(
              <div key={label} style={{backgroundColor:C.bgWhite,border:'1px solid '+C.border,borderRadius:'8px',padding:'9px'}}>
                <span style={{color:C.textMuted,fontSize:'11px',display:'block'}}>{label}</span>
                <b style={{color:index===1?(value.startsWith('-')?C.danger:C.success):C.text,fontSize:'14px'}}>{formatExactMoney(value,{signed:index===1})}</b>
              </div>
            ))}
          </div>
          <p style={{color:C.textSec,fontSize:'11px',margin:'9px 0'}}>Будет записано одно неизменяемое событие по сверке № {preview.reconciliationId}. Отменить его редактированием истории нельзя.</p>
          <div style={{display:'flex',gap:'7px',flexWrap:'wrap'}}>
            <button disabled={approving} onClick={approve} style={{...btnGr,padding:'7px 11px',fontSize:'12px'}}><CheckCircle2 size={14}/>{approving?'Применение…':'Подтвердить изменение бюджета'}</button>
            <button disabled={approving} onClick={()=>setPreview(null)} style={{...btnG,padding:'7px 11px',fontSize:'12px'}}><X size={14}/>Отмена</button>
          </div>
        </div>
      )}
      {historyOpen&&<ProjectBudgetAdjustmentHistory error={historyError} formatDate={formatDate} formatMoney={formatExactMoney} items={history} loading={historyLoading} nextBeforeId={historyCursor} onLoadMore={()=>loadHistory(historyCursor)}/>} 
    </section>
  );
}
