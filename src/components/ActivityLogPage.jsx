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

export default function ActivityLogPage({C, tbl, tblH, tblC, activityLog, auditLog, roleLabels}) {
  const rows = Array.isArray(auditLog) && auditLog.length ? auditLog : (Array.isArray(activityLog) ? activityLog : []);
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
