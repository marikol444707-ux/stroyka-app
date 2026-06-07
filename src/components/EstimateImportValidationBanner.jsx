import React from 'react';

const severityRank = (severity) => {
  const s = String(severity || '').toLowerCase();
  if (s === 'critical' || s === 'критично') return 0;
  if (s === 'warning' || s === 'внимание') return 1;
  return 2;
};

const severityTone = (severity, C) => {
  const rank = severityRank(severity);
  if (rank === 0) return {icon:'🔴', color:C.danger, bg:C.dangerLight, border:C.dangerBorder, label:'Критично'};
  if (rank === 1) return {icon:'🟡', color:C.warning, bg:C.warningLight, border:C.warningBorder, label:'Внимание'};
  return {icon:'💡', color:C.info, bg:C.infoLight, border:C.infoBorder, label:'Инфо'};
};

const issueWhere = (issue) => issue.where || [issue.sectionName, issue.itemName].filter(Boolean).join(' / ') || '?';
const issueMessage = (issue) => issue.message || issue.problem || '';
const issueStatus = (issue) => issue.status || issue.type || issue.title || 'Замечание';

export default function EstimateImportValidationBanner({
  C,
  card,
  importValidating,
  importValidationWarnings,
  setImportValidationWarnings,
  estimateIssues = [],
  onJumpToIssue,
}) {
  const issues = (estimateIssues && estimateIssues.length ? estimateIssues : (importValidationWarnings || []))
    .map((issue, idx) => ({...issue, _issueIdx: idx}))
    .sort((a,b) => severityRank(a.severity) - severityRank(b.severity));
  const [expanded, setExpanded] = React.useState(false);
  const [filter, setFilter] = React.useState('all');

  if (!importValidating && !issues.length) return null;

  const hasCritical = issues.some(w => severityRank(w.severity) === 0);
  const toneColor = importValidating ? C.info : (hasCritical ? C.danger : C.warning);
  const statusCounts = issues.reduce((acc, issue) => {
    const key = issueStatus(issue);
    acc[key] = (acc[key] || 0) + 1;
    return acc;
  }, {});
  const statusOptions = Object.entries(statusCounts).sort((a,b) => b[1] - a[1]);
  const filtered = filter === 'all' ? issues : issues.filter(issue => issueStatus(issue) === filter);
  const visible = expanded ? filtered : filtered.slice(0, 20);
  const canClearManualWarnings = !estimateIssues?.length && (importValidationWarnings || []).length > 0;

  return (
    <div
      style={{
        ...card,
        padding:'14px',
        marginBottom:'14px',
        backgroundColor: importValidating ? C.infoLight : (hasCritical ? C.dangerLight : C.warningLight),
        border: '1.5px solid '+(importValidating ? C.infoBorder : (hasCritical ? C.dangerBorder : C.warningBorder)),
        position:'sticky',
        top:'8px',
        zIndex:18,
      }}
    >
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:'10px',marginBottom:'10px'}}>
        <div>
          <b style={{fontSize:'13px',color:toneColor}}>
            {importValidating ? '🤖 ИИ проверяет смету...' : ('⚠️ Проблемы сметы: '+issues.length)}
          </b>
          {!importValidating && issues.length > 0 && (
            <span style={{marginLeft:'8px',fontSize:'11px',color:C.textSec}}>
              {hasCritical ? 'сначала исправьте красные строки' : 'критичных ошибок нет'}
            </span>
          )}
        </div>
        <div style={{display:'flex',gap:'6px',alignItems:'center'}}>
          {issues.length > 20 && (
            <button onClick={()=>setExpanded(v=>!v)} style={{background:C.bgWhite,border:'1px solid '+C.border,borderRadius:'8px',padding:'5px 9px',cursor:'pointer',fontSize:'11px',color:C.text}}>
              {expanded ? 'Свернуть' : 'Показать все'}
            </button>
          )}
          {canClearManualWarnings && (
            <button onClick={()=>setImportValidationWarnings([])} style={{background:'none',border:'none',cursor:'pointer',fontSize:'16px',color:C.textSec}}>×</button>
          )}
        </div>
      </div>

      {issues.length > 0 && (
        <>
          <div style={{display:'flex',gap:'6px',flexWrap:'wrap',marginBottom:'10px'}}>
            <button onClick={()=>setFilter('all')} style={{backgroundColor:filter==='all'?toneColor:C.bgWhite,color:filter==='all'?'white':C.text,border:'1px solid '+(filter==='all'?toneColor:C.border),borderRadius:'999px',padding:'4px 10px',fontSize:'11px',fontWeight:'700',cursor:'pointer'}}>
              Все {issues.length}
            </button>
            {statusOptions.slice(0, 8).map(([status, count]) => (
              <button key={status} onClick={()=>setFilter(status)} style={{backgroundColor:filter===status?toneColor:C.bgWhite,color:filter===status?'white':C.text,border:'1px solid '+(filter===status?toneColor:C.border),borderRadius:'999px',padding:'4px 10px',fontSize:'11px',fontWeight:'700',cursor:'pointer'}}>
                {status}: {count}
              </button>
            ))}
          </div>

          <div style={{maxHeight:expanded?'420px':'260px',overflowY:'auto',paddingRight:'4px'}}>
            {visible.map(issue => {
              const tone = severityTone(issue.severity, C);
              const canJump = Boolean(onJumpToIssue && issue.sectionIdx !== undefined && issue.itemIdx !== undefined);
              return (
                <div
                  key={issue.key || issue._issueIdx}
                  style={{
                    padding:'8px 10px',
                    marginBottom:'6px',
                    backgroundColor:C.bgWhite,
                    borderRadius:'8px',
                    border:'1px solid '+tone.border,
                    borderLeft:'4px solid '+tone.color,
                  }}
                >
                  <div style={{display:'grid',gridTemplateColumns:'minmax(0,1fr) auto',gap:'10px',alignItems:'start'}}>
                    <div style={{minWidth:0}}>
                      <b style={{fontSize:'11px',color:C.text,display:'block',lineHeight:1.35}}>
                        {tone.icon+' '+issueStatus(issue)}
                      </b>
                      <div style={{fontSize:'11px',color:C.textSec,lineHeight:1.35,marginTop:'2px',wordBreak:'break-word'}}>
                        {issueWhere(issue)}
                      </div>
                      <p style={{fontSize:'11px',color:C.text,margin:'4px 0 0',lineHeight:1.35}}>
                        {issueMessage(issue)}
                      </p>
                    </div>
                    {canJump && (
                      <button onClick={()=>onJumpToIssue(issue)} style={{backgroundColor:C.bg,border:'1px solid '+C.border,borderRadius:'8px',padding:'5px 9px',fontSize:'11px',fontWeight:'700',color:C.text,cursor:'pointer',whiteSpace:'nowrap'}}>
                        К строке
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
            {!expanded && filtered.length > visible.length && (
              <div style={{fontSize:'11px',color:C.textSec,textAlign:'center',padding:'6px'}}>
                Показаны первые {visible.length} из {filtered.length}. Нажмите “Показать все”.
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
