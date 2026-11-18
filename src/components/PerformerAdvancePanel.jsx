import React, { useEffect, useRef, useState } from 'react';
import { API } from '../api';
import { actRemaining } from '../utils/actSettlement';

const labels = { expense: 'Подотчёт на расходы', salary_advance: 'Зарплатный аванс', unclassified: 'Тип не проверен' };
const money = value => Number(value || 0).toLocaleString('ru-RU', { maximumFractionDigits: 2 }) + ' ₽';

function AdvanceRow({ payment, acts, refreshData, C, inp, btnB, btnG }) {
  const [kind, setKind] = useState(payment.paymentKind === 'unclassified' ? '' : payment.paymentKind || '');
  const [actId, setActId] = useState('');
  const [amount, setAmount] = useState('');
  const [revision, setRevision] = useState(payment.revision);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const flight = useRef(false);
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const stale = revision !== payment.revision;
  const used = (payment.allocations || []).reduce((sum, row) => sum + Number(row.amount), 0);
  const eligible = (acts || []).filter(act => Number(act.masterId) === Number(payment.givenToId)
    && Number(act.companyId) === Number(payment.companyId) && act.project === payment.projectName
    && act.sourceType !== 'daily_work' && act.status !== 'Аннулирован' && Number(act.paidAmount || 0) === 0);

  const change = async (operation, body) => {
    if (flight.current || stale) return;
    flight.current = true; setBusy(true); setError('');
    try {
      const response = await fetch(`${API}/accountable-payments/${payment.id}/${operation}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json', 'X-Company-Id': String(payment.companyId), 'X-Company-Mode': 'company' },
        body: JSON.stringify({ ...body, expectedRevision: revision }),
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : `Не удалось сохранить (${response.status})`);
      if (!mounted.current) return;
      if (!result.ok || !Number.isSafeInteger(result.revision) || result.revision <= revision) {
        throw new Error('Ответ не подтверждает новую версию. Обновите данные перед повтором; введённая сумма сохранена.');
      }
      setRevision(result.revision);
      await refreshData?.();
    } catch (e) {
      if (mounted.current) setError(e.message || 'Ответ не получен. Обновите список перед повтором; введённые суммы сохранены.');
    } finally {
      flight.current = false;
      if (mounted.current) setBusy(false);
    }
  };

  return <fieldset disabled={busy} style={{ border: '1px solid ' + C.border, padding: 12, marginBottom: 8 }}>
    <legend>{payment.givenTo} · {payment.projectName} · выдача №{payment.id}</legend>
    <p>{labels[payment.paymentKind] || labels.unclassified} · {money(payment.amount)} · {payment.date || 'Без даты'}</p>
    {payment.purpose && <p>{payment.purpose}</p>}
    {error && <p role="alert" style={{ color: C.danger }}>{error}</p>}
    {stale && <p role="alert">На сервере другая версия выдачи. Сверьте остаток перед сохранением. Введённые суммы не изменены.</p>}
    <select aria-label={`Тип выдачи ${payment.id}`} value={kind} onChange={e => setKind(e.target.value)} style={inp}>
      <option value="">Выберите проверенный тип</option><option value="expense">Подотчёт на расходы</option><option value="salary_advance">Зарплатный аванс</option>
    </select>
    <button style={btnB} disabled={!kind || stale || kind === payment.paymentKind} onClick={() => change('kind', { paymentKind: kind })}>Сохранить тип</button>
    {payment.paymentKind === 'salary_advance' && <div>
      <p>Зачтено: {money(used)} · Не распределено: {money(Number(payment.amount) - used)}</p>
      {(payment.allocations || []).map(row => {
        const act = (acts || []).find(item => Number(item.id) === Number(row.actId));
        return <p key={row.actId}>Акт №{row.actId} · {act?.workPackage || 'Пакет из акта'}: {money(row.amount)}</p>;
      })}
      <select aria-label={`Акт для аванса ${payment.id}`} value={actId} onChange={e => {
        setActId(e.target.value);
        setAmount(String((payment.allocations || []).find(row => String(row.actId) === e.target.value)?.amount || ''));
      }} style={inp}>
        <option value="">Выберите сохранённый акт пакета</option>
        {eligible.map(act => <option key={act.id} value={act.id}>№{act.id} · {act.workPackage || 'Основная'} · {act.periodStart} — {act.periodEnd} · остаток {money(actRemaining(act))}</option>)}
      </select>
      <input aria-label={`Сумма зачёта ${payment.id}`} type="number" min="0" step="0.01" value={amount} onChange={e => setAmount(e.target.value)} style={inp} />
      <button style={btnB} disabled={!actId || amount === '' || !Number.isFinite(Number(amount)) || Number(amount) < 0 || stale}
        onClick={() => change('allocations', { actId: Number(actId), amount: Number(amount) })}>Сохранить сумму зачёта</button>
      <p>Указывается полная сумма зачёта этой выдачи в выбранный акт. Ноль отменяет зачёт до денежной оплаты. Новая выплата не создаётся.</p>
      {!eligible.length && <p>Сначала сохраните акт нужного пакета. Оплаченные акты и расчёты по договорам с учётом материалов здесь не распределяются.</p>}
    </div>}
    <button style={btnG} onClick={async () => { try { await refreshData?.(); } catch { if (mounted.current) setError('Не удалось обновить список'); } }}>Обновить данные</button>
    {stale && <button style={btnG} onClick={() => { setRevision(payment.revision); setError(''); }}>Использовать загруженную версию после сверки</button>}
  </fieldset>;
}

export default function PerformerAdvancePanel({ payments = [], acts = [], refreshData, C = {}, inp, btnB, btnG }) {
  return <details style={{ marginBottom: 16 }}>
    <summary>Подотчёт и зарплатные авансы · проверка типа и ручной зачёт</summary>
    <p>Подотчёт на материалы не уменьшает оплату работ. Зарплатный аванс учитывается только после сохранённого зачёта в акт пакета. Старые выдачи сначала проверяет бухгалтер.</p>
    {!payments.length && <p>Выдач сотрудникам нет.</p>}
    {payments.map(payment => <AdvanceRow key={`${payment.companyId}:${payment.id}`} payment={payment} acts={acts} refreshData={refreshData} C={C} inp={inp} btnB={btnB} btnG={btnG} />)}
  </details>;
}
