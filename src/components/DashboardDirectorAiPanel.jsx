import React from 'react';
import { Bot } from 'lucide-react';

export default function DashboardDirectorAiPanel({
  isLeadership,
  directorSkillCards,
  dailyReportDate,
  setDailyReportDate,
  canUseDirectorAgent,
  directorAgentLoading,
  askDirectorAgent,
  directorAgentQuestion,
  setDirectorAgentQuestion,
  isMobile,
  directorAgentAnswer,
  directorAgentError,
  directorAgentSteps,
}) {
  if (!isLeadership()) return null;

  return (
    <div style={{marginBottom:'20px'}}>
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:'10px',flexWrap:'wrap',marginBottom:'12px'}}>
        <div>
          <h2 style={{margin:0,fontSize:'18px',color:'#f8fafc',display:'flex',alignItems:'center',gap:'8px'}}><Bot size={18} color='#fdba74'/>ИИ-контроль директора</h2>
          <p style={{color:'#94a3b8',fontSize:'12px',margin:'3px 0 0'}}>Автопроверки по данным программы</p>
        </div>
        <input type='date' value={dailyReportDate} onChange={e=>setDailyReportDate(e.target.value)} style={{height:'34px',padding:'6px 8px',borderRadius:'8px',border:'1px solid rgba(148,163,184,.32)',background:'rgba(15,23,42,.72)',color:'#f8fafc',fontSize:'12px',boxSizing:'border-box'}}/>
      </div>
      <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(190px,1fr))',gap:'12px'}}>
        {directorSkillCards.map((k,i)=>(
          <button key={i} onClick={k.onClick} style={{textAlign:'left',padding:'14px',borderRadius:'16px',background:k.bg,border:'1px solid '+k.border,cursor:'pointer',transition:'transform 0.15s, background 0.15s',color:'#f8fafc',display:'flex',flexDirection:'column',gap:'10px',minHeight:'116px'}} onMouseEnter={e=>{e.currentTarget.style.transform='translateY(-2px)';e.currentTarget.style.background='rgba(30,41,59,.75)';}} onMouseLeave={e=>{e.currentTarget.style.transform='';e.currentTarget.style.background=k.bg;}}>
            <span style={{width:'34px',height:'34px',borderRadius:'12px',display:'inline-flex',alignItems:'center',justifyContent:'center',background:'rgba(15,23,42,.55)',border:'1px solid '+k.border,color:k.color}}>{k.icon}</span>
            <span style={{display:'block'}}>
              <b style={{display:'block',fontSize:'13px',color:'#f8fafc'}}>{k.label}</b>
              <span style={{display:'block',marginTop:'3px',color:'#94a3b8',fontSize:'11px'}}>{k.sub}</span>
            </span>
            <span style={{marginTop:'auto',fontSize:'12px',fontWeight:'800',color:k.color}}>{k.metric}</span>
          </button>
        ))}
      </div>
      {canUseDirectorAgent()&&(
        <div style={{marginTop:'12px',padding:'16px',borderRadius:'18px',background:'rgba(15,23,42,.82)',border:'1px solid rgba(56,189,248,.28)',boxShadow:'0 18px 60px rgba(8,47,73,.22)'}}>
          <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'12px',flexWrap:'wrap',marginBottom:'12px'}}>
            <div>
              <h3 style={{margin:0,fontSize:'16px',color:'#f8fafc',display:'flex',alignItems:'center',gap:'8px'}}><Bot size={17} color='#38bdf8'/>ИИ-помощник директора</h3>
              <p style={{margin:'4px 0 0',fontSize:'12px',color:'#94a3b8'}}>Читает объекты, склад, снабжение, сметы, финансы и задачи ИИ-контроля. Данные не меняет.</p>
            </div>
            <span style={{fontSize:'11px',fontWeight:'800',color:'#7dd3fc',background:'rgba(14,165,233,.12)',border:'1px solid rgba(14,165,233,.32)',borderRadius:'999px',padding:'5px 9px'}}>только директор</span>
          </div>
          <div style={{display:'flex',gap:'8px',flexWrap:'wrap',marginBottom:'10px'}}>
            {['Что сейчас критично по объектам?','Где есть риски по снабжению?','Какие сметы требуют внимания?','Где зависли задачи ИИ-контроля?'].map(q=>(
              <button key={q} onClick={()=>askDirectorAgent(q)} disabled={directorAgentLoading} style={{padding:'7px 10px',borderRadius:'999px',border:'1px solid rgba(148,163,184,.22)',background:'rgba(30,41,59,.72)',color:'#cbd5e1',fontSize:'11px',cursor:directorAgentLoading?'not-allowed':'pointer',opacity:directorAgentLoading?0.65:1}}>{q}</button>
            ))}
          </div>
          <div style={{display:'grid',gridTemplateColumns:isMobile?'1fr':'1fr auto',gap:'10px',alignItems:'stretch'}}>
            <textarea value={directorAgentQuestion} onChange={e=>setDirectorAgentQuestion(e.target.value)} placeholder="Спросите по объектам, складу, деньгам, сметам или задачам..." rows={isMobile?3:2} disabled={directorAgentLoading} style={{width:'100%',resize:'vertical',minHeight:'48px',padding:'11px 12px',borderRadius:'12px',border:'1px solid rgba(148,163,184,.28)',background:'rgba(2,6,23,.62)',color:'#f8fafc',outline:'none',fontSize:'13px',lineHeight:1.45,boxSizing:'border-box'}}/>
            <button onClick={()=>askDirectorAgent()} disabled={directorAgentLoading||!directorAgentQuestion.trim()} style={{padding:'10px 16px',borderRadius:'12px',border:'none',background:(directorAgentLoading||!directorAgentQuestion.trim())?'#334155':'linear-gradient(135deg,#0ea5e9,#0284c7)',color:'#f8fafc',fontWeight:'800',fontSize:'13px',cursor:(directorAgentLoading||!directorAgentQuestion.trim())?'not-allowed':'pointer',minWidth:isMobile?'100%':'120px'}}>{directorAgentLoading?'Думаю...':'Спросить'}</button>
          </div>
          {(directorAgentAnswer||directorAgentError||directorAgentLoading)&&(
            <div style={{marginTop:'12px',padding:'13px 14px',borderRadius:'14px',background:directorAgentError?'rgba(239,68,68,.10)':'rgba(30,41,59,.62)',border:'1px solid '+(directorAgentError?'rgba(239,68,68,.26)':'rgba(148,163,184,.18)'),color:directorAgentError?'#fca5a5':'#e2e8f0',fontSize:'13px',lineHeight:1.55,whiteSpace:'pre-wrap'}}>
              {directorAgentLoading?'Запрашиваю данные и собираю ответ...':(directorAgentError||directorAgentAnswer)}
            </div>
          )}
          {directorAgentSteps.length>0&&(
            <div style={{display:'flex',gap:'6px',flexWrap:'wrap',marginTop:'10px'}}>
              {directorAgentSteps.map((s,i)=><span key={i} style={{fontSize:'10px',fontWeight:'800',color:'#bae6fd',background:'rgba(14,165,233,.12)',border:'1px solid rgba(14,165,233,.24)',borderRadius:'999px',padding:'4px 8px'}}>{s.tool}</span>)}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
