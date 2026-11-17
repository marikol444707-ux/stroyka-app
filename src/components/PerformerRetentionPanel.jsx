import React, { useEffect, useRef, useState } from 'react';
import { API } from '../api';
import { actRetention, actRemaining } from '../utils/actSettlement';

const money = value => Number(value || 0).toLocaleString('ru-RU', { maximumFractionDigits: 2 }) + ' ₽';

function RetentionRow({ savedAct, refreshData, C, inp, btnB, btnG }) {
  const [amount, setAmount] = useState(String(savedAct.retentionAmount || 0));
  const [basis, setBasis] = useState(savedAct.retentionBasis || '');
  const [releaseAmount, setReleaseAmount] = useState('');
  const [releaseBasis, setReleaseBasis] = useState('');
  const [confirmed, setConfirmed] = useState(false);
  const [releaseConfirmed, setReleaseConfirmed] = useState(false);
  const [revision, setRevision] = useState(savedAct.retentionRevision);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const flight = useRef(false);
  const mounted = useRef(true);
  const current = useRef(savedAct);
  current.current = savedAct;
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const stale = revision !== savedAct.retentionRevision;
  const editable = (!Number(savedAct.paidAmount) || savedAct.retentionRevision === 0) && !Number(savedAct.retentionReleased);
  const valid = value => value !== '' && Number.isFinite(Number(value)) && Number(value) >= 0;

  const change = async release => {
    if (flight.current || stale) return;
    flight.current = true; setBusy(true); setError(''); setNotice('');
    const isCurrent = () => mounted.current && current.current.retentionRevision === savedAct.retentionRevision;
    try {
      const response = await fetch(`${API}/interim-acts/${savedAct.id}/${release ? 'retention-release' : 'retention'}`, {
        method: release ? 'POST' : 'PUT',
        headers: { 'Content-Type': 'application/json', 'X-Company-Id': String(savedAct.companyId), 'X-Company-Mode': 'company' },
        body: JSON.stringify({ amount: release ? releaseAmount : amount, basis: release ? releaseBasis : basis,
          confirmed: release ? releaseConfirmed : confirmed, expectedRevision: revision }),
      });
      const result = await response.json().catch(() => ({}));
      if (!isCurrent()) return;
      if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : `Не удалось сохранить (${response.status})`);
      if (!result.ok || result.actId !== savedAct.id || !Number.isSafeInteger(result.revision) || result.revision <= revision) {
        throw new Error('Ответ не подтверждает сохранение. Обновите данные и сверьте результат; введённые значения сохранены.');
      }
      setRevision(result.revision); setConfirmed(false); setReleaseConfirmed(false);
      setNotice(release ? 'Удержание освобождено. Денежная выплата не создана: запишите фактическую оплату отдельно в акте.' : 'Удержание сохранено по акту.');
      try { await refreshData?.(); } catch { if (mounted.current) setError('Изменение сохранено, но список не обновился. Обновите данные перед следующей операцией.'); }
    } catch (e) {
      if (isCurrent()) setError(e.message || 'Ответ не получен. Обновите данные перед повтором; введённые значения сохранены.');
    } finally {
      flight.current = false;
      if (mounted.current) setBusy(false);
    }
  };

  return <fieldset disabled={busy} style={{ border: '1px solid ' + C.border, padding: 12, marginBottom: 8 }}>
    <legend>Акт №{savedAct.id} · {savedAct.masterName} · {savedAct.project} · {savedAct.workPackage || 'Основная'}</legend>
    <p>{savedAct.periodStart} — {savedAct.periodEnd} · Установлено {money(savedAct.retentionAmount)} · Освобождено {money(savedAct.retentionReleased)}</p>
    <p>Удержано {money(actRetention(savedAct))} · Доступно к оплате {money(actRemaining(savedAct))}</p>
    {error && <p role="alert" style={{ color: C.danger }}>{error}</p>}
    {notice && <p role="status">{notice}</p>}
    {stale && <p role="alert">Данные акта изменились. Сверьте удержание и остаток. Ваши значения сохранены; автоматического повтора нет.</p>}
    {editable ? <div>
      <label>Сумма удержания <input aria-label={`Удержание ${savedAct.id}`} type="number" min="0" step="0.01" value={amount} onChange={e => setAmount(e.target.value)} style={inp}/></label>
      <label>Основание по договору <input aria-label={`Основание удержания ${savedAct.id}`} maxLength={1000} value={basis} onChange={e => setBasis(e.target.value)} style={inp}/></label>
      <label><input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)}/>Подтверждаю сумму удержания по договору</label>
      <button style={btnB} disabled={stale || !confirmed || !basis.trim() || !valid(amount)} onClick={() => change(false)}>Сохранить удержание</button>
    </div> : <p>Исходная сумма защищена после оплаты или освобождения удержания.</p>}
    {actRetention(savedAct) > 0 && <div>
      <label>Сумма к освобождению <input aria-label={`Освобождение ${savedAct.id}`} type="number" min="0.01" step="0.01" value={releaseAmount} onChange={e => setReleaseAmount(e.target.value)} style={inp}/></label>
      <label>Основание освобождения <input aria-label={`Основание освобождения ${savedAct.id}`} maxLength={1000} value={releaseBasis} onChange={e => setReleaseBasis(e.target.value)} style={inp}/></label>
      <label><input type="checkbox" checked={releaseConfirmed} onChange={e => setReleaseConfirmed(e.target.checked)}/>Условия договора для освобождения суммы проверены</label>
      <button style={btnB} disabled={stale || !releaseConfirmed || !releaseBasis.trim() || !valid(releaseAmount) || Number(releaseAmount) <= 0 || Number(releaseAmount) > actRetention(savedAct)} onClick={() => change(true)}>Подтвердить освобождение удержания</button>
      <p>Это разрешает последующую оплату. Денежная выплата создаётся отдельно при записи фактической оплаты акта.</p>
    </div>}
    <button style={btnG} onClick={async () => { try { await refreshData?.(); } catch { if (mounted.current) setError('Не удалось обновить данные'); } }}>Обновить данные удержания</button>
    {stale && <button style={btnG} onClick={() => { setRevision(savedAct.retentionRevision); setConfirmed(false); setReleaseConfirmed(false); setError(''); }}>Сверено: использовать загруженную версию</button>}
  </fieldset>;
}

export default function PerformerRetentionPanel({ acts = [], refreshData, C = {}, inp, btnB, btnG }) {
  const eligible = acts.filter(a => a.sourceType !== 'daily_work' && a.status !== 'Аннулирован' && Number.isSafeInteger(a.retentionRevision));
  return <details style={{ marginBottom: 16 }}>
    <summary>Гарантийные удержания по актам · подтверждение бухгалтера</summary>
    <p>Без подтверждения удержание равно нулю. Бухгалтер задаёт сумму по договору в пределах неоплаченного остатка. После оплаты подтверждённую сумму можно только освобождать. Освобождение ранее удержанной суммы подтверждается отдельно после проверки условий договора.</p>
    {!eligible.length && <p>Сохранённых актов для проверки удержания нет.</p>}
    {eligible.map(savedAct => <RetentionRow key={`${savedAct.companyId}:${savedAct.id}`} savedAct={savedAct} refreshData={refreshData} C={C} inp={inp} btnB={btnB} btnG={btnG}/>) }
  </details>;
}
