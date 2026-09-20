import React from 'react';
import { customerProjectRecord } from './projectSelection';
import { customerRecordsScope } from './useCustomerRecordsLoader';

export function recordLoadIssue(state, kind, project, user) {
  const entry = state?.[kind];
  if (entry?.scope !== customerRecordsScope(user, project.companyId ?? project.company_id, project.id)) return 'Загрузка данных…';
  if (entry.status === 'error') return entry.error || 'Данные временно недоступны.';
  return entry.status === 'ready' ? '' : 'Загрузка данных…';
}

export function CustomerAttachment({ value, fileSrc, label = 'Открыть вложение' }) {
  if (!value) return null;
  // External storage URLs must first be registered and published through the API.
  const safe = typeof value === 'string' && (/^\/tenant-files\/[1-9]\d*\/content$/.test(value)
    || /^\/uploads\/[^?#]+$/.test(value));
  return safe ? <a href={fileSrc(value)} target="_blank" rel="noopener noreferrer">{label}</a>
    : <p>Для вложения требуется защищённая ссылка. Обратитесь к подрядчику.</p>;
}

export default function CustomerDocuments({ project, user, documents = [], letters = [], loadState, refresh, fileSrc, C, card, btnG }) {
  const renderRows = (kind, rows) => {
    const issue = recordLoadIssue(loadState, kind, project, user);
    if (issue) return <p role="status">{issue}</p>;
    const visible = rows.filter(row => customerProjectRecord(row, project) && row.side === 'customer'
      && row.signStatus !== 'Аннулирован' && row.status !== 'Аннулировано');
    if (!visible.length) return <p style={{ color: C.textMuted }}>{kind === 'documents' ? 'Опубликованных документов пока нет.' : 'Писем по объекту пока нет.'}</p>;
    return visible.map(row => <article key={row.id} style={{ padding: '12px 0', borderBottom: `1px solid ${C.border}`, overflowWrap: 'anywhere' }}>
      <b>{kind === 'documents' ? [row.docType || 'Документ', row.number].filter(Boolean).join(' № ') : row.subject || 'Письмо'}</b>
      <p style={{ color: C.textSec, fontSize: 12 }}>{[row.docDate || row.letterDate, row.signStatus || row.status].filter(Boolean).join(' · ')}</p>
      {kind === 'letters' && row.body && <p style={{ whiteSpace: 'pre-wrap' }}>{row.body}</p>}
      <CustomerAttachment value={row.scanUrl || row.fileUrl} fileSrc={fileSrc} />
    </article>);
  };
  return <section style={{ ...card, padding: 20, marginBottom: 16 }} aria-label="Документы и письма">
    <h3 style={{ marginTop: 0 }}>Документы и письма</h3>
    <button type="button" style={btnG} onClick={() => refresh().catch(() => {})}>Обновить документы</button>
    <h4>Документы объекта</h4>{renderRows('documents', documents)}
    <h4>Переписка по объекту</h4>{renderRows('letters', letters)}
  </section>;
}
