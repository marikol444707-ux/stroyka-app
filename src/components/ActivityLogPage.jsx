import React from 'react';

const formatAuditTime = (value) => {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString('ru-RU');
};

const auditActionText = (entry) => {
  const action = entry.action || '—';
  const description = entry.description || '';
  const project = entry.projectName ? ` · ${entry.projectName}` : '';
  return `${action}${description ? ` — ${description}` : ''}${project}`;
};

const mergeRows = (auditLog, activityLog) => {
  const rows = [
    ...(Array.isArray(auditLog) ? auditLog : []),
    ...(Array.isArray(activityLog) ? activityLog : []),
  ];
  const seen = new Set();
  return rows.filter((entry, index) => {
    const key = entry.userName || entry.user || entry.userRole || entry.role
      ? `${entry.action || ''}|${entry.description || ''}|${entry.userName || entry.user || ''}|${entry.createdAt || entry.time || ''}`
      : `id:${entry.id || index}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
};

export default function ActivityLogPage({C, tbl, tblH, tblC, activityLog, auditLog, roleLabels, isMobile = false}) {
  const rows = mergeRows(auditLog, activityLog);
  if (isMobile) {
    return (
      <div style={{paddingBottom:'84px'}}>
        <h3 style={{color:C.text,margin:'0 0 14px',fontSize:'20px',fontWeight:'800'}}>Журнал активности</h3>
        {rows.length===0&&<p style={{color:C.textMuted,textAlign:'center',padding:'30px'}}>Журнал пуст</p>}
        <div style={{display:'grid',gap:'10px'}}>
          {rows.map((e,i)=>(
            <div key={e.id || i} style={{backgroundColor:C.bgWhite,border:'1.5px solid '+C.border,borderRadius:'14px',padding:'14px',boxSizing:'border-box'}}>
              <div style={{color:C.text,fontSize:'14px',fontWeight:'800',lineHeight:1.35,overflowWrap:'anywhere'}}>
                {auditActionText(e)}
              </div>
              <div style={{marginTop:'10px',display:'grid',gridTemplateColumns:'1fr',gap:'6px',color:C.textSec,fontSize:'12px',lineHeight:1.3}}>
                <span><b style={{color:C.textMuted}}>Пользователь:</b> {e.userName || e.user || '—'}</span>
                <span><b style={{color:C.textMuted}}>Роль:</b> {roleLabels[e.userRole] || roleLabels[e.role] || e.userRole || e.role || '—'}</span>
                <span><b style={{color:C.textMuted}}>Время:</b> {formatAuditTime(e.createdAt || e.time)}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }
  return (
    <div>
      <h3 style={{color:C.text,marginBottom:'20px',fontSize:'16px',fontWeight:'700'}}>Журнал активности</h3>
      <table style={tbl}>
        <thead>
          <tr>
            <th style={tblH}>Действие</th>
            <th style={tblH}>Пользователь</th>
            <th style={tblH}>Роль</th>
            <th style={tblH}>Время</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((e,i)=>(
            <tr key={e.id || i}>
              <td style={{...tblC,whiteSpace:'normal'}}>{auditActionText(e)}</td>
              <td style={tblC}>{e.userName || e.user || '—'}</td>
              <td style={tblC}>{roleLabels[e.userRole] || roleLabels[e.role] || e.userRole || e.role || '—'}</td>
              <td style={tblC}>{formatAuditTime(e.createdAt || e.time)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length===0&&<p style={{color:C.textMuted,textAlign:'center',padding:'30px'}}>Журнал пуст</p>}
    </div>
  );
}
