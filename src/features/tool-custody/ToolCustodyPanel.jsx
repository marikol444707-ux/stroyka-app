import React, { useEffect, useRef, useState } from 'react';
import { useLedger } from '../work-material-accounting/ledgerUi';
import WorkSubmissionRecovery from '../work-material-accounting/WorkSubmissionRecovery';
import IncidentCard from './IncidentCard';
import '../work-material-accounting/ledger.css';
import './toolCustody.css';

const actions = { issue: 'Выдача', return: 'Возврат', repair: 'Ремонт завершён', recover: 'Инструмент найден', write_off: 'Списание', archive: 'Архивирование', reconcile: 'Уточнение прежней записи' };
export const toolCustodyEnabled = () => process.env.REACT_APP_TOOL_CUSTODY_ENABLED === '1';

function CustodyContent({ toolId, API, companyContext, user, C, onChanged }) {
  const path = `/tools/${toolId}/custody`;
  const [projectId, setProjectId] = useState('');
  const [recipientId, setRecipientId] = useState('');
  const [contractId, setContractId] = useState('');
  const [condition, setCondition] = useState('good');
  const [reason, setReason] = useState('');
  const [reconciledStatus, setReconciledStatus] = useState('На складе');
  const { data, error, busy, submit, recovered, reload, setError } = useLedger({ API, path, companyContext, user, onChanged,
    onRecovered: batch => {
      setError('');
      if (batch?.commands?.slice(0, batch.next).some(command => command.path === path)) {
        setReason(''); setCondition('good'); setProjectId(''); setRecipientId(''); setContractId('');
      }
    },
  });
  const move = action => submit(path, { action, expectedState: data.expectedState, reason, condition,
    ...(action === 'issue' || action === 'reconcile' ? { reconciledStatus, projectId: Number(projectId), recipientId: Number(recipientId), contractId: contractId ? Number(contractId) : null } : {}),
  });
  const tool = data?.tool;
  return <>
    <WorkSubmissionRecovery {...{ API, companyContext, user, C }} onRecovered={recovered} />
    {error && <p role="alert" className="ledger-error">{error} <button disabled={busy} onClick={() => reload().then(() => setError('')).catch(e => setError(e.message))}>Обновить карточку</button></p>}
    {!data && !error && <p role="status">Загрузка инструмента…</p>}
    {data && <>
      <h4>{tool.name} · {tool.inventoryNumber || 'Без инвентарного номера'}</h4>
      {tool.status && <p><b>{tool.status}</b>{tool.masterName ? ` · ${tool.masterName}` : ''}{tool.project ? ` · ${tool.project}` : ''}</p>}
      {tool.contractId && <p>Договор ответственности №{tool.contractId}</p>}
      {data.needsReconciliation && <p>В прежней записи не определены точные связи. Директор должен проверить фактическое местонахождение и получателя.</p>}
      {data.canManage && <section><h4>Операция с инструментом</h4>
        <fieldset disabled={busy} style={{ border: 0, padding: 0 }}>
          {data.needsReconciliation && data.canDecide && <label>Фактическое местонахождение<select value={reconciledStatus} onChange={e => setReconciledStatus(e.target.value)}><option>На складе</option><option>У мастера</option></select></label>}
          {(tool.status === 'На складе' || (data.needsReconciliation && data.canDecide && reconciledStatus === 'У мастера')) && <div className="ledger-grid">
            <label>Объект<select value={projectId} onChange={e => { setProjectId(e.target.value); setRecipientId(''); setContractId(''); }}><option value="">Выберите объект</option>{data.choices.projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label>
            <label>Получатель<select value={recipientId} disabled={!projectId} onChange={e => { setRecipientId(e.target.value); setContractId(''); }}><option value="">Выберите исполнителя</option>{data.choices.recipients.filter(r => r.projectIds.includes(Number(projectId))).map(r => <option key={r.id} value={r.id}>{r.name} · №{r.id}</option>)}</select></label>
            <label>Договор ответственности<select value={contractId} disabled={!recipientId} onChange={e => setContractId(e.target.value)}><option value="">Без договора — только учёт выдачи</option>{data.choices.contracts.filter(c => c.projectId === Number(projectId) && c.recipientId === Number(recipientId)).map(c => <option key={c.id} value={c.id}>№{c.id} · {c.name}</option>)}</select></label>
          </div>}
          {!data.needsReconciliation && ['У мастера', 'Утерян'].includes(tool.status) && <label>Состояние при возврате<select value={condition} onChange={e => setCondition(e.target.value)}>
            <option value="good">Исправен</option><option value="damaged">Повреждён, требуется ремонт</option>{tool.status === 'У мастера' && <option value="lost">Утерян</option>}
          </select></label>}
          <label>Причина / примечание<textarea maxLength={4000} value={reason} onChange={e => setReason(e.target.value)} /></label>
          <div className="ledger-actions">
            {data.needsReconciliation && data.canDecide && <button className="primary" disabled={!reason.trim() || (reconciledStatus === 'У мастера' && (!projectId || !recipientId))} onClick={() => move('reconcile')}>Уточнить прежнюю запись</button>}
            {tool.status === 'На складе' && <button className="primary" disabled={!projectId || !recipientId} onClick={() => move('issue')}>Выдать инструмент</button>}
            {tool.status === 'У мастера' && !data.needsReconciliation && <button className="primary" disabled={condition !== 'good' && !reason.trim()} onClick={() => move('return')}>Оформить возврат</button>}
            {tool.status === 'На ремонте' && <button className="primary" disabled={!reason.trim()} onClick={() => move('repair')}>Завершить ремонт</button>}
            {tool.status === 'Утерян' && <button className="primary" disabled={!reason.trim()} onClick={() => move('recover')}>Инструмент найден</button>}
            {data.canDecide && ['На складе', 'На ремонте', 'Утерян'].includes(tool.status) && <button disabled={!reason.trim()} onClick={() => move('write_off')}>Списать инструмент</button>}
            {data.canDecide && ['На складе', 'Списан'].includes(tool.status) && <button disabled={!reason.trim()} onClick={() => move('archive')}>В архив</button>}
          </div>
          {condition !== 'good' && tool.status === 'У мастера' && <p>Происшествие сохранится за получателем. Денежное возмещение назначается отдельным решением директора.</p>}
        </fieldset>
      </section>}
      <section><h4>Ответственность</h4>
        {!data.incidents.length && <p>Происшествия не зарегистрированы.</p>}
        {data.incidents.map(incident => <IncidentCard key={`${incident.id}:${incident.decisionId}`} {...{ incident, toolId, submit, busy }} canDecide={data.canDecide} canDispute={data.canDispute} />)}
      </section>
      <section><h4>История инструмента</h4>
        {!data.history.length && <p>Новых операций пока нет. Прежние записи доступны в общей истории склада.</p>}
        {data.history.map(event => <article key={event.id}><b>{actions[event.action]}</b><p>{event.actorName} · {new Date(event.createdAt).toLocaleString('ru-RU')}</p>
          <p>{event.before?.status} → {event.after?.status}<br />{event.action === 'issue' ? event.after?.masterName : event.before?.masterName}</p>
          {event.reason && <p>{event.reason}</p>}
        </article>)}
      </section>
    </>}
  </>;
}

export default function ToolCustodyPanel({ tool, C, onClose, ...props }) {
  const dialog = useRef(null);
  useEffect(() => { dialog.current?.showModal(); }, []);
  return <dialog ref={dialog} className="work-ledger tool-custody" aria-labelledby="tool-custody-title" onCancel={onClose}
    style={{ '--ledger-bg': C.card || C.bg, '--ledger-text': C.text, '--ledger-border': C.border }}>
    <div className="ledger-actions" style={{ justifyContent: 'space-between', marginTop: 0 }}><h3 id="tool-custody-title">Инструмент и ответственность</h3><button onClick={onClose}>Закрыть</button></div>
    <CustodyContent key={`${props.companyContext?.selectedCompanyId}:${props.user?.id}:${props.user?.role}:${tool.id}`} toolId={tool.id} C={C} {...props} />
  </dialog>;
}
