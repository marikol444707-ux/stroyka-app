import React from 'react';
import { FileText } from 'lucide-react';

export default function DashboardProductionSummaryPanel({
  workJournal,
  workDocDate,
  normalizeDocDate,
  dailyReportDate,
  setDailyReportDate,
  user,
  showPreview,
  buildDailyObjectReportContent,
  setActivePage,
  setAccountingTab,
}) {
  const safeWorkJournal = Array.isArray(workJournal) ? workJournal : [];
  const getWorkDocDate = typeof workDocDate === 'function' ? workDocDate : () => '';
  const normalizeDate = typeof normalizeDocDate === 'function' ? normalizeDocDate : (value) => String(value || '').split('T')[0] || '';
  const changeDailyReportDate = typeof setDailyReportDate === 'function' ? setDailyReportDate : () => {};
  const previewDocument = typeof showPreview === 'function' ? showPreview : () => {};
  const buildDailyReport = typeof buildDailyObjectReportContent === 'function' ? buildDailyObjectReportContent : () => '';
  const goToPage = typeof setActivePage === 'function' ? setActivePage : () => {};
  const changeAccountingTab = typeof setAccountingTab === 'function' ? setAccountingTab : () => {};
  const today = new Date().toISOString().split('T')[0];
  const yest = new Date(Date.now()-24*3600*1000).toISOString().split('T')[0];
  const wj = safeWorkJournal.filter(w=>w.status==='Подтверждено');
  const todayWorks = wj.filter(w=>getWorkDocDate(w)===today);
  const yestWorks = wj.filter(w=>getWorkDocDate(w)===yest);
  const reportDate = normalizeDate(dailyReportDate)||today;
  const reportWorks = safeWorkJournal.filter(w=>getWorkDocDate(w)===reportDate);
  const reportProjects = new Set(reportWorks.map(w=>w.project).filter(Boolean)).size;
  const sumToday = todayWorks.reduce((s,w)=>s+Number(w.total||0),0);
  const sumYest = yestWorks.reduce((s,w)=>s+Number(w.total||0),0);
  const byMaster = {};
  todayWorks.forEach(w=>{const n=w.masterName||w.master_name||'—';byMaster[n]=(byMaster[n]||0)+Number(w.total||0);});
  const masters = Object.entries(byMaster).sort((a,b)=>b[1]-a[1]).slice(0,5);

  return (
    <div onClick={()=>{goToPage('accounting');changeAccountingTab('acts');}} style={{background:'rgba(17,24,39,.88)',border:'1px solid rgba(148,163,184,.18)',borderRadius:'22px',padding:'20px',backdropFilter:'blur(24px)',cursor:'pointer'}}>
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'12px',marginBottom:'12px',flexWrap:'wrap'}}>
        <div>
          <h2 style={{margin:'0 0 4px',fontSize:'17px',color:'#f8fafc'}}>👷 Производство работ <span style={{fontSize:'12px',color:'#94a3b8',fontWeight:'400'}}>→ Акты</span></h2>
          <p style={{margin:0,color:'#94a3b8',fontSize:'11px'}}>{'Отчёт за день: '+reportWorks.length+' работ · '+reportProjects+' объектов'}</p>
        </div>
        {user&&['директор','зам_директора'].includes(user.role)&&(<div onClick={e=>e.stopPropagation()} style={{display:'flex',gap:'6px',alignItems:'center',flexWrap:'wrap',justifyContent:'flex-end'}}>
          <input type='date' value={dailyReportDate || ''} onChange={e=>changeDailyReportDate(e.target.value)} style={{height:'34px',padding:'6px 8px',borderRadius:'8px',border:'1px solid rgba(148,163,184,.32)',background:'rgba(15,23,42,.72)',color:'#f8fafc',fontSize:'12px',boxSizing:'border-box'}}/>
          <button onClick={e=>{e.stopPropagation();previewDocument(buildDailyReport(reportDate),'Ежедневный отчет — '+new Date(reportDate+'T00:00:00').toLocaleDateString('ru-RU'));}} style={{height:'34px',padding:'7px 10px',borderRadius:'8px',border:'1px solid rgba(34,197,94,.34)',background:'rgba(34,197,94,.14)',color:'#86efac',fontWeight:'700',fontSize:'12px',cursor:'pointer',display:'inline-flex',alignItems:'center',gap:'5px'}}><FileText size={13}/>Ежедневный отчёт</button>
        </div>)}
      </div>
      <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'10px',marginBottom:'14px'}}>
        <div style={{padding:'12px',borderRadius:'14px',background:'rgba(34,197,94,.12)',border:'1px solid rgba(34,197,94,.28)'}}>
          <p style={{color:'#86efac',fontSize:'11px',margin:'0 0 4px'}}>Сегодня</p>
          <b style={{color:'#86efac',fontSize:'17px',display:'block'}}>{sumToday>=1000000?(sumToday/1000000).toFixed(1)+' млн':Math.round(sumToday/1000)+' тыс'} ₽</b>
          <span style={{color:'#94a3b8',fontSize:'10px'}}>{todayWorks.length+' работ'}</span>
        </div>
        <div style={{padding:'12px',borderRadius:'14px',background:'rgba(59,130,246,.12)',border:'1px solid rgba(59,130,246,.28)'}}>
          <p style={{color:'#93c5fd',fontSize:'11px',margin:'0 0 4px'}}>Вчера</p>
          <b style={{color:'#93c5fd',fontSize:'17px',display:'block'}}>{sumYest>=1000000?(sumYest/1000000).toFixed(1)+' млн':Math.round(sumYest/1000)+' тыс'} ₽</b>
          <span style={{color:'#94a3b8',fontSize:'10px'}}>{yestWorks.length+' работ'}</span>
        </div>
      </div>
      {masters.length>0?(<div>
        <p style={{color:'#94a3b8',fontSize:'11px',margin:'0 0 8px'}}>По мастерам сегодня:</p>
        {masters.map(([name,sum])=>(<div key={name} style={{display:'flex',justifyContent:'space-between',padding:'6px 0',borderBottom:'1px solid rgba(148,163,184,.18)'}}><span style={{color:'#f8fafc',fontSize:'12px'}}>{name}</span><b style={{color:'#86efac',fontSize:'12px'}}>{Math.round(sum).toLocaleString('ru-RU')+' ₽'}</b></div>))}
      </div>):(<div style={{color:'#94a3b8',fontSize:'13px',padding:'8px 0',textAlign:'center'}}>Сегодня работ ещё нет</div>)}
    </div>
  );
}
