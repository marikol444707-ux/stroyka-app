import React, { useEffect, useState } from 'react';
import { API } from '../../api';
import WorkSubmissionRecovery from './WorkSubmissionRecovery';
import { formatMoney, useLedger } from './ledgerUi';
import { buildSettlementAct } from './settlementPrint';
import { acknowledgedPayment } from './ledgerDrafts';
import { createUploadActions } from '../uploads/uploadActions';
import useProtectedFileObjectUrl from '../uploads/useProtectedFileObjectUrl';
import './ledger.css';

function SignedAct({ url }) {
  const { src, loading, error } = useProtectedFileObjectUrl(url, value => value.startsWith('/') ? API + value : value);
  if (loading) return <span>Загружаем документ…</span>;
  if (error || !src) return <span>Документ недоступен</span>;
  return <a href={src} target="_blank" rel="noreferrer">Подписанный акт</a>;
}

function SavedAct({ act, contract, projectId, submit, busy, canManage, showPreview, setError, acknowledged }) {
  const [payment, setPayment] = useState({ amount: String(act.remainingAmount), paidDate: new Date().toLocaleDateString('en-CA'), open: false });
  const { amount, paidDate } = payment;
  useEffect(() => {
    setPayment(previous => acknowledgedPayment(acknowledged, contract.id, act.id, previous.amount, previous.paidDate)
      ? { ...previous, amount: '', open: false } : previous);
  }, [acknowledged, contract.id, act.id]);
  const [uploading, setUploading] = useState(false);
  const upload = async file => {
    if (!file) return;
    setUploading(true); setError('');
    try {
      const { uploadPhoto } = createUploadActions({ API, projects: [] });
      const scanUrl = await uploadPhoto(file, { projectId, projectName: contract.projectName, context: 'brigade-contracts' });
      if (!scanUrl) throw new Error('Не удалось загрузить подписанный акт. Повторите загрузку.');
      await submit(`/brigade-contracts/${contract.id}/acts/${act.id}/signature`, { scanUrl });
    } catch (e) { setError(e.message); }
    finally { setUploading(false); }
  };
  return <article>
    <h4>Акт №{act.id} · {act.status}</h4>
    <p>{act.snapshot.periodFrom} — {act.snapshot.periodTo} · работ: {act.snapshot.works.length}</p>
    <div className="ledger-totals"><span>Принято<b>{formatMoney(act.totalAmount)}</b></span><span>Штрафы<b>{formatMoney(act.fineAmount)}</b></span><span>К оплате по акту<b>{formatMoney(act.netAmount)}</b></span></div>
    <p>Оплачено: {formatMoney(act.paidAmount)} · Остаток: <b>{formatMoney(act.remainingAmount)}</b></p>
    <div className="ledger-actions"><button onClick={() => showPreview(buildSettlementAct(act), 'Акт №' + act.id)}>Открыть акт для печати</button>{act.scanUrl && <SignedAct url={act.scanUrl} />}</div>
    {!act.scanUrl && canManage && <label style={{ marginTop: 12 }}>Загрузить подписанный акт<input type="file" accept="image/*,.pdf" disabled={busy || uploading} onChange={e => upload(e.target.files[0])} /></label>}
    {uploading && <p role="status">Сохраняем подписанный акт…</p>}
    {canManage && act.scanUrl && Number(act.remainingAmount) > 0 && <details open={payment.open} onToggle={event => { const open = event.currentTarget.open; setPayment(previous => ({...previous, open})); }} style={{ marginTop: 12 }}><summary>Записать оплату</summary>
      <fieldset disabled={busy} style={{ border: 0, padding: 0 }}><div className="ledger-grid">
        <label>Сумма оплаты, ₽<input type="number" step="0.01" min="0.01" max={act.remainingAmount} value={amount} onChange={e => setPayment({...payment, amount:e.target.value})} /></label>
        <label>Дата оплаты<input type="date" value={paidDate} onChange={e => setPayment({...payment, paidDate:e.target.value})} /></label>
      </div><button className="primary" disabled={!amount || !paidDate} onClick={() => submit('/brigade-payments', { contractId: contract.id, actId: act.id, amount, paidDate })}>Сохранить оплату</button></fieldset>
    </details>}
    {act.scanUrl && Number(act.netAmount) === 0 && <p>Сумма работ полностью зачтена штрафом. Денежная оплата не требуется.</p>}
  </article>;
}

export default function ContractSettlementPanel({ contract, companyContext, user, C, showPreview, onChanged, onRecovered }) {
  const [periodFrom, setPeriodFrom] = useState('');
  const [periodTo, setPeriodTo] = useState('');
  const [acknowledged, setAcknowledged] = useState(null);
  const completePeriod = Boolean(periodFrom && periodTo);
  const incompletePeriod = Boolean(periodFrom || periodTo) && !completePeriod;
  const query = completePeriod ? `?periodFrom=${encodeURIComponent(periodFrom)}&periodTo=${encodeURIComponent(periodTo)}` : '';
  const ledger = useLedger({ API, path: `/brigade-contracts/${contract.id}/settlement${query}`, companyContext, user, onChanged,
    onRecovered: async batch => { setAcknowledged(batch); await onRecovered?.(batch); },
  });
  const { data, error, busy, submit, recovered, setError } = ledger;
  const create = () => {
    const dates = data.eligibleWorks.map(work => String(work.date).slice(0, 10)).sort();
    return submit(`/brigade-contracts/${contract.id}/acts`, {
      workJournalIds: data.eligibleWorks.map(work => work.id),
      expectedGrossAmount: String(data.grossAmount), expectedFineAmount: String(data.fineAmount),
      fineAllocations: data.fineAllocations,
      periodFrom: periodFrom || dates[0], periodTo: periodTo || dates[dates.length - 1],
    });
  };
  return <div className="work-ledger" style={{ '--ledger-bg': C.card || C.bg, '--ledger-text': C.text, '--ledger-border': C.border }}>
    <section><h3>Акты и оплата по договору</h3><p>{contract.brigadeName} · {contract.projectName} · договор №{contract.id}</p>
      <WorkSubmissionRecovery {...{ API, companyContext, user, C }} onRecovered={recovered} />
      {error && <p className="ledger-error" role="alert">{error}</p>}
      <div className="ledger-grid">
        <label>Работы с даты<input type="date" disabled={busy} value={periodFrom} onChange={e => setPeriodFrom(e.target.value)} /></label>
        <label>По дату<input type="date" disabled={busy} value={periodTo} onChange={e => setPeriodTo(e.target.value)} /></label>
      </div>
      {incompletePeriod && <p>Укажите обе даты или очистите их, чтобы включить все неактированные работы.</p>}
      {!data && !error && <p role="status">Рассчитываем работы и штрафы…</p>}
      {data && <>
        <h4>Предварительный расчёт нового акта</h4>
        <div className="ledger-totals"><span>Принятые работы<b>{formatMoney(data.grossAmount)}</b></span><span>Штрафы<b>{formatMoney(data.fineAmount)}</b></span><span>К оплате<b>{formatMoney(data.netAmount)}</b></span></div>
        <p>В расчёте только подтверждённые работы, которые ещё не включены в акт.</p>
        {data.eligibleWorks.length > 0 && <details><summary>Работы: {data.eligibleWorks.length}</summary><div className="ledger-scroll"><table><thead><tr><th>ЖПР</th><th>Работа</th><th>Объём</th><th className="amount">Стоимость</th></tr></thead><tbody>{data.eligibleWorks.map(work => <tr key={work.id}><td>№{work.id}</td><td>{work.description}<br />{work.room_name}</td><td>{work.quantity} {work.unit}</td><td className="amount">{formatMoney(work.execution_total)}</td></tr>)}</tbody></table></div></details>}
        {data.fineAllocations.map(fine => <p key={fine.defectId}>Брак №{fine.defectId} · ЖПР №{fine.journalId}: <b>{formatMoney(fine.amount)}</b><br />{fine.reason} · {fine.contractEvidence}</p>)}
        {Number(data.carryFineAmount) > 0 && <p>Остаток подтверждённых штрафов для следующих актов: <b>{formatMoney(data.carryFineAmount)}</b>.</p>}
        {data.canManage && <div className="ledger-actions"><button className="primary" disabled={busy || incompletePeriod || !data.eligibleWorks.length} onClick={create}>{busy ? 'Сохраняем…' : 'Сформировать акт с указанными штрафами'}</button></div>}
        {!data.eligibleWorks.length && <p>Нет принятых работ для нового акта за выбранный период.</p>}
      </>}
    </section>
    {data && <><h4>Сохранённые акты</h4>{!data.acts.length && <p>Акты пока не сформированы.</p>}{data.acts.map(act => <SavedAct key={act.id} {...{ act, contract, submit, busy, showPreview, setError, acknowledged }} projectId={data.projectId} canManage={data.canManage} />)}</>}
  </div>;
}
