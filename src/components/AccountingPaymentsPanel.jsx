import React, { useMemo, useState } from 'react';
import { ChevronDown, ChevronUp, DollarSign, Plus, Search } from 'lucide-react';
import AccountingIncomingPaymentForm from './AccountingIncomingPaymentForm';
import SupplierPaymentDeadline from '../features/supply/SupplierPaymentDeadline';
import { createAccountingProjectResolver } from '../utils/accountingProjectIdentity';
import { isSupplierLedgerPayment, projectPaymentOutgoingAmount } from '../utils/projectPaymentUtils';

export default function AccountingPaymentsPanel({
  C,
  card,
  inp,
  btnO,
  btnG,
  btnGr,
  matchSearch,
  listSearch,
  setListSearch,
  projects,
  companyContext = {},
  toNum,
  user,
  refreshData,
  setShowReimburseModal,
  ownExpenses,
  manualExpenses,
  projectPayments,
  projectPaymentInAmount,
  accountablePayments,
  supplierInvoices,
  interimActs,
  expandedProject,
  setExpandedProject,
}) {
  const [showIncomingPaymentForm, setShowIncomingPaymentForm] = useState(false);
  const workPackageLabel = (row) => {
    const value = row?.workPackage || row?.work_package || '';
    return value ? ' · ' + value : '';
  };

  const resolveProjectIdentity = useMemo(
    () => createAccountingProjectResolver(projects, companyContext.companies),
    [projects, companyContext.companies],
  );
  const projectIdentities = Object.create(null);
  const projectKey = (row, name) => {
    const identity = resolveProjectIdentity(row, name);
    projectIdentities[identity.key] = { ...identity,
      needsReview: identity.needsReview || !!projectIdentities[identity.key]?.needsReview };
    return identity.key;
  };
  const allMovesByProject = Object.create(null);
  const emptyMoveGroup = () => ({
    incoming: [],
    projectOut: [],
    ownExp: [],
    manualExp: [],
    accountable: [],
    supplierInv: [],
    actsPaid: [],
    totalIn: 0,
    totalOut: 0,
    supplyDebt: 0,
    actsDebt: 0,
  });
  const ensureMoveGroup = (projectName) => {
    if (!allMovesByProject[projectName]) allMovesByProject[projectName] = emptyMoveGroup();
    if (!allMovesByProject[projectName].manualExp) allMovesByProject[projectName].manualExp = [];
    return allMovesByProject[projectName];
  };
  (projectPayments || []).forEach(payment => {
    const amountIn = isSupplierLedgerPayment(payment) ? 0 : projectPaymentInAmount(payment);
    const outgoingAmount = projectPaymentOutgoingAmount(payment);
    if (amountIn <= 0 && outgoingAmount === 0) return;
    const projectName = projectKey(payment, payment.projectName);
    if (!allMovesByProject[projectName]) {
      allMovesByProject[projectName] = {
        incoming: [],
        projectOut: [],
        ownExp: [],
        accountable: [],
        supplierInv: [],
        actsPaid: [],
        totalIn: 0,
        totalOut: 0,
        supplyDebt: 0,
        actsDebt: 0,
      };
    }
    if (amountIn > 0) {
      allMovesByProject[projectName].incoming.push({ ...payment, _amountIn: amountIn });
      allMovesByProject[projectName].totalIn += amountIn;
    }
    if (outgoingAmount !== 0) {
      allMovesByProject[projectName].projectOut.push({ ...payment, _amountOut: outgoingAmount });
      allMovesByProject[projectName].totalOut += outgoingAmount;
    }
  });
  (ownExpenses || []).filter(expense => expense.status === 'Возмещено').forEach(expense => {
    const projectName = projectKey(expense, expense.projectName);
    if (!allMovesByProject[projectName]) {
      allMovesByProject[projectName] = {
        incoming: [],
        projectOut: [],
        ownExp: [],
        accountable: [],
        supplierInv: [],
        actsPaid: [],
        totalIn: 0,
        totalOut: 0,
        supplyDebt: 0,
        actsDebt: 0,
      };
    }
    allMovesByProject[projectName].ownExp.push(expense);
  });
  (manualExpenses || [])
    .filter(expense => !expense.ownExpenseId && expense.source !== 'own_expense')
    .forEach(expense => {
      const projectName = projectKey(expense, expense.project);
      const group = ensureMoveGroup(projectName);
      group.manualExp.push(expense);
      group.totalOut += Number(expense.amount || 0);
    });
  (accountablePayments || []).forEach(payment => {
    const projectName = projectKey(payment, payment.projectName);
    if (!allMovesByProject[projectName]) {
      allMovesByProject[projectName] = {
        incoming: [],
        projectOut: [],
        ownExp: [],
        accountable: [],
        supplierInv: [],
        actsPaid: [],
        totalIn: 0,
        totalOut: 0,
        supplyDebt: 0,
        actsDebt: 0,
      };
    }
    allMovesByProject[projectName].accountable.push(payment);
    allMovesByProject[projectName].totalOut += Number(payment.amount || 0);
  });
  (supplierInvoices || []).forEach(invoice => {
    if (invoice.accountingRequired === false) return;
    const projectName = projectKey(invoice, invoice.projectName);
    if (!allMovesByProject[projectName]) {
      allMovesByProject[projectName] = {
        incoming: [],
        projectOut: [],
        ownExp: [],
        accountable: [],
        supplierInv: [],
        actsPaid: [],
        totalIn: 0,
        totalOut: 0,
        supplyDebt: 0,
        actsDebt: 0,
      };
    }
    allMovesByProject[projectName].supplierInv.push(invoice);
    const paid = Number(invoice.paidAmount || 0);
    const total = Number(invoice.totalAmount || 0);
    if (invoice.status !== 'Аннулирован') allMovesByProject[projectName].supplyDebt += Math.max(0, total - paid);
  });
  (interimActs || []).forEach(act => {
    const projectName = projectKey(act, act.project);
    if (!allMovesByProject[projectName]) {
      allMovesByProject[projectName] = {
        incoming: [],
        projectOut: [],
        ownExp: [],
        accountable: [],
        supplierInv: [],
        actsPaid: [],
        totalIn: 0,
        totalOut: 0,
        supplyDebt: 0,
        actsDebt: 0,
      };
    }
    const paid = Number(act.paidAmount || 0);
    const total = Number(act.totalAmount || 0);
    allMovesByProject[projectName].actsPaid.push(act);
    if (paid < total) allMovesByProject[projectName].actsDebt += (total - paid);
  });

  const projectNames = Object.keys(allMovesByProject).sort((left, right) =>
    (projectIdentities[left].companyLabel + projectIdentities[left].projectName)
      .localeCompare(projectIdentities[right].companyLabel + projectIdentities[right].projectName, 'ru'));
  const pendingReimburseCount = (ownExpenses || []).filter(expense => expense.status === 'Ожидает').length;
  const totalIncoming = projectNames.reduce((sum, projectName) => sum + allMovesByProject[projectName].totalIn, 0);
  const totalOutgoing = projectNames.reduce((sum, projectName) => sum + allMovesByProject[projectName].totalOut, 0);
  const totalSupplyDebt = projectNames.reduce((sum, projectName) => sum + allMovesByProject[projectName].supplyDebt, 0);
  const totalActsDebt = projectNames.reduce((sum, projectName) => sum + allMovesByProject[projectName].actsDebt, 0);

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px', flexWrap: 'wrap', gap: '10px' }}>
        <b style={{ color: C.text, fontSize: '15px', fontWeight: '700' }}>💸 Платежи по объектам</b>
        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
          <button
            onClick={() => setShowIncomingPaymentForm(true)}
            style={btnO}
          >
            <Plus size={14} />
            Поступление
          </button>
          <button onClick={() => setShowReimburseModal(true)} style={{ ...btnGr, position: 'relative' }}>
            <DollarSign size={14} />
            Возместить сотруднику
            {pendingReimburseCount > 0 && (
              <span style={{
                position: 'absolute',
                top: '-6px',
                right: '-6px',
                backgroundColor: '#ef4444',
                color: 'white',
                borderRadius: '50%',
                padding: '1px 6px',
                fontSize: '10px',
                fontWeight: '700',
              }}>
                {pendingReimburseCount}
              </span>
            )}
          </button>
        </div>
      </div>

      {showIncomingPaymentForm && <AccountingIncomingPaymentForm
        key={companyContext.mode + ':' + companyContext.selectedCompanyId}
        C={C} card={card} inp={inp} btnO={btnO} btnG={btnG || btnGr}
        projects={projects} companyContext={companyContext} user={user}
        onClose={() => setShowIncomingPaymentForm(false)} refreshData={refreshData}
      />}

      {projectNames.length === 0 ? (
        <div style={{ ...card, padding: '40px', textAlign: 'center', color: C.textMuted }}>
          Движений денег пока нет
        </div>
      ) : (
        <div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(170px,1fr))', gap: '10px', marginBottom: '18px' }}>
            <div style={{ ...card, padding: '12px', backgroundColor: C.successLight, border: '1.5px solid ' + C.successBorder }}>
              <p style={{ color: C.success, fontSize: '11px', margin: '0 0 4px' }}>Поступило от заказчиков</p>
              <b style={{ color: C.success, fontSize: '15px' }}>{Math.round(totalIncoming).toLocaleString('ru-RU') + ' ₽'}</b>
            </div>
            <div style={{ ...card, padding: '12px', backgroundColor: C.dangerLight, border: '1.5px solid ' + C.dangerBorder }}>
              <p style={{ color: C.danger, fontSize: '11px', margin: '0 0 4px' }}>Расходов оплачено</p>
              <b style={{ color: C.danger, fontSize: '15px' }}>{Math.round(totalOutgoing).toLocaleString('ru-RU') + ' ₽'}</b>
            </div>
            {totalSupplyDebt > 0 && (
              <div style={{ ...card, padding: '12px', backgroundColor: C.warningLight, border: '1.5px solid ' + C.warningBorder }}>
                <p style={{ color: C.warning, fontSize: '11px', margin: '0 0 4px' }}>⚠️ Долг поставщикам</p>
                <b style={{ color: C.warning, fontSize: '15px' }}>{Math.round(totalSupplyDebt).toLocaleString('ru-RU') + ' ₽'}</b>
              </div>
            )}
            {totalActsDebt > 0 && (
              <div style={{ ...card, padding: '12px', backgroundColor: C.warningLight, border: '1.5px solid ' + C.warningBorder }}>
                <p style={{ color: C.warning, fontSize: '11px', margin: '0 0 4px' }}>⚠️ Долг по актам мастерам</p>
                <b style={{ color: C.warning, fontSize: '15px' }}>{Math.round(totalActsDebt).toLocaleString('ru-RU') + ' ₽'}</b>
              </div>
            )}
          </div>

          <div style={{ position: 'relative', marginBottom: '12px' }}>
            <Search size={13} style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: C.textMuted }} />
            <input
              placeholder="🔍 Поиск по компании или объекту"
              value={listSearch}
              onChange={e => setListSearch(e.target.value)}
              style={{ ...inp, marginBottom: 0, paddingLeft: '30px', fontSize: '12px', padding: '6px 8px 6px 30px' }}
            />
          </div>

          {projectNames.filter(key => matchSearch(listSearch,
            projectIdentities[key].companyLabel + ' ' + projectIdentities[key].projectName + ' ' + (projectIdentities[key].projectId || ''))).map(projectName => {
            const group = allMovesByProject[projectName];
            const identity = projectIdentities[projectName];
            const isOpen = expandedProject === 'pay-' + projectName;
            const balance = group.totalIn - group.totalOut;

            return (
              <div key={projectName} style={{ ...card, marginBottom: '8px', borderLeft: '3px solid ' + (balance >= 0 ? C.success : C.danger) }}>
                <div
                  role="button"
                  tabIndex={0}
                  aria-expanded={isOpen}
                  onKeyDown={event => {
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault();
                      setExpandedProject(isOpen ? null : 'pay-' + projectName);
                    }
                  }}
                  style={{ padding: '12px 14px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', cursor: 'pointer', gap: '10px', flexWrap: 'wrap' }}
                  onClick={() => setExpandedProject(isOpen ? null : 'pay-' + projectName)}
                >
                  <div>
                    <b style={{ color: C.text, fontSize: '13px' }}>🏗 {identity.projectName}</b>
                    <p style={{ color: C.textSec, margin: '4px 0', fontSize: '12px', overflowWrap: 'anywhere' }}>
                      {identity.companyLabel}{identity.projectId ? ' · Объект #' + identity.projectId : ''}
                    </p>
                    {identity.needsReview && <p style={{ color: C.warning, fontSize: '11px', margin: '4px 0' }}>
                      Принадлежность записей требует проверки: нет полных ID или объект найден только по названию.
                    </p>}
                    <p style={{ color: C.textSec, margin: '2px 0', fontSize: '11px' }}>
                      Поступило: <b style={{ color: C.success }}>{Math.round(group.totalIn).toLocaleString('ru-RU')} ₽</b>
                      {' · '}
                      Оплачено: <b style={{ color: C.danger }}>{Math.round(group.totalOut).toLocaleString('ru-RU')} ₽</b>
                      {group.supplyDebt > 0 && <><span style={{ color: C.warning }}> · ⚠️ долг постав. {Math.round(group.supplyDebt).toLocaleString('ru-RU')} ₽</span></>}
                      {group.actsDebt > 0 && <><span style={{ color: C.warning }}> · ⚠️ долг мастерам {Math.round(group.actsDebt).toLocaleString('ru-RU')} ₽</span></>}
                    </p>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <b style={{ color: balance >= 0 ? C.success : C.danger, fontSize: '15px' }}>
                      {(balance >= 0 ? '+' : '') + Math.round(balance).toLocaleString('ru-RU') + ' ₽'}
                    </b>
                    {isOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                  </div>
                </div>

                {isOpen && (
                  <div style={{ borderTop: '1px solid ' + C.border, padding: '10px 14px', fontSize: '11px' }}>
                    {group.incoming.length > 0 && (
                      <details style={{ marginBottom: '6px' }}>
                        <summary style={{ cursor: 'pointer', padding: '4px 0', color: C.success, fontWeight: '600' }}>
                          ↘️ Поступления ({group.incoming.length}) — {Math.round(group.totalIn).toLocaleString('ru-RU')} ₽
                        </summary>
                        {group.incoming.map((payment, index) => (
                          <div key={index} style={{ padding: '4px 10px', color: C.textSec, display: 'flex', justifyContent: 'space-between', borderBottom: '1px dashed ' + C.border }}>
                            <span>{(payment.date || '—') + workPackageLabel(payment) + (payment.note ? ' · ' + payment.note : '') + (payment.paidBy ? ' · ' + payment.paidBy : '')}</span>
                            <b style={{ color: C.success }}>{Math.round(Number(payment._amountIn || 0)).toLocaleString('ru-RU') + ' ₽'}</b>
                          </div>
                        ))}
                      </details>
                    )}

                    {group.projectOut.length > 0 && (
                      <details style={{ marginBottom: '6px' }}>
                        <summary style={{ cursor: 'pointer', padding: '4px 0', color: C.danger, fontWeight: '600' }}>
                          ↗️ Выплаты и расходы ({group.projectOut.length}) — {Math.round(group.projectOut.reduce((sum, payment) => sum + Number(payment._amountOut || 0), 0)).toLocaleString('ru-RU')} ₽
                        </summary>
                        {group.projectOut.map((payment, index) => (
                          <div key={payment.id || index} style={{ padding: '4px 10px', color: C.textSec, display: 'flex', justifyContent: 'space-between', gap: '8px', borderBottom: '1px dashed ' + C.border }}>
                            <span>{(isSupplierLedgerPayment(payment) && payment.operationKind === 'reversal' ? 'Сторно · ' : '') + (payment.date || '—') + workPackageLabel(payment) + (payment.note ? ' · ' + payment.note : '') + (payment.addedBy ? ' · ' + payment.addedBy : '')}</span>
                            <b style={{ color: C.danger }}>{Math.round(Number(payment._amountOut || 0)).toLocaleString('ru-RU') + ' ₽'}</b>
                          </div>
                        ))}
                      </details>
                    )}

                    {group.supplierInv.length > 0 && (
                      <details style={{ marginBottom: '6px' }}>
                        <summary style={{ cursor: 'pointer', padding: '4px 0', color: C.info, fontWeight: '600' }}>
                          📥 Счета поставщиков ({group.supplierInv.length})
                        </summary>
                        {group.supplierInv.map(invoice => {
                          const paid = Number(invoice.paidAmount || 0);
                          const total = Number(invoice.totalAmount || 0);
                          const owe = invoice.status === 'Аннулирован' ? 0 : Math.max(0, total - paid);
                          return (
                            <div key={invoice.id} style={{ padding: '4px 10px', overflowWrap: 'anywhere', borderBottom: '1px dashed ' + C.border }}>
                              <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', gap: '8px' }}>
                                <span style={{ color: C.textSec }}>
                                  {(invoice.supplierName || '—') + ' · ' + (invoice.invoiceNumber || 'без №') + ' · ' + (invoice.invoiceDate || invoice.date || '')}
                                </span>
                                <span>
                                  <b style={{ color: C.text }}>{Math.round(total).toLocaleString('ru-RU') + ' ₽'}</b>
                                  {paid > 0 && <span style={{ color: C.success, marginLeft: '4px' }}>(опл. {Math.round(paid).toLocaleString('ru-RU')})</span>}
                                  {owe > 0 && <b style={{ color: C.danger, marginLeft: '4px' }}>⚠️ долг {Math.round(owe).toLocaleString('ru-RU')}</b>}
                                </span>
                              </div>
                              {invoice.paymentDeadline != null && (
                                <SupplierPaymentDeadline value={invoice.paymentDeadline.invoiceId === invoice.id
                                  ? invoice.paymentDeadline : { status: 'review_required' }} />
                              )}
                            </div>
                          );
                        })}
                      </details>
                    )}

                    {(group.manualExp || []).length > 0 && (
                      <details style={{ marginBottom: '6px' }}>
                        <summary style={{ cursor: 'pointer', padding: '4px 0', color: C.danger, fontWeight: '600' }}>
                          🧾 Прямые расходы объекта ({group.manualExp.length}) — {Math.round(group.manualExp.reduce((sum, expense) => sum + Number(expense.amount || 0), 0)).toLocaleString('ru-RU')} ₽
                        </summary>
                        {group.manualExp.map(expense => (
                          <div key={expense.id} style={{ padding: '4px 10px', color: C.textSec, display: 'flex', justifyContent: 'space-between', gap: '8px', borderBottom: '1px dashed ' + C.border }}>
                            <span>{(expense.date || '—') + ' · ' + (expense.category || 'Расход') + (expense.note ? ' · ' + expense.note : '') + (expense.addedBy ? ' · ' + expense.addedBy : '')}</span>
                            <b style={{ color: C.danger }}>{Math.round(Number(expense.amount || 0)).toLocaleString('ru-RU') + ' ₽'}</b>
                          </div>
                        ))}
                      </details>
                    )}

                    {group.actsPaid.length > 0 && (
                      <details style={{ marginBottom: '6px' }}>
                        <summary style={{ cursor: 'pointer', padding: '4px 0', color: C.accent, fontWeight: '600' }}>
                          📄 Акты мастеров ({group.actsPaid.length})
                        </summary>
                        {group.actsPaid.map(act => {
                          const paid = Number(act.paidAmount || 0);
                          const total = Number(act.totalAmount || 0);
                          const owe = Math.max(0, total - paid);
                          return (
                            <div key={act.id} style={{ padding: '4px 10px', display: 'flex', justifyContent: 'space-between', gap: '8px', borderBottom: '1px dashed ' + C.border }}>
                              <span style={{ color: C.textSec }}>
                                {'№' + act.id + ' · ' + (act.masterName || '—') + ' · ' + (act.periodStart || '') + '—' + (act.periodEnd || '')}
                              </span>
                              <span>
                                <b style={{ color: C.text }}>{Math.round(total).toLocaleString('ru-RU') + ' ₽'}</b>
                                {paid > 0 && <span style={{ color: C.success, marginLeft: '4px' }}>(опл. {Math.round(paid).toLocaleString('ru-RU')})</span>}
                                {owe > 0 && <b style={{ color: C.danger, marginLeft: '4px' }}>⚠️ долг {Math.round(owe).toLocaleString('ru-RU')}</b>}
                              </span>
                            </div>
                          );
                        })}
                      </details>
                    )}

                    {group.accountable.length > 0 && (
                      <details style={{ marginBottom: '6px' }}>
                        <summary style={{ cursor: 'pointer', padding: '4px 0', color: C.warning, fontWeight: '600' }}>
                          💵 Подотчётные ({group.accountable.length})
                        </summary>
                        {group.accountable.map(payment => (
                          <div key={payment.id} style={{ padding: '4px 10px', color: C.textSec, display: 'flex', justifyContent: 'space-between', borderBottom: '1px dashed ' + C.border }}>
                            <span>{(payment.givenTo || '—') + ' · ' + (payment.date || '') + (payment.purpose ? ' · ' + payment.purpose : '')}</span>
                            <b style={{ color: C.warning }}>{Math.round(Number(payment.amount || 0)).toLocaleString('ru-RU') + ' ₽'}</b>
                          </div>
                        ))}
                      </details>
                    )}

                    {group.ownExp.length > 0 && (
                      <details>
                        <summary style={{ cursor: 'pointer', padding: '4px 0', color: C.textSec, fontWeight: '600' }}>
                          💸 Возмещения сотрудникам ({group.ownExp.length})
                        </summary>
                        {group.ownExp.map(expense => (
                          <div key={expense.id} style={{ padding: '4px 10px', color: C.textSec, display: 'flex', justifyContent: 'space-between', borderBottom: '1px dashed ' + C.border }}>
                            <span>{(expense.employeeName || '—') + ' · ' + (expense.description || '') + ' · ' + (expense.date || '')}</span>
                            <b>{Math.round(Number(expense.amount || 0)).toLocaleString('ru-RU') + ' ₽'}</b>
                          </div>
                        ))}
                      </details>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
