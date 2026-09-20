import React, { useState } from 'react';
import { customerProjectRecord } from './projectSelection';
import { recordLoadIssue } from './CustomerDocuments';
import useCustomerCommands from './useCustomerCommands';

export default function CustomerHiddenActs({ project, user, rows = [], loadState, refresh, C, card }) {
  const scope = `${user.id}:${project.companyId ?? project.company_id}:${project.id}`;
  const [confirmed, setConfirmed] = useState({});
  const command = useCustomerCommands({ scope, companyId: project.companyId ?? project.company_id, refresh });
  const issue = recordLoadIssue(loadState, 'hiddenActs', project, user);
  const acts = rows.filter(row => customerProjectRecord(row, project));
  return <section aria-label="Акты скрытых работ" style={{ ...card, padding: 20, marginBottom: 16 }}>
    <h3>Акты освидетельствования скрытых работ</h3>
    <p>Подтверждение фиксируется в программе. Подписанные файлы актов доступны в документах объекта.</p>
    {issue ? <p role="status">{issue}</p> : acts.length ? acts.map(row => <article key={row.id} style={{ padding: '12px 0', borderBottom: `1px solid ${C.border}` }}>
      <b>{[row.actNumber, row.workName].filter(Boolean).join(' · ')}</b>
      <p>{[`${Number(row.quantity || 0).toLocaleString('ru-RU')} ${row.unit || ''}`, row.workDate, row.city].filter(Boolean).join(' · ')}</p>
      {row.sectionName && <p>{row.sectionName}</p>}
      {row.conclusion && <p>{row.conclusion}</p>}
      {row.signedCustomer || confirmed[scope + ':' + row.id] ? <p>Подтверждено{row.signedCustomer ? ': ' + row.signedCustomer : ''}{row.signedCustomerAt ? ' · ' + row.signedCustomerAt : ''}</p>
        : <button disabled={command.blocked || !row.revision} onClick={() => command.run(`/hidden-works-acts/${row.id}/customer-confirm`, {
          method: 'POST', body: { revision: row.revision }, onSuccess: () => setConfirmed(previous => ({ ...previous, [scope + ':' + row.id]: true })),
        })}>Подтвердить акт</button>}
    </article>) : <p>Актов по подтверждённым работам пока нет.</p>}
    {command.error && <p role="alert">{command.error}</p>}
  </section>;
}
