import React, { useState } from 'react';
import { formatMoney } from '../work-material-accounting/ledgerUi';

const statuses = { pending: 'Решение ещё не принято', confirmed: 'Штраф подтверждён', disputed: 'Оспаривается', cancelled: 'Ответственность отменена' };

export default function IncidentCard({ incident, toolId, canDecide, canDispute, submit, busy }) {
  const [reason, setReason] = useState('');
  const [amount, setAmount] = useState('');
  const [priceEvidence, setPriceEvidence] = useState('');
  const [contractEvidence, setContractEvidence] = useState('');
  const allocated = Number(incident.allocatedAmount) > 0;
  const editable = !allocated && incident.status !== 'cancelled';
  const decide = decision => submit(`/tools/${toolId}/incidents/${incident.id}/decisions`, {
    expectedDecisionId: incident.decisionId, decision, reason, amount, priceEvidence, contractEvidence,
  });
  return <article>
    <h4>{incident.kind === 'lost' ? 'Утеря' : 'Повреждение'} · происшествие №{incident.id}</h4>
    <p>{incident.holderName} · {incident.contractId ? `договор №${incident.contractId}` : 'Договор ответственности не указан'}</p>
    <p>{incident.reason}</p><p><b>{statuses[incident.status]}</b></p>
    {incident.decisionReason && <p>Основание решения: {incident.decisionReason}</p>}
    {incident.status === 'confirmed' && <p>Возмещение: <b>{formatMoney(incident.amount)}</b><br />{incident.contractEvidence}<br />{incident.priceEvidence}</p>}
    {allocated && <p>Включено в акты: {formatMoney(incident.allocatedAmount)}. Сохранённое решение защищено от изменения.</p>}
    {editable && (canDecide || canDispute) && <details>
      <summary>Решение по ответственности</summary>
      <fieldset disabled={busy} style={{ border: 0, padding: 0 }}>
        <label>Причина решения<textarea maxLength={4000} value={reason} onChange={e => setReason(e.target.value)} /></label>
        {canDecide && incident.contractId && <div className="ledger-grid">
          <label>Сумма возмещения, ₽<input type="number" min="0.01" step="0.01" value={amount} onChange={e => setAmount(e.target.value)} /></label>
          <label>Документ о стоимости<input maxLength={4000} value={priceEvidence} onChange={e => setPriceEvidence(e.target.value)} /></label>
          <label>Договорное основание<input maxLength={4000} value={contractEvidence} onChange={e => setContractEvidence(e.target.value)} /></label>
        </div>}
        {!incident.contractId && <p>Без договора подряда денежный штраф через акт недоступен.</p>}
        <div className="ledger-actions">
          {canDecide && incident.contractId && <button className="primary" disabled={!reason.trim() || !priceEvidence.trim() || !contractEvidence.trim() || !(Number(amount) > 0)} onClick={() => decide('confirmed')}>Подтвердить штраф</button>}
          {canDispute && <button disabled={!reason.trim()} onClick={() => decide('disputed')}>Оспорить</button>}
          {canDecide && <button disabled={!reason.trim()} onClick={() => decide('cancelled')}>Отменить ответственность</button>}
        </div>
      </fieldset>
    </details>}
    {incident.decisions?.length > 0 && <details><summary>История решений: {incident.decisions.length}</summary>{incident.decisions.map(item => <p key={item.id}>{statuses[item.decision]} · {formatMoney(item.amount)}<br />{item.reason}</p>)}</details>}
  </article>;
}
