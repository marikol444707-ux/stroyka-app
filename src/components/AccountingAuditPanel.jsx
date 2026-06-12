import React from 'react';
import { API } from '../api';

export default function AccountingAuditPanel({
  C,
  card,
  btnB,
  auditLog,
  setAuditLog,
  tbl,
  tblH,
  tblC,
}) {
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px', flexWrap: 'wrap', gap: '10px' }}>
        <b style={{ color: C.text, fontSize: '15px', fontWeight: '700' }}>📜 Журнал действий пользователей (Audit log)</b>
        <button onClick={() => fetch(API + '/audit-log').then(r => r.json()).then(d => setAuditLog(Array.isArray(d) ? d : []))} style={{ ...btnB, fontSize: '12px', padding: '7px 12px' }}>
          🔄 Обновить
        </button>
      </div>
      {auditLog.length === 0 ? (
        <div style={{ ...card, padding: '30px', textAlign: 'center', color: C.textMuted }}>
          <p>Записей нет</p>
          <p style={{ fontSize: '11px' }}>Записи появляются по мере действий пользователей. Интеграция с endpoints — в Ф6.1.</p>
        </div>
      ) : (
        <div style={{ ...card, padding: 0, overflow: 'auto' }}>
          <table style={tbl}>
            <thead>
              <tr>
                <th style={tblH}>Время</th>
                <th style={tblH}>Пользователь</th>
                <th style={tblH}>Действие</th>
                <th style={tblH}>Объект изменения</th>
                <th style={tblH}>Проект</th>
                <th style={tblH}>Описание</th>
              </tr>
            </thead>
            <tbody>
              {auditLog.slice(0, 100).map(auditRow => (
                <tr key={auditRow.id}>
                  <td style={tblC}>{auditRow.createdAt || '—'}</td>
                  <td style={tblC}>{(auditRow.userName || '—') + (auditRow.userRole ? ' (' + auditRow.userRole + ')' : '')}</td>
                  <td style={tblC}>
                    <span style={{ padding: '2px 8px', borderRadius: '10px', fontSize: '11px', fontWeight: '600', backgroundColor: C.bg, color: C.textSec }}>
                      {auditRow.action || '—'}
                    </span>
                  </td>
                  <td style={tblC}>{(auditRow.entityType || '') + (auditRow.entityId ? ' №' + auditRow.entityId : '')}</td>
                  <td style={tblC}>{auditRow.projectName || '—'}</td>
                  <td style={{ ...tblC, maxWidth: '300px', whiteSpace: 'normal' }}>{auditRow.description || ''}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
