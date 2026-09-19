import React, { useEffect, useRef, useState } from 'react';
import { useLedger } from '../work-material-accounting/ledgerUi';
import WorkSubmissionRecovery from '../work-material-accounting/WorkSubmissionRecovery';
import { createUploadActions } from '../uploads/uploadActions';
import useProtectedFileObjectUrl from '../uploads/useProtectedFileObjectUrl';
import AdditionalMaterials from './AdditionalMaterials';
import '../work-material-accounting/ledger.css';

function Photo({ url, API }) {
  const { src, loading, error } = useProtectedFileObjectUrl(url, value => value.startsWith('/') ? API + value : value);
  if (loading) return <span role="status">Загрузка фото…</span>;
  if (error || !src) return <span role="status">Фото недоступно</span>;
  return <a href={src} target="_blank" rel="noreferrer"><img src={src} alt="Фото работы" width="96" height="72" style={{ objectFit: 'cover' }} /></a>;
}

function AcceptanceContent({ journalId, API, companyContext, user, C, onChanged, onNavigate,
  materialAvailabilityMapForWork, prepareWorkMaterialGroups }) {
  const path = `/work-journal/${journalId}`;
  const [accepted, setAccepted] = useState(null);
  const [reason, setReason] = useState('');
  const [comment, setComment] = useState('');
  const [photos, setPhotos] = useState([]);
  const [materials, setMaterials] = useState([]);
  const [uploading, setUploading] = useState(false);
  const { data, error, busy, submit, recovered, setError, reload } = useLedger({ API, path: path + '/acceptance',
    companyContext, user, onChanged, onRecovered: batch => {
      if (batch?.commands?.slice(0, batch.next).some(command => command.path === path + '/acceptance' || command.path === path + '/resubmit')) {
        setPhotos([]); setReason(''); setComment(''); setMaterials([]); setAccepted(null);
      }
    },
  });
  const quantity = accepted ?? String(data?.quantity ?? '');
  const remaining = Math.round((Number(data?.quantity) - Number(quantity)) * 1e6) / 1e6;
  const validAcceptance = Number.isFinite(Number(quantity)) && Number(quantity) > 0 && remaining >= 0 && (!remaining || reason.trim());
  const upload = async files => {
    setUploading(true); setError('');
    try {
      if (files.length + photos.length > 20) throw new Error('Можно приложить не более 20 фотографий.');
      const { uploadPhoto } = createUploadActions({ API, projects: [] });
      for (const file of Array.from(files)) {
        const url = await uploadPhoto(file, { projectId: data.projectId, projectName: data.project, context: 'work-journal' });
        if (!url) throw new Error('Фото не загружено. Повторите загрузку.');
        setPhotos(previous => [...previous, url]);
      }
    } catch (e) { setError(e.message); }
    finally { setUploading(false); }
  };
  const decide = decision => submit(path + '/acceptance', { expectedState: data.expectedState, decision,
    acceptedQuantity: decision === 'accept' ? quantity : null, reason, photos });
  const resubmit = async () => {
    try {
      if (materials.some(item => !Number.isFinite(Number(item.quantity)) || Number(item.quantity) <= 0)) throw new Error('Укажите количество каждого добавленного материала.');
      if (materials.length && !prepareWorkMaterialGroups) throw new Error('Обновите остатки материалов перед отправкой.');
      const prepared = materials.length ? prepareWorkMaterialGroups(data.project, [materials])[0] : [];
      await submit(path + '/resubmit', { expectedState: data.expectedState, comment, photos, materialsUsed: prepared });
    } catch (e) { setError(e.message); }
  };
  return <>
    <WorkSubmissionRecovery {...{ API, companyContext, user, C }} onRecovered={recovered} />
    {error && <p role="alert" className="ledger-error">{error} <button disabled={busy} onClick={() => reload().catch(e => setError(e.message))}>Обновить работу</button></p>}
    {!data && !error && <p role="status">Загрузка приёмки…</p>}
    {data && <>
      <h4>{data.description}</h4>
      <p>{data.project} · {data.roomName || 'Помещение не указано'}<br />{data.masterName} · {data.date}</p>
      <p><b>{data.status}</b> · {data.quantity} {data.unit}</p>
      {data.comment && <p>{data.comment}</p>}
      {data.returnReason && <p><b>Замечания к доработке:</b> {data.returnReason}</p>}
      <div className="ledger-actions">{data.photos.map((url, i) => <Photo key={i} {...{ url, API }} />)}</div>
      {!data.photos.length && <p>Фотографий пока нет.</p>}
      <div className="ledger-actions">
        {data.parentJournalId && <button disabled={busy || uploading} onClick={() => onNavigate(data.parentJournalId)}>Исходная работа №{data.parentJournalId}</button>}
        {data.reworkJournalId && <button disabled={busy || uploading} onClick={() => onNavigate(data.reworkJournalId)}>Доработка №{data.reworkJournalId}</button>}
      </div>
      {(data.canReview || data.canResubmit) && <fieldset disabled={busy || uploading} style={{ border: 0, padding: 0, margin: '16px 0' }}>
        {data.canReview ? <>
          <label>Принять ({data.unit})<input type="number" min="0.000001" max={data.quantity} step="0.000001" value={quantity} onChange={event => setAccepted(event.target.value)} /></label>
          {remaining > 0 && <p>На доработку: {remaining} {data.unit}. Этот объём будет отдельной записью для повторной сдачи.</p>}
          {remaining < 0 && <p role="alert">Нельзя принять больше заявленного объёма.</p>}
          <label>Замечания<textarea maxLength={4000} value={reason} onChange={event => setReason(event.target.value)} /></label>
          <p>При частичной приёмке и возврате замечания обязательны.</p>
        </> : <>
          <h4>Повторная сдача: {data.quantity} {data.unit}</h4>
          <label>Что исправлено<textarea maxLength={4000} value={comment} onChange={event => setComment(event.target.value)} /></label>
          <AdditionalMaterials {...{ data, materialAvailabilityMapForWork }} value={materials} onChange={setMaterials} />
        </>}
        <label>Новые фотографии<input type="file" multiple accept="image/*" onChange={event => upload(event.target.files)} /></label>
        {uploading && <p role="status">Загружаем фотографии…</p>}
        <div className="ledger-actions">{photos.map((url, i) => <span key={i}><Photo {...{ url, API }} /><button aria-label={`Убрать фото ${i + 1}`} onClick={() => setPhotos(previous => previous.filter((_, index) => index !== i))}>Убрать</button></span>)}</div>
        <div className="ledger-actions">{data.canReview ? <>
          <button className="primary" disabled={!validAcceptance} onClick={() => decide('accept')}>Принять объём</button>
          <button disabled={!reason.trim()} onClick={() => decide('return')}>Вернуть весь объём</button>
        </> : <button className="primary" disabled={!comment.trim() || !photos.length} onClick={resubmit}>Сдать доработку</button>}</div>
        <p>В акт договора входит только принятый объём. Расход материалов сохраняется отдельно; штраф за брак оформляется в разделе «Материалы и брак».</p>
      </fieldset>}
      <section><h4>История решений</h4>
        {!data.history.length && <p>Решение по этой записи ещё не принято.</p>}
        {data.history.map(item => <article key={item.id}>
          <b>{item.decision === 'return' ? 'Возвращено на доработку' : `Принято ${item.acceptedQuantity} из ${item.submittedQuantity} ${data.unit}`}</b>
          <p>{item.actorName} · {new Date(item.createdAt).toLocaleString('ru-RU')}</p>
          {item.reason && <p>{item.reason}</p>}
          <div className="ledger-actions">{item.photos.map((url, i) => <Photo key={i} {...{ url, API }} />)}</div>
        </article>)}
      </section>
    </>}
  </>;
}

export default function WorkAcceptancePanel({ journal, onClose, C, ...props }) {
  const dialog = useRef(null);
  const [journalId, setJournalId] = useState(journal.id);
  useEffect(() => { dialog.current?.showModal(); }, []);
  return <dialog ref={dialog} className="work-ledger" aria-labelledby="work-acceptance-title" onCancel={onClose}
    style={{ '--ledger-bg': C.card || C.bg, '--ledger-text': C.text, '--ledger-border': C.border }}>
    <div className="ledger-actions" style={{ justifyContent: 'space-between', marginTop: 0 }}>
      <h3 id="work-acceptance-title">Приёмка работы №{journalId}</h3><button onClick={onClose}>Закрыть</button>
    </div>
    <AcceptanceContent key={`${props.companyContext?.selectedCompanyId}:${props.user?.id}:${props.user?.role}:${journalId}`} journalId={journalId} C={C} onNavigate={setJournalId} {...props} />
  </dialog>;
}
