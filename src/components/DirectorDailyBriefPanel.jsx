import React from 'react';
import {AlertTriangle, CheckCircle2, ClipboardCheck, Clock3} from 'lucide-react';


const STATUS_META = {
  attention: {color: '#fbbf24', border: 'rgba(245,158,11,.34)', background: 'rgba(120,53,15,.18)'},
  info: {color: '#7dd3fc', border: 'rgba(14,165,233,.30)', background: 'rgba(8,47,73,.20)'},
  clear: {color: '#6ee7b7', border: 'rgba(16,185,129,.28)', background: 'rgba(6,78,59,.16)'},
};

const formatDate = (value) => {
  const match = String(value || '').match(/^(\d{4})-(\d{2})-(\d{2})$/);
  return match ? `${match[3]}.${match[2]}.${match[1]}` : String(value || '');
};

const formatCompletedAt = (value) => {
  if (!value) return '';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return '';
  return parsed.toLocaleTimeString('ru-RU', {hour: '2-digit', minute: '2-digit'});
};

const unitLabel = (unit) => ({
  days: 'дн.',
  requests: 'заяв.',
  tasks: 'задач',
  RUB: '₽',
}[unit] || unit || '');

const formatMetric = (item) => {
  if (item?.metricValue === undefined || item?.metricValue === null) return '';
  const value = typeof item.metricValue === 'number'
    ? item.metricValue.toLocaleString('ru-RU', {maximumFractionDigits: 3})
    : String(item.metricValue);
  return `${value}${unitLabel(item.metricUnit) ? ` ${unitLabel(item.metricUnit)}` : ''}`;
};

function BriefStateMessage({status, error}) {
  let text = '';
  if (status === 'loading') text = 'Загружаю последнюю сводку...';
  if (status === 'select-company') text = 'Выберите одну компанию, чтобы увидеть её сводку.';
  if (status === 'empty') text = 'Готовая фоновая сводка пока не сформирована.';
  if (status === 'error') text = error || 'Не удалось загрузить последнюю сводку.';
  if (!text) return null;
  return (
    <div style={{padding:'12px 0',color:status === 'error' ? '#fca5a5' : '#94a3b8',fontSize:'13px'}}>
      {text}
    </div>
  );
}

export default function DirectorDailyBriefPanel({state = {}, isMobile = false}) {
  const status = state?.status || 'idle';
  const data = state?.data || null;
  const brief = data?.brief || null;
  const summary = brief?.summary || {};
  const sections = Array.isArray(brief?.sections) ? brief.sections : [];
  const completedTime = formatCompletedAt(data?.completedAt);

  return (
    <section aria-label="Последняя фоновая сводка" style={{margin:'0 0 14px',padding:'14px 0',borderTop:'1px solid rgba(148,163,184,.18)',borderBottom:'1px solid rgba(148,163,184,.18)'}}>
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:'10px',flexWrap:'wrap'}}>
        <div style={{display:'flex',alignItems:'center',gap:'8px'}}>
          <ClipboardCheck size={17} color="#fdba74"/>
          <div>
            <h3 style={{margin:0,fontSize:'14px',color:'#f8fafc'}}>Последняя фоновая сводка</h3>
            <div style={{marginTop:'2px',fontSize:'11px',color:'#94a3b8'}}>Только чтение, данные выбранной компании</div>
          </div>
        </div>
        {status === 'ready'&&brief&&(
          <span style={{display:'inline-flex',alignItems:'center',gap:'5px',fontSize:'11px',color:'#cbd5e1'}}>
            <Clock3 size={13}/>{formatDate(brief.briefDate)}{completedTime ? ` · ${completedTime}` : ''}
          </span>
        )}
      </div>

      {status !== 'ready'||!brief
        ? <BriefStateMessage status={status} error={state?.error}/>
        : (
          <>
            <div style={{display:'flex',gap:'6px',flexWrap:'wrap',marginTop:'12px'}}>
              <span style={{fontSize:'11px',fontWeight:800,color:'#fca5a5',border:'1px solid rgba(239,68,68,.30)',borderRadius:'999px',padding:'4px 8px'}}>Критично: {Number(summary.critical || 0)}</span>
              <span style={{fontSize:'11px',fontWeight:800,color:'#fbbf24',border:'1px solid rgba(245,158,11,.30)',borderRadius:'999px',padding:'4px 8px'}}>Внимание: {Number(summary.warning || 0)}</span>
              <span style={{fontSize:'11px',fontWeight:800,color:'#7dd3fc',border:'1px solid rgba(14,165,233,.28)',borderRadius:'999px',padding:'4px 8px'}}>Информация: {Number(summary.info || 0)}</span>
            </div>
            <div style={{display:'grid',gridTemplateColumns:isMobile?'1fr':'repeat(2,minmax(0,1fr))',gap:'8px',marginTop:'10px'}}>
              {sections.map((section) => {
                const meta = STATUS_META[section.status] || STATUS_META.info;
                const visibleItems = Array.isArray(section.items) ? section.items.slice(0,3) : [];
                return (
                  <div key={section.key} style={{minWidth:0,padding:'10px',borderRadius:'8px',border:`1px solid ${meta.border}`,background:meta.background}}>
                    <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',gap:'8px'}}>
                      <span style={{display:'inline-flex',alignItems:'center',gap:'6px',minWidth:0,fontSize:'12px',fontWeight:800,color:'#e2e8f0'}}>
                        {section.status === 'clear' ? <CheckCircle2 size={14} color={meta.color}/> : <AlertTriangle size={14} color={meta.color}/>}
                        <span style={{overflowWrap:'anywhere'}}>{section.title}</span>
                      </span>
                      <span style={{fontSize:'12px',fontWeight:900,color:meta.color}}>{Number(section.count || 0)}</span>
                    </div>
                    {visibleItems.length>0&&(
                      <div style={{marginTop:'7px',display:'grid',gap:'5px'}}>
                        {visibleItems.map((item, index) => {
                          const metric = formatMetric(item);
                          const project = item.project && item.project !== item.subject ? item.project : '';
                          return (
                            <div key={`${item.code || 'item'}-${index}`} style={{display:'grid',gridTemplateColumns:metric?'minmax(0,1fr) auto':'minmax(0,1fr)',gap:'8px',fontSize:'11px',lineHeight:1.35,color:'#cbd5e1'}}>
                              <span style={{minWidth:0,overflowWrap:'anywhere'}}>{item.subject}{project ? ` · ${project}` : ''}</span>
                              {metric&&<b style={{color:meta.color,whiteSpace:'nowrap'}}>{metric}</b>}
                            </div>
                          );
                        })}
                        {(section.truncated || Number(section.count || 0) > visibleItems.length)&&(
                          <span style={{fontSize:'10px',color:'#94a3b8'}}>Ещё {Math.max(0, Number(section.count || 0) - visibleItems.length)}</span>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </>
        )}
    </section>
  );
}
