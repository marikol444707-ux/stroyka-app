import React, { useEffect, useRef, useState } from 'react';
import WorkSubmissionRecovery from './WorkSubmissionRecovery';
import { formatMoney, useLedger } from './ledgerUi';
import { createUploadActions } from '../uploads/uploadActions';
import useProtectedFileObjectUrl from '../uploads/useProtectedFileObjectUrl';
import { workMaterialAccountingEnabled } from './materialSources';
import { pruneDefectDraft } from './ledgerDrafts';
import './ledger.css';

const sourceLabel = value => value === 'personal' ? 'У исполнителя' : 'Склад объекта';
const statuses = { pending: 'Ответственность не подтверждена', confirmed: 'Штраф подтверждён', disputed: 'Оспаривается', cancelled: 'Отменён' };

function Evidence({ url, API }) {
  const { src, loading, error } = useProtectedFileObjectUrl(url, value => value.startsWith('/') ? API + value : value);
  if (loading) return <span>Загрузка фото…</span>;
  if (error || !src) return <span role="status">Фото недоступно</span>;
  return <a href={src} target="_blank" rel="noreferrer"><img src={src} alt="Материал с браком" style={{ width: 88, height: 68, objectFit: 'cover', borderRadius: 6 }} /></a>;
}

function DefectCard({ defect, data, API, submit, busy }) {
  const [reason, setReason] = useState('');
  const [contractEvidence, setContractEvidence] = useState('');
  const [values, setValues] = useState({});
  const decide = async decision => {
    const payload = { decision, reason, contractEvidence, valuations: defect.items.map(item => ({ entryId: item.entryId, ...values[item.entryId] })) };
    if (await submit(`/work-journal/${data.journalId}/material-defects/${defect.id}/decisions`, payload)) setReason('');
  };
  return <article>
    <h4>Брак №{defect.id} · {statuses[defect.status]}</h4>
    <p>{defect.reason}</p>
    <div className="ledger-actions">{defect.photos.map((url, i) => <Evidence key={i} url={url} API={API} />)}</div>
    <ul>{defect.items.map(item => <li key={item.entryId}>{item.name}: {item.quantity} {item.unit} · {sourceLabel(item.source)}</li>)}</ul>
    {defect.decisionReason && <p>Решение: {defect.decisionReason}</p>}
    {defect.status === 'confirmed' && <p><b>Штраф: {formatMoney(defect.amount)}</b><br />Основание: {defect.contractEvidence}</p>}
    {defect.status !== 'cancelled' && workMaterialAccountingEnabled() && <details>
      <summary>Решение по ответственности</summary>
      <fieldset disabled={busy} style={{ border: 0, padding: 0 }}>
        <label style={{ marginTop: 12 }}>Причина решения<textarea value={reason} onChange={e => setReason(e.target.value)} /></label>
        {data.canConfirmDefect && <>
          <label style={{ marginTop: 12 }}>Договорное основание штрафа<input value={contractEvidence} onChange={e => setContractEvidence(e.target.value)} placeholder="Договор, пункт об ответственности за материал" /></label>
          {defect.items.map(item => <div className="ledger-grid" key={item.entryId}>
            <label>{item.name} · цена за {item.unit}<input type="number" min="0.01" step="0.01" value={values[item.entryId]?.unitPrice || ''} onChange={e => setValues(prev => ({ ...prev, [item.entryId]: { ...prev[item.entryId], unitPrice: e.target.value } }))} /></label>
            <label>Документ о стоимости<input value={values[item.entryId]?.priceEvidence || ''} onChange={e => setValues(prev => ({ ...prev, [item.entryId]: { ...prev[item.entryId], priceEvidence: e.target.value } }))} placeholder="Накладная, строка" /></label>
          </div>)}
        </>}
        <div className="ledger-actions">
          {data.canConfirmDefect && <button className="primary" disabled={!reason.trim() || !contractEvidence.trim()} onClick={() => decide('confirmed')}>Подтвердить штраф</button>}
          <button disabled={!reason.trim()} onClick={() => decide('disputed')}>Оспорить</button>
          {data.canConfirmDefect && <button disabled={!reason.trim()} onClick={() => decide('cancelled')}>Отменить ответственность</button>}
        </div>
      </fieldset>
    </details>}
  </article>;
}

export default function WorkMaterialAccountingPanel({ journal, API, companyContext, user, C, onClose, onChanged, onRecovered }) {
  const dialog = useRef(null);
  const path = `/work-journal/${journal.id}`;
  const [correction, setCorrection] = useState(null);
  const [draft, setDraft] = useState({ reason: '', photos: [], quantities: {} });
  const { reason, photos, quantities } = draft;
  const setReason = value => setDraft(previous => ({ ...previous, reason: value }));
  const setPhotos = value => setDraft(previous => ({ ...previous, photos: typeof value === 'function' ? value(previous.photos) : value }));
  const setQuantities = value => setDraft(previous => ({ ...previous, quantities: value }));
  const ledger = useLedger({ API, path: path + '/material-accounting', companyContext, user, onChanged,
    onRecovered: async batch => {
      setDraft(previous => pruneDefectDraft(batch, path, previous));
      setCorrection(previous => (batch?.commands || []).slice(0, batch?.next || 0).some(command => command.path === path + '/material-corrections'
        && command.payload.entryId === previous?.entryId && String(command.payload.quantity) === String(previous?.quantity)
        && command.payload.reason === previous?.reason) ? null : previous);
      await onRecovered?.(batch);
    },
  });
  const { data, error, busy, submit, recovered, setError } = ledger;
  const [uploading, setUploading] = useState(false);
  useEffect(() => { dialog.current?.showModal(); }, []);
  const upload = async files => {
    setUploading(true); setError('');
    try {
      const { uploadPhoto } = createUploadActions({ API, projects: [] });
      const added = [];
      for (const file of Array.from(files || [])) {
        const url = await uploadPhoto(file, { projectId: data.projectId, projectName: journal.project, context: 'work-journal' });
        if (!url) throw new Error('Не удалось загрузить фото. Повторите загрузку.');
        added.push(url);
      }
      setPhotos(prev => [...prev, ...added]);
    } catch (e) { setError(e.message); }
    finally { setUploading(false); }
  };
  return <dialog ref={dialog} className="work-ledger" aria-labelledby="material-ledger-title" onCancel={onClose} style={{ '--ledger-bg': C.card || C.bg, '--ledger-text': C.text, '--ledger-border': C.border }}>
    <div className="ledger-actions" style={{ justifyContent: 'space-between', marginTop: 0 }}>
      <h3 id="material-ledger-title">Расход материалов и брак</h3><button onClick={onClose} aria-label="Закрыть расход материалов">Закрыть</button>
    </div>
    <p>{journal.description} · {journal.project}</p>
    <WorkSubmissionRecovery {...{ API, companyContext, user, C }} onRecovered={recovered} />
    {error && <p role="alert" className="ledger-error">{error}</p>}
    {!data && !error && <p role="status">Загрузка фактического расхода…</p>}
    {data && <>
      <p>Исполнитель: <b>{data.actorName}</b> · договор №{data.contractId}. Расход сохранён независимо от приёмки работы.</p>
      <div className="ledger-scroll"><table><thead><tr><th>Материал</th><th>Источник</th><th className="amount">Израсходовано</th><th className="amount">Из него брак</th><th /></tr></thead><tbody>
        {data.entries.map(entry => <tr key={entry.id}><td>{entry.name}</td><td>{sourceLabel(entry.source)}</td><td className="amount">{entry.quantity} {entry.unit}</td><td className="amount">{entry.defectQuantity} {entry.unit}</td><td>{data.canCorrect && workMaterialAccountingEnabled() && <button onClick={() => setCorrection({ entryId: entry.id, name: entry.name, expectedQuantity: entry.quantity, quantity: String(entry.quantity), reason: '' })}>Исправить</button>}</td></tr>)}
      </tbody></table></div>
      {!data.entries.length && <p>По этой работе расход материалов не указан.</p>}
      {correction && <section>
        <h4>Исправление расхода: {correction.name}</h4><p>Укажите правильный фактический расход. Физический возврат неиспользованного материала оформляется на складе.</p>
        <fieldset disabled={busy} style={{ border: 0, padding: 0 }}><div className="ledger-grid">
          <label>Правильное количество<input type="number" min="0" step="0.000001" value={correction.quantity} onChange={e => setCorrection({ ...correction, quantity: e.target.value })} /></label>
          <label>Причина исправления<input value={correction.reason} onChange={e => setCorrection({ ...correction, reason: e.target.value })} /></label>
        </div><div className="ledger-actions"><button className="primary" disabled={!correction.reason.trim()} onClick={async () => { if (await submit(path + '/material-corrections', correction)) setCorrection(null); }}>Сохранить исправление</button><button onClick={() => setCorrection(null)}>Отмена</button></div></fieldset>
      </section>}
      {data.canRecordDefect && data.entries.length > 0 && workMaterialAccountingEnabled() && <section>
        <h4>Зафиксировать испорченный материал</h4><p>Брак относится к исполнителю этой работы. Денежный штраф попадёт в акт после подтверждения ответственности и стоимости.</p>
        <fieldset disabled={busy || uploading} style={{ border: 0, padding: 0 }}>
          <label>Причина брака<textarea value={reason} onChange={e => setReason(e.target.value)} /></label>
          <div className="ledger-grid">{data.entries.map(entry => <label key={entry.id}>{entry.name} · {sourceLabel(entry.source)} ({entry.unit})<input type="number" min="0" step="0.000001" placeholder="Количество брака" value={quantities[entry.id] || ''} onChange={e => setQuantities({ ...quantities, [entry.id]: e.target.value })} /></label>)}</div>
          <label>Фотографии брака<input type="file" multiple accept="image/*" onChange={e => upload(e.target.files)} /></label>
          {uploading && <p role="status">Загружаем фотографии…</p>}
          <div className="ledger-actions">{photos.map((url, i) => <span key={i}><Evidence url={url} API={API} /><button aria-label={'Убрать фото ' + (i + 1)} onClick={() => setPhotos(prev => prev.filter((_, index) => index !== i))}>×</button></span>)}</div>
          <div className="ledger-actions"><button className="primary" disabled={!reason.trim() || !photos.length} onClick={async () => {
            const items = Object.entries(quantities).filter(([, value]) => Number(value) > 0).map(([entryId, quantity]) => ({ entryId: Number(entryId), quantity }));
            await submit(path + '/material-defects', { reason, photos, items });
          }}>Зафиксировать брак</button></div>
        </fieldset>
      </section>}
      <h4 style={{ marginTop: 20 }}>Акты брака</h4>
      {!data.defects.length && <p>Брак по материалам этой работы не зарегистрирован.</p>}
      {data.defects.map(defect => <DefectCard key={defect.id} {...{ defect, data, API, submit, busy }} />)}
    </>}
  </dialog>;
}
