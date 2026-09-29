import React, { useEffect, useRef, useState } from 'react';
import { API } from '../../api';
import useCustomerCommands from './useCustomerCommands';
import { customerRemark } from './projectSelection';
import { CustomerAttachment, recordLoadIssue } from './CustomerDocuments';

export default function CustomerWarranty({ project, user, records = [], loadState, refresh, fileSrc, C, card, inp, btnB, btnG }) {
  const [description, setDescription] = useState('');
  const [foundAt, setFoundAt] = useState('');
  const [phone, setPhone] = useState('');
  const [photo, setPhoto] = useState('');
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState('');
  const [success, setSuccess] = useState('');
  const upload = useRef({ busy: false, active: true });
  const fileInput = useRef(null);
  const companyId = project.companyId ?? project.company_id;
  const command = useCustomerCommands({ scope: `${user.id}:${companyId}:${project.id}`, companyId, refresh });
  useEffect(() => {
    const owner = upload.current;
    owner.active = true;
    return () => { owner.active = false; owner.controller?.abort(); };
  }, []);
  async function attach(file) {
    if (!file || upload.current.busy) return;
    const owner = upload.current;
    setUploadError('');
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type) || file.size > 10 * 1024 * 1024) {
      setUploadError('Выберите фотографию JPG, PNG или WebP размером до 10 МБ.');
      return;
    }
    owner.busy = true;
    setUploading(true);
    const controller = new AbortController();
    owner.controller = controller;
    const timer = setTimeout(() => controller.abort(), 20000);
    try {
      const body = new FormData();
      body.append('file', file); body.append('projectId', String(project.id)); body.append('context', 'customer-request');
      const response = await fetch(API + '/upload-photo', { method: 'POST', body, signal: controller.signal,
        headers: { 'X-Company-Id': String(companyId), 'X-Company-Mode': 'company' } });
      const result = await response.json();
      if (!response.ok || Number(result.companyId) !== Number(companyId) || Number(result.projectId) !== Number(project.id)
          || !/^\/tenant-files\/[1-9]\d*\/content$/.test(result.contentUrl || '')) throw new Error('Upload not confirmed');
      if (owner.active) setPhoto(result.contentUrl);
    } catch (_) {
      if (owner.active) setUploadError('Не удалось загрузить фотографию. Текст обращения сохранён; выберите файл ещё раз.');
    } finally {
      clearTimeout(timer); owner.busy = false;
      if (owner.active) { setUploading(false); if (fileInput.current) fileInput.current.value = ''; }
    }
  }
  const issue = recordLoadIssue(loadState, 'warranty', project, user);
  const visible = records.filter(row => customerRemark(row, project, user));
  const blocked = command.blocked || uploading;
  return <section style={{ ...card, padding: 20, marginBottom: 16 }} aria-label="Гарантийные обращения">
    <h3 style={{ marginTop: 0 }}>Гарантийные обращения</h3>
    {project.warrantyEndDate && <p>Гарантия до {project.warrantyEndDate}</p>}
    {project.warrantyContact && <p>Контакт подрядчика: {project.warrantyContact}</p>}
    <form onSubmit={async event => {
      event.preventDefault(); if (blocked || upload.current.busy || !description.trim()) return;
      setSuccess('');
      await command.run('/warranty-defects', { method: 'POST', body: {
        projectId: project.id, description: description.trim(), foundAt: foundAt || null, reporterPhone: phone, photoUrl: photo,
      }, onSuccess: () => { setDescription(''); setFoundAt(''); setPhone(''); setPhoto(''); setUploadError(''); setSuccess('Обращение сохранено.'); } });
    }}>
      <label style={{ display: 'block', marginBottom: 12 }}>Что нужно исправить
        <textarea value={description} onChange={event => setDescription(event.target.value)} required maxLength={10000}
          disabled={blocked} style={{ ...inp, display: 'block', width: '100%', boxSizing: 'border-box', minHeight: 90 }} />
      </label>
      <label style={{ display: 'block', marginBottom: 12 }}>Когда обнаружено
        <input type="date" value={foundAt} onChange={event => setFoundAt(event.target.value)} disabled={blocked} style={{ ...inp, display: 'block' }} />
      </label>
      <label style={{ display: 'block', marginBottom: 12 }}>Телефон для связи (необязательно)
        <input type="tel" value={phone} maxLength={50} onChange={event => setPhone(event.target.value)} disabled={blocked} style={{ ...inp, display: 'block' }} />
      </label>
      <label style={{ display: 'block', marginBottom: 12 }}>Фотография (до 10 МБ)
        <input ref={fileInput} type="file" accept="image/jpeg,image/png,image/webp" disabled={blocked}
          onChange={event => attach(event.target.files?.[0])} style={{ display: 'block', maxWidth: '100%' }} />
      </label>
      {uploading && <p role="status">Загрузка фотографии…</p>}
      {photo && <p><CustomerAttachment value={photo} fileSrc={fileSrc} label="Посмотреть фотографию" />{' '}
        <button type="button" style={btnG} disabled={blocked} onClick={() => setPhoto('')}>Убрать из обращения</button></p>}
      {(uploadError || command.error) && <p role="alert" style={{ color: C.danger }}>{command.error || uploadError}</p>}
      {success && <p role="status">{success}</p>}
      <button type="submit" disabled={blocked || !description.trim()}
        style={{ ...btnB, opacity: blocked || !description.trim() ? 0.55 : 1 }}>Отправить обращение</button>
    </form>
    <h4>Мои обращения</h4>
    <button type="button" style={btnG} onClick={() => refresh().catch(() => {})}>Обновить обращения</button>
    {issue ? <p role="status">{issue}</p> : !visible.length ? <p>Обращений пока нет.</p> : visible.map(row => <article key={row.id}
      style={{ padding: '12px 0', borderBottom: `1px solid ${C.border}`, overflowWrap: 'anywhere' }}>
      <b>Обращение № {row.id} · {row.status}</b>
      <p style={{ whiteSpace: 'pre-wrap' }}>{row.description}</p>
      <CustomerAttachment value={row.photoUrl} fileSrc={fileSrc} label="Фотография обращения" />
      {row.fixNotes && <p style={{ whiteSpace: 'pre-wrap' }}>Ответ подрядчика: {row.fixNotes}</p>}
      {row.fixedAt && <p>Устранено: {row.fixedAt}</p>}
    </article>)}
  </section>;
}
