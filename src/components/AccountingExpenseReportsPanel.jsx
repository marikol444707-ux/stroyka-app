import React from 'react';
import { Check, Plus, Trash2 } from 'lucide-react';
import { API } from '../api';
import { createExpenseReportForm } from '../features/payments/paymentInitialForms';

export default function AccountingExpenseReportsPanel({
  C,
  card,
  inp,
  btnO,
  btnG,
  btnR,
  staff,
  projects,
  newExpenseReport,
  setNewExpenseReport,
  refreshData,
  expenseReports,
  user,
  badge,
  isMobile = false,
}) {
  const visibleExpenseReports = isMobile ? expenseReports.slice(0, 40) : expenseReports;

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px', flexWrap: 'wrap', gap: '8px' }}>
        <b style={{ color: C.text, fontSize: '15px', fontWeight: '700' }}>💼 Авансовые отчёты и командировочные</b>
        <button
          onClick={() => setNewExpenseReport(createExpenseReportForm())}
          style={btnO}
        >
          <Plus size={14} />
          Новый отчёт
        </button>
      </div>
      {newExpenseReport && (
        <div style={{ ...card, padding: '16px', marginBottom: '14px', backgroundColor: C.bg }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginBottom: '8px' }}>
            <select value={newExpenseReport.reportType} onChange={e => setNewExpenseReport({ ...newExpenseReport, reportType: e.target.value })} style={{ ...inp, marginBottom: 0 }}>
              {['Авансовый отчёт', 'Командировочные', 'Мелкий нал', 'Бензин/такси', 'Закупка материалов'].map(type => <option key={type}>{type}</option>)}
            </select>
            <select value={newExpenseReport.employeeName} onChange={e => setNewExpenseReport({ ...newExpenseReport, employeeName: e.target.value })} style={{ ...inp, marginBottom: 0 }}>
              <option value=''>Кому выдано *</option>
              {(staff || []).map(st => <option key={st.id} value={st.name}>{st.name}</option>)}
            </select>
            <select value={newExpenseReport.projectName} onChange={e => setNewExpenseReport({ ...newExpenseReport, projectName: e.target.value })} style={{ ...inp, marginBottom: 0 }}>
              <option value=''>Объект (если по проекту)</option>
              {(projects || []).map(project => <option key={project.id} value={project.name}>{project.name}</option>)}
            </select>
            <input placeholder='Назначение *' value={newExpenseReport.purpose} onChange={e => setNewExpenseReport({ ...newExpenseReport, purpose: e.target.value })} style={{ ...inp, marginBottom: 0 }} />
            <input placeholder='Выдано (₽) *' type='number' step='any' inputMode='decimal' value={newExpenseReport.issuedAmount} onChange={e => setNewExpenseReport({ ...newExpenseReport, issuedAmount: e.target.value })} style={{ ...inp, marginBottom: 0 }} />
            <input placeholder='Потрачено (₽)' type='number' step='any' inputMode='decimal' value={newExpenseReport.spentAmount} onChange={e => setNewExpenseReport({ ...newExpenseReport, spentAmount: e.target.value })} style={{ ...inp, marginBottom: 0 }} />
            <input type='date' value={newExpenseReport.dateFrom} onChange={e => setNewExpenseReport({ ...newExpenseReport, dateFrom: e.target.value })} title='С' style={{ ...inp, marginBottom: 0 }} />
            <input type='date' value={newExpenseReport.dateTo} onChange={e => setNewExpenseReport({ ...newExpenseReport, dateTo: e.target.value })} title='По' style={{ ...inp, marginBottom: 0 }} />
          </div>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              onClick={async () => {
                if (!newExpenseReport.employeeName || !newExpenseReport.purpose || !newExpenseReport.issuedAmount) {
                  alert('Заполните: кому, назначение, выдано');
                  return;
                }
                const issued = Number(newExpenseReport.issuedAmount) || 0;
                const spent = Number(newExpenseReport.spentAmount || 0);
                await fetch(API + '/expense-reports', {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({
                    ...newExpenseReport,
                    issuedAmount: issued,
                    spentAmount: spent,
                    totalAmount: spent || issued,
                    balance: issued - spent,
                    status: 'На утверждении',
                  }),
                });
                await refreshData();
                setNewExpenseReport(null);
              }}
              style={btnO}
            >
              <Check size={14} />
              Сохранить
            </button>
            <button onClick={() => setNewExpenseReport(null)} style={btnG}>Отмена</button>
          </div>
        </div>
      )}
      {expenseReports.length === 0 ? (
        <div style={{ ...card, padding: '30px', textAlign: 'center', color: C.textMuted }}>
          <p>Отчётов нет</p>
          <p style={{ fontSize: '11px' }}>Сотрудник съездил в командировку или потратил мелкий нал → добавьте отчёт для бухгалтерии.</p>
        </div>
      ) : (
        <div>
          {visibleExpenseReports.map(report => (
            <div key={report.id} style={{ ...card, padding: '14px', marginBottom: '8px', borderLeft: '3px solid ' + (report.status === 'Утверждён' ? C.success : report.status === 'Отклонён' ? C.danger : C.warning) }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '10px', flexWrap: 'wrap' }}>
                <div style={{ flex: 1, minWidth: '200px' }}>
                  <b style={{ color: C.text, fontSize: '13px' }}>{report.reportType + ' · ' + report.employeeName}</b>
                  <p style={{ color: C.textSec, margin: '2px 0', fontSize: '12px' }}>{(report.projectName ? report.projectName + ' · ' : '') + report.purpose}</p>
                  <p style={{ color: C.textMuted, margin: 0, fontSize: '11px' }}>
                    Выдано: {Math.round(report.issuedAmount).toLocaleString('ru-RU') + ' ₽'}
                    {' · '}
                    Потрачено: {Math.round(report.spentAmount || 0).toLocaleString('ru-RU') + ' ₽'}
                    {' · '}
                    Остаток: <b style={{ color: Math.round(report.balance) > 0 ? C.success : C.danger }}>{Math.round(report.balance).toLocaleString('ru-RU') + ' ₽'}</b>
                  </p>
                </div>
                <div style={{ display: 'flex', gap: '4px' }}>
                  <span style={badge(report.status === 'Утверждён' ? C.success : report.status === 'Отклонён' ? C.danger : C.warning, report.status === 'Утверждён' ? C.successLight : report.status === 'Отклонён' ? C.dangerLight : C.warningLight, report.status === 'Утверждён' ? C.successBorder : report.status === 'Отклонён' ? C.dangerBorder : C.warningBorder)}>
                    {report.status}
                  </span>
                  {report.status === 'На утверждении' && (
                    <>
                      <button
                        onClick={async () => {
                          await fetch(API + '/expense-reports/' + report.id, {
                            method: 'PUT',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ status: 'Утверждён', approvedBy: user.name, approvedAt: new Date().toISOString().split('T')[0] }),
                          });
                          await refreshData();
                        }}
                        style={{ ...btnG, padding: '4px 8px', fontSize: '11px' }}
                      >
                        ✅
                      </button>
                      <button
                        onClick={async () => {
                          await fetch(API + '/expense-reports/' + report.id, {
                            method: 'PUT',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ status: 'Отклонён', approvedBy: user.name, approvedAt: new Date().toISOString().split('T')[0] }),
                          });
                          await refreshData();
                        }}
                        style={{ ...btnR, padding: '4px 8px', fontSize: '11px' }}
                      >
                        ✕
                      </button>
                    </>
                  )}
                  <button
                    onClick={async () => {
                      if (!window.confirm('Удалить?')) return;
                      await fetch(API + '/expense-reports/' + report.id, { method: 'DELETE' });
                      await refreshData();
                    }}
                    style={{ ...btnR, padding: '4px 8px' }}
                  >
                    <Trash2 size={11} />
                  </button>
                </div>
              </div>
            </div>
          ))}
          {visibleExpenseReports.length < expenseReports.length && (
            <div style={{ ...card, padding: '12px', textAlign: 'center', color: C.textMuted, fontSize: '11px' }}>
              Показаны первые {visibleExpenseReports.length} из {expenseReports.length}. Полный список доступен на компьютере.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
