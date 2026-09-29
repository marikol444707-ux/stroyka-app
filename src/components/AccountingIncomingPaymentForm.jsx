import React, { useRef, useState } from 'react';
import { API } from '../api';

const financeRoles = ['директор', 'зам_директора', 'бухгалтер'];
const validId = value => /^(?:[1-9]\d*)$/.test(String(value)) && Number.isSafeInteger(Number(value));

export default function AccountingIncomingPaymentForm({ C, card, inp, btnO, btnG,
  projects = [], companyContext = {}, user, onClose, refreshData }) {
  const today = () => new Date().toISOString().slice(0, 10);
  const [form, setForm] = useState({ projectId: '', amount: '', date: today(), note: '' });
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const submitting = useRef(false);
  const companies = (companyContext.companies || []).filter(company =>
    validId(company.companyId) && !company.readOnly && company.active !== false
    && company.companyActive !== false && financeRoles.includes(company.role));
  const company = companyContext.mode === 'company' && companies.find(item =>
    Number(item.companyId) === Number(companyContext.selectedCompanyId));
  const ready = !!company && !companyContext.loading && !companyContext.error;
  const scopedProjects = projects.filter(project => company && validId(project.id)
    && Number(project.companyId ?? project.company_id) === Number(company.companyId)
    && String(project.name || '').trim());
  const nameCounts = new Map();
  const idCounts = new Map();
  scopedProjects.forEach(project => {
    const name = project.name.trim();
    nameCounts.set(name, (nameCounts.get(name) || 0) + 1);
    idCounts.set(String(project.id), (idCounts.get(String(project.id)) || 0) + 1);
  });
  const unique = project => nameCounts.get(project.name.trim()) === 1 && idCounts.get(String(project.id)) === 1;
  const update = (key, value) => { setForm(previous => ({ ...previous, [key]: value })); setError(''); };
  const save = async event => {
    event.preventDefault();
    if (submitting.current) return;
    const project = scopedProjects.find(item => String(item.id) === form.projectId && unique(item));
    const amount = Number(form.amount);
    if (!ready || !project) { setError('Выберите доступную компанию и однозначный объект.'); return; }
    if (!Number.isFinite(amount) || amount <= 0) { setError('Укажите сумму поступления больше нуля.'); return; }
    submitting.current = true;
    setBusy(true);
    setError('');
    try {
      // The shared fetch wrapper supplies the selected company headers. Never
      // bypass all-company read-only mode or infer ownership from an object name.
      const response = await fetch(API + '/project-payments', { method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ companyId: Number(company.companyId), projectName: project.name.trim(),
          amount, note: form.note, date: form.date || today(), paidBy: user?.name || '' }) });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) { setError(typeof result.detail === 'string' ? result.detail : 'Не удалось добавить поступление.'); return; }
      // Close before refreshing: a refresh failure must not invite a second POST.
      onClose();
      await refreshData();
    } catch (_error) {
      setError('Не удалось подтвердить сохранение. Проверьте список поступлений перед повторной отправкой.');
    } finally { submitting.current = false; setBusy(false); }
  };
  return <form aria-label="Поступление от заказчика" onSubmit={save} style={{ ...card, padding: '14px', marginBottom: '14px', border: '1.5px solid ' + C.accentBorder }}>
    <b style={{ color: C.text }}>Поступление от заказчика</b>
    <p style={{ color: C.textSec, fontSize: '12px' }}>Выбор компании переключает рабочую компанию платформы. В режиме «Все компании» сохранение недоступно.</p>
    <fieldset disabled={busy} style={{ border: 0, margin: 0, padding: 0, minWidth: 0 }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(min(100%,180px),1fr))', gap: '8px' }}>
        <label>Компания поступления
          <select value={company ? String(company.companyId) : ''} disabled={!companyContext.setSelectedCompanyId}
            onChange={event => { setForm({ projectId: '', amount: '', date: today(), note: '' }); setError('');
              companyContext.setSelectedCompanyId(event.target.value); }} style={{ ...inp, width: '100%', minWidth: 0 }}>
            <option value="" disabled>Выберите компанию</option>
            {companies.map(item => <option key={item.companyId} value={item.companyId}>{item.companyName || `Компания #${item.companyId}`}</option>)}
          </select>
        </label>
        <label>Объект поступления
          <select value={form.projectId} disabled={!ready} onChange={event => update('projectId', event.target.value)} style={{ ...inp, width: '100%', minWidth: 0 }}>
            <option value="">Выберите объект</option>
            {scopedProjects.map((item, index) => <option key={`${item.id}-${index}`} value={item.id} disabled={!unique(item)}>
              {item.name} · #{item.id}{!unique(item) ? ' — требуется уточнение' : ''}
            </option>)}
          </select>
        </label>
        <label>Сумма, ₽<input type="number" min="0.01" step="0.01" value={form.amount} onChange={event => update('amount', event.target.value)} style={{ ...inp, width: '100%', boxSizing: 'border-box' }} /></label>
        <label>Дата поступления<input type="date" value={form.date} onChange={event => update('date', event.target.value)} style={{ ...inp, width: '100%', boxSizing: 'border-box' }} /></label>
        <label>Договор, счёт или комментарий<input value={form.note} onChange={event => update('note', event.target.value)} style={{ ...inp, width: '100%', boxSizing: 'border-box' }} /></label>
      </div>
      {!ready && <p role="status">Выберите рабочую компанию с правом ведения платежей и дождитесь загрузки.</p>}
      {ready && !scopedProjects.length && <p role="status">Нет доступных объектов с подтверждённой компанией.</p>}
      {scopedProjects.some(item => !unique(item)) && <p role="status">Объекты с одинаковыми названиями или повторяющимися ID требуют уточнения. Сохранение для них недоступно.</p>}
      {error && <p role="alert" style={{ color: C.danger }}>{error}</p>}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginTop: '10px' }}>
        <button type="submit" disabled={!ready} style={btnO}>{busy ? 'Сохраняем...' : 'Сохранить поступление'}</button>
        <button type="button" onClick={onClose} style={btnG}>Отмена</button>
      </div>
    </fieldset>
  </form>;
}
