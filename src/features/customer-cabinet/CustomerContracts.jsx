import React from 'react';
import { customerProjectRecord } from './projectSelection';
import { CustomerAttachment, recordLoadIssue } from './CustomerDocuments';

export default function CustomerContracts({ project, user, documents = [], loadState, fileSrc, C, card }) {
  const issue = recordLoadIssue(loadState, 'documents', project, user);
  const contracts = documents.filter(row => customerProjectRecord(row, project) && row.side === 'customer'
    && ['Договор', 'Доп.соглашение'].includes(row.docType) && row.signStatus !== 'Аннулирован');
  return <section style={{ ...card, padding: 20 }} aria-label="Договоры заказчика">
    <b>Договоры и дополнительные соглашения</b>
    {issue ? <p role="status">{issue}</p> : contracts.length ? contracts.map(row => <article key={row.id} style={{ padding: '12px 0', borderBottom: `1px solid ${C.border}` }}>
      <b>{row.docType}{row.number ? ' № ' + row.number : ''}</b>
      <p>{[row.docDate, row.signStatus].filter(Boolean).join(' · ')}</p>
      {row.scanUrl ? <CustomerAttachment value={row.scanUrl} fileSrc={fileSrc} /> : <p>Файл документа ещё не опубликован.</p>}
    </article>) : <p>Подрядчик ещё не опубликовал договоры для заказчика.</p>}
  </section>;
}
