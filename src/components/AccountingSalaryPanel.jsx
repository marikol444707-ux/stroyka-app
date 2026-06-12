import React from 'react';
import { Plus, Search, Trash2 } from 'lucide-react';
import { API } from '../api';

export default function AccountingSalaryPanel({
  C,
  card,
  inp,
  btnG,
  btnO,
  btnR,
  tbl,
  tblH,
  tblC,
  salaryMonth,
  setSalaryMonth,
  listSearch,
  setListSearch,
  salaryEdits,
  payrollExtras,
  piecework,
  tools,
  staff,
  matchSearch,
  setSalaryEdit,
  toNum,
  salaryPayments,
  setSalaryPayments,
  paySalary,
  setPayrollExtra,
}) {
  const monthStr = salaryMonth;
  const monthStart = monthStr + '-01';
  const nextMonth = new Date(monthStart);
  nextMonth.setMonth(nextMonth.getMonth() + 1);
  const nextStr = nextMonth.toISOString().slice(0, 7) + '-01';
  const edits = (salaryEdits || {})[monthStr] || {};
  const extras = (payrollExtras || {})[monthStr] || [];

  const buildRow = staffRow => {
    const pieceworkRows = (piecework || []).filter(row => Number(row.staffId) === staffRow.id && row.date && row.date >= monthStart && row.date < nextStr);
    const pieceworkSum = pieceworkRows.reduce((sum, row) => sum + Number(row.total || 0), 0);
    const salary = Number(staffRow.salary || 0);
    const baseRaw = (staffRow.payType === 'Сдельная' ? pieceworkSum : (staffRow.payType === 'Оклад' ? salary : salary + pieceworkSum));
    const editRow = edits[staffRow.id] || {};
    const bonus = Number(editRow.bonus || 0);
    const toolHold = (tools || []).filter(tool => tool.masterName === staffRow.name && tool.issueType === 'В счёт зарплаты').reduce((sum, tool) => sum + Number(tool.cost || 0), 0);
    const deductExtra = Number(editRow.deduct || 0);
    const accrued = baseRaw + bonus - toolHold - deductExtra;
    const ndfl = Math.max(0, Math.round(accrued * 0.13));
    const insurance = Math.max(0, Math.round((baseRaw + bonus) * 0.302));
    const net = accrued - ndfl;
    return {
      id: staffRow.id,
      name: staffRow.name || (staffRow.lastName || '') + ' ' + (staffRow.firstName || ''),
      role: staffRow.role || '—',
      payType: staffRow.payType || '—',
      employmentType: staffRow.employmentType || '',
      salary,
      pwSum: pieceworkSum,
      base: baseRaw,
      bonus,
      toolHold,
      deductExtra,
      accrued,
      ndfl,
      insurance,
      net,
    };
  };

  const allStaff = (staff || [])
    .filter(staffRow => staffRow.status !== 'Уволен' && staffRow.status !== 'Архив')
    .filter(staffRow => matchSearch(listSearch, staffRow.name, staffRow.role));

  const staffRows = allStaff
    .filter(staffRow => ['ТД', 'Оклад', 'Штат'].includes(staffRow.employmentType)
      || staffRow.payType === 'Оклад'
      || (!staffRow.employmentType && ['прораб', 'инженер', 'бухгалтер', 'снабженец', 'кладовщик', 'директор', 'менеджер'].some(key => String(staffRow.role || '').toLowerCase().includes(key))))
    .map(buildRow);

  const sdelRows = allStaff.filter(staffRow => !staffRows.some(row => row.id === staffRow.id)).map(buildRow);
  const sumOf = (rows, key) => rows.reduce((sum, row) => sum + (row[key] || 0), 0);
  const allRows = [...staffRows, ...sdelRows];
  const grandAccrued = sumOf(allRows, 'accrued');
  const grandNdfl = sumOf(allRows, 'ndfl');
  const grandIns = sumOf(allRows, 'insurance');
  const grandNet = sumOf(allRows, 'net');
  const grandExtras = extras.reduce((sum, row) => sum + Number(row.amount || 0), 0);
  const grandTotalExpense = grandAccrued + grandIns + grandExtras;

  const renderTable = (rows, title) => (
    <div style={{ marginBottom: '18px' }}>
      <b style={{ color: C.text, fontSize: '13px', display: 'block', marginBottom: '8px' }}>{title} ({rows.length})</b>
      {rows.length === 0 ? (
        <p style={{ color: C.textMuted, fontSize: '12px' }}>Нет</p>
      ) : (
        <div style={{ ...card, padding: 0, overflow: 'auto' }}>
          <table style={tbl}>
            <thead>
              <tr>
                <th style={tblH}>ФИО</th>
                <th style={tblH}>Должность</th>
                <th style={tblH}>Оклад</th>
                <th style={tblH}>Сдельные</th>
                <th style={tblH}>Премия</th>
                <th style={tblH}>Удерж.</th>
                <th style={tblH}>Начисл.</th>
                <th style={tblH}>НДФЛ</th>
                <th style={tblH}>Страх.30.2%</th>
                <th style={tblH}>На руки</th>
                <th style={tblH}></th>
              </tr>
            </thead>
            <tbody>
              {rows.map(row => (
                <tr key={row.id}>
                  <td style={tblC}><b style={{ fontSize: '12px' }}>{row.name}</b></td>
                  <td style={tblC}>{row.role}</td>
                  <td style={tblC}>{row.salary ? Math.round(row.salary).toLocaleString('ru-RU') : '—'}</td>
                  <td style={tblC}>{row.pwSum > 0 ? Math.round(row.pwSum).toLocaleString('ru-RU') : '—'}</td>
                  <td style={tblC}>
                    <input
                      type='number'
                      step='any'
                      inputMode='decimal'
                      value={row.bonus || ''}
                      onChange={e => setSalaryEdit(monthStr, row.id, 'bonus', toNum(e.target.value))}
                      placeholder='0'
                      style={{ ...inp, marginBottom: 0, width: '80px', fontSize: '11px', padding: '3px 6px' }}
                    />
                  </td>
                  <td style={{ ...tblC, color: row.toolHold > 0 ? C.warning : undefined }}>
                    {(row.toolHold > 0 ? '-' + Math.round(row.toolHold).toLocaleString('ru-RU') + ' (инстр.) ' : '')}
                    <input
                      type='number'
                      step='any'
                      inputMode='decimal'
                      value={row.deductExtra || ''}
                      onChange={e => setSalaryEdit(monthStr, row.id, 'deduct', toNum(e.target.value))}
                      placeholder='0'
                      style={{ ...inp, marginBottom: 0, width: '70px', fontSize: '11px', padding: '3px 6px' }}
                    />
                  </td>
                  <td style={{ ...tblC, fontWeight: '600' }}>{Math.round(row.accrued).toLocaleString('ru-RU')}</td>
                  <td style={{ ...tblC, color: C.info }}>{Math.round(row.ndfl).toLocaleString('ru-RU')}</td>
                  <td style={{ ...tblC, color: C.warning, fontSize: '11px' }}>{Math.round(row.insurance).toLocaleString('ru-RU')}</td>
                  <td style={{ ...tblC, fontWeight: '700', color: C.success }}>{Math.round(row.net).toLocaleString('ru-RU') + ' ₽'}</td>
                  <td style={tblC}>
                    {(() => {
                      const payment = (salaryPayments || []).find(item => Number(item.staffId) === Number(row.id) && item.month === monthStr);
                      if (payment) {
                        return (
                          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                            <span style={{ color: C.success, fontSize: '11px', fontWeight: '700' }}>✓ {Math.round(Number(payment.amount || 0)).toLocaleString('ru-RU')}</span>
                            <button
                              onClick={async () => {
                                if (!window.confirm('Отменить выплату?')) return;
                                await fetch(API + '/salary-payments/' + payment.id, { method: 'DELETE' });
                                const refreshed = await fetch(API + '/salary-payments').then(response => response.json());
                                setSalaryPayments(Array.isArray(refreshed) ? refreshed : []);
                              }}
                              style={{ ...btnR, padding: '2px 5px' }}
                            >
                              <Trash2 size={10} />
                            </button>
                          </span>
                        );
                      }
                      return (
                        <button onClick={() => paySalary(row, monthStr)} style={{ ...btnO, padding: '3px 8px', fontSize: '10px' }}>
                          Выплатить
                        </button>
                      );
                    })()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px', flexWrap: 'wrap', gap: '8px' }}>
        <b style={{ color: C.text, fontSize: '15px', fontWeight: '700' }}>👥 Зарплата по сотрудникам</b>
        <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
          <button onClick={() => { const d = new Date(salaryMonth + '-01'); d.setMonth(d.getMonth() - 1); setSalaryMonth(d.toISOString().slice(0, 7)); }} style={{ ...btnG, padding: '5px 10px' }}>‹</button>
          <input type='month' value={salaryMonth} onChange={e => setSalaryMonth(e.target.value)} style={{ ...inp, marginBottom: 0, width: 'auto', padding: '5px 8px', fontSize: '12px' }} />
          <button onClick={() => { const d = new Date(salaryMonth + '-01'); d.setMonth(d.getMonth() + 1); setSalaryMonth(d.toISOString().slice(0, 7)); }} style={{ ...btnG, padding: '5px 10px' }}>›</button>
        </div>
      </div>
      <div style={{ ...card, padding: '10px 14px', marginBottom: '12px', backgroundColor: C.infoLight, border: '1.5px solid ' + C.infoBorder, fontSize: '11px', color: C.info }}>
        ℹ️ <b>Формулы:</b> Начислено = Оклад + Сдельные + Премия − Удержания. НДФЛ 13%. Страховые (от начислено): ПФР 22% + ФСС 2.9% + ОМС 5.1% + Травм 0.2% = <b>30.2%</b>. На руки = Начислено − НДФЛ.
      </div>
      <div style={{ position: 'relative', marginBottom: '12px' }}>
        <Search size={14} style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: C.textMuted }} />
        <input placeholder='🔍 Поиск сотрудника' value={listSearch} onChange={e => setListSearch(e.target.value)} style={{ ...inp, marginBottom: 0, paddingLeft: '32px', fontSize: '12px' }} />
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(140px,1fr))', gap: '10px', marginBottom: '14px' }}>
        <div style={{ ...card, padding: '12px', backgroundColor: C.bg }}><p style={{ color: C.textSec, fontSize: '11px', margin: '0 0 4px' }}>Начислено</p><b style={{ color: C.text, fontSize: '15px' }}>{Math.round(grandAccrued).toLocaleString('ru-RU') + ' ₽'}</b></div>
        <div style={{ ...card, padding: '12px', backgroundColor: C.infoLight }}><p style={{ color: C.info, fontSize: '11px', margin: '0 0 4px' }}>НДФЛ 13%</p><b style={{ color: C.info, fontSize: '14px' }}>{Math.round(grandNdfl).toLocaleString('ru-RU') + ' ₽'}</b></div>
        <div style={{ ...card, padding: '12px', backgroundColor: C.warningLight }}><p style={{ color: C.warning, fontSize: '11px', margin: '0 0 4px' }}>Страх.взносы 30.2%</p><b style={{ color: C.warning, fontSize: '14px' }}>{Math.round(grandIns).toLocaleString('ru-RU') + ' ₽'}</b></div>
        <div style={{ ...card, padding: '12px', backgroundColor: C.successLight }}><p style={{ color: C.success, fontSize: '11px', margin: '0 0 4px' }}>На руки</p><b style={{ color: C.success, fontSize: '15px' }}>{Math.round(grandNet).toLocaleString('ru-RU') + ' ₽'}</b></div>
        <div style={{ ...card, padding: '12px', backgroundColor: C.dangerLight, border: '1.5px solid ' + C.dangerBorder }}><p style={{ color: C.danger, fontSize: '11px', margin: '0 0 4px' }}>💰 Расход фирмы итого</p><b style={{ color: C.danger, fontSize: '15px' }}>{Math.round(grandTotalExpense).toLocaleString('ru-RU') + ' ₽'}</b><p style={{ color: C.textMuted, fontSize: '10px', margin: '2px 0 0' }}>Нач. + Страх. + Прочие</p></div>
      </div>
      {renderTable(staffRows, '👔 Штатные (оклад/ТД)')}
      {renderTable(sdelRows, '👷 Сдельщики/субподряд')}
      <div style={{ ...card, padding: '14px', marginTop: '14px', backgroundColor: C.bg }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px', flexWrap: 'wrap', gap: '6px' }}>
          <b style={{ color: C.text, fontSize: '13px' }}>💼 Прочие затраты по фонду оплаты</b>
          <button
            onClick={() => {
              const name = window.prompt('Название статьи затрат:', '');
              if (!name) return;
              const amount = window.prompt('Сумма (₽):', '0');
              if (amount === null) return;
              const next = [...extras, { id: Date.now(), name, amount: toNum(amount) }];
              setPayrollExtra(monthStr, next);
            }}
            style={btnO}
          >
            <Plus size={14} />
            Добавить
          </button>
        </div>
        {extras.length === 0 ? (
          <p style={{ color: C.textMuted, fontSize: '12px' }}>Например: материальная помощь, отпускные, командировочные, корпоратив, обучение, спецодежда…</p>
        ) : (
          extras.map(extra => (
            <div key={extra.id} style={{ padding: '6px 0', borderBottom: '1px solid ' + C.border, display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '8px' }}>
              <span style={{ color: C.text, fontSize: '12px' }}>{extra.name}</span>
              <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                <b style={{ color: C.warning, fontSize: '13px' }}>{Math.round(Number(extra.amount || 0)).toLocaleString('ru-RU') + ' ₽'}</b>
                <button onClick={() => { const next = extras.filter(item => item.id !== extra.id); setPayrollExtra(monthStr, next); }} style={{ ...btnR, padding: '2px 6px', fontSize: '10px' }}>
                  <Trash2 size={10} />
                </button>
              </div>
            </div>
          ))
        )}
        {extras.length > 0 && (
          <div style={{ padding: '6px 0', display: 'flex', justifyContent: 'space-between', marginTop: '6px', fontWeight: '700' }}>
            <span>Итого прочих:</span>
            <b style={{ color: C.warning }}>{Math.round(grandExtras).toLocaleString('ru-RU') + ' ₽'}</b>
          </div>
        )}
      </div>
    </div>
  );
}
