import React, { useMemo, useState } from 'react';
import { CheckCircle2, CreditCard, FileText, Printer, Save, Search } from 'lucide-react';
import { API } from '../api';

const toNumber = value => Number(String(value ?? 0).replace(',', '.')) || 0;
const money = value => Math.round(toNumber(value)).toLocaleString('ru-RU') + ' ₽';
const safeText = value => String(value ?? '').trim();
const monthNow = () => new Date().toISOString().slice(0, 7);
const dateOnly = value => safeText(value).split('T')[0];
const monthOf = value => dateOnly(value).slice(0, 7);
const personKey = value => safeText(value).toLowerCase().replace(/\s+/g, ' ');
const workExecutionTotal = work => toNumber(work?.executionTotal ?? work?.execution_total ?? 0);
const workCustomerTotal = work => toNumber(work?.customerTotal ?? work?.customer_total ?? work?.total);
const periodStartForMonth = month => month ? month + '-01' : '';
const periodEndForMonth = month => {
  if (!month) return '';
  const [year, monthNumber] = month.split('-').map(Number);
  if (!year || !monthNumber) return '';
  return new Date(Date.UTC(year, monthNumber, 0)).toISOString().slice(0, 10);
};

const isContractorLike = staffRow => {
  const raw = [
    staffRow?.role,
    staffRow?.employmentType,
    staffRow?.payType,
    staffRow?.contractType,
    staffRow?.specialization,
  ].map(value => safeText(value).toLowerCase()).join(' ');
  return ['суб', 'подряд', 'ип', 'ооо', 'самозан', 'бригад'].some(key => raw.includes(key));
};

const matchByPerson = (payment, performer) => {
  const id = Number(performer.staffId || performer.masterId || 0);
  const name = personKey(performer.performerName);
  return (
    (id && [payment.recipientId, payment.employeeId, payment.staffId, payment.masterId, payment.userId].some(value => Number(value) === id)) ||
    [payment.recipientName, payment.employeeName, payment.masterName, payment.givenTo, payment.name].some(value => personKey(value) === name)
  );
};

const paymentSignedAmount = payment => Number(payment?.amount || 0);
const performerPaymentNote = ({ performerName, month, workPackage }) =>
  'Выплата исполнителю: ' + performerName + ' · ' + month + (workPackage ? ' · ' + workPackage : '');

const performerPaymentAmount = (payment, group, month) => {
  const amount = paymentSignedAmount(payment);
  if (amount >= 0) return 0;
  if (safeText(payment.projectName || payment.project) !== group.project) return 0;
  const note = safeText(payment.note);
  if (!note.startsWith('Выплата исполнителю:')) return 0;
  if (!note.includes(group.performerName) || !note.includes(month)) return 0;
  if (group.workPackage && safeText(payment.workPackage || payment.work_package) && safeText(payment.workPackage || payment.work_package) !== group.workPackage) return 0;
  if (group.workPackage && !safeText(payment.workPackage || payment.work_package) && !note.includes(group.workPackage)) return 0;
  return Math.abs(amount);
};

const buildPrintHtml = ({ month, rows, summary }) => {
  const title = 'Реестр закрытия исполнителей за ' + month;
  const body = rows.map((row, index) => (
    '<tr>' +
      '<td>' + (index + 1) + '</td>' +
      '<td>' + row.project + '</td>' +
      '<td>' + row.performerName + '</td>' +
      '<td>' + row.workPackage + '</td>' +
      '<td>' + row.roomName + '</td>' +
      '<td>' + row.description + '</td>' +
      '<td>' + row.quantity + ' ' + row.unit + '</td>' +
      '<td>' + money(row.unitPrice) + '</td>' +
      '<td>' + money(row.executionTotal) + '</td>' +
      '<td>' + money(row.customerTotal) + '</td>' +
    '</tr>'
  )).join('');
  return (
    '<h2 style="text-align:center">' + title + '</h2>' +
    '<p><b>Начислено:</b> ' + money(summary.accrued) +
    ' &nbsp; <b>Авансы:</b> ' + money(summary.advances) +
    ' &nbsp; <b>Удержание:</b> ' + money(summary.retention) +
    ' &nbsp; <b>Выплачено:</b> ' + money(summary.paid) +
    ' &nbsp; <b>К выплате:</b> ' + money(summary.payable) + '</p>' +
    '<table><tr><th>N</th><th>Объект</th><th>Исполнитель</th><th>Пакет</th><th>Помещение</th><th>Работа</th><th>Объем</th><th>Цена исп.</th><th>Начислено</th><th>Заказчик</th></tr>' +
    (body || '<tr><td colspan="10" style="text-align:center;color:#777">Нет подтвержденных работ за период</td></tr>') +
    '</table>' +
    '<p style="margin-top:24px">Бухгалтер ____________________ / ____________________</p>' +
    '<p>Руководитель ____________________ / ____________________</p>' +
    '<p style="font-size:10px;color:#666">Ведомость сформирована из подтвержденного журнала производства работ. Удержание применяется расчетно по исполнителям с типом субподрядчик/ИП/ООО/самозанятый.</p>'
  );
};

export default function AccountingPerformerClosingPanel({
  C,
  card,
  inp,
  btnG,
  btnB,
  tbl,
  tblH,
  tblC,
  workJournal,
  staff,
  accountablePayments,
  ownExpenses,
  projects,
  listSearch,
  setListSearch,
  matchSearch,
  showPreview,
  interimActs,
  contracts,
  refreshData,
  btnO,
  projectPayments,
  user,
}) {
  const [month, setMonth] = useState(monthNow());
  const [projectFilter, setProjectFilter] = useState('');
  const [performerFilter, setPerformerFilter] = useState('');
  const [expandedKey, setExpandedKey] = useState('');
  const [savingKey, setSavingKey] = useState('');

  const periodStart = periodStartForMonth(month);
  const periodEnd = periodEndForMonth(month);

  const staffById = useMemo(() => {
    const map = {};
    (staff || []).forEach(row => { if (row.id) map[Number(row.id)] = row; });
    return map;
  }, [staff]);

  const rows = useMemo(() => {
    return (workJournal || [])
      .filter(work => safeText(work.status) === 'Подтверждено')
      .filter(work => monthOf(work.confirmedAt || work.date) === month)
      .map(work => {
        const staffRow = staffById[Number(work.masterId || 0)] || {};
        const executionTotal = workExecutionTotal(work);
        const qty = toNumber(work.quantity);
        return {
          id: work.id,
          date: dateOnly(work.confirmedAt || work.date),
          project: safeText(work.project) || 'Без объекта',
          performerName: safeText(work.masterName || work.master_name || staffRow.name) || 'Без исполнителя',
          staffId: Number(work.masterId || staffRow.id || 0),
          workPackage: safeText(work.workPackage || work.work_package) || 'Основная',
          roomName: safeText(work.roomName || work.room_name) || 'Без помещения',
          description: safeText(work.description),
          unit: safeText(work.unit),
          quantity: qty,
          unitPrice: toNumber(work.executionPricePerUnit || work.pricePerUnit) || (qty > 0 ? executionTotal / qty : 0),
          executionTotal,
          customerTotal: workCustomerTotal(work),
          isContractor: isContractorLike(staffRow),
        };
      })
      .filter(row => row.roomName !== 'Без помещения')
      .filter(row => row.executionTotal > 0)
      .filter(row => !projectFilter || row.project === projectFilter)
      .filter(row => !performerFilter || row.performerName === performerFilter)
      .filter(row => matchSearch ? matchSearch(listSearch, row.performerName, row.project, row.workPackage, row.roomName, row.description) : true)
      .sort((a, b) => (a.performerName + a.project + a.date).localeCompare(b.performerName + b.project + b.date));
  }, [workJournal, staffById, month, projectFilter, performerFilter, listSearch, matchSearch]);

  const blockedRows = useMemo(() => {
    return (workJournal || [])
      .filter(work => safeText(work.status) === 'Подтверждено')
      .filter(work => monthOf(work.confirmedAt || work.date) === month)
      .filter(work => !safeText(work.roomName || work.room_name) || workExecutionTotal(work) <= 0);
  }, [workJournal, month]);

  const groups = useMemo(() => {
    const byKey = {};
    rows.forEach(row => {
      const performerKey = row.staffId ? 'staff:' + row.staffId : 'name:' + personKey(row.performerName);
      const key = performerKey + '|' + row.project + '|' + row.workPackage;
      if (!byKey[key]) {
        byKey[key] = {
          key,
          performerName: row.performerName,
          project: row.project,
          workPackage: row.workPackage,
          staffId: row.staffId,
          isContractor: row.isContractor,
          rows: [],
          accrued: 0,
          customer: 0,
        };
      }
      byKey[key].rows.push(row);
      byKey[key].accrued += row.executionTotal;
      byKey[key].customer += row.customerTotal;
    });
    Object.values(byKey).forEach(group => {
      const performer = { performerName: group.performerName, staffId: group.staffId };
      const advances = (accountablePayments || [])
        .filter(payment => monthOf(payment.date || payment.createdAt) === month)
        .filter(payment => !projectFilter || (payment.projectName || payment.project) === group.project)
        .filter(payment => (payment.projectName || payment.project || group.project) === group.project)
        .filter(payment => matchByPerson(payment, performer))
        .reduce((sum, payment) => sum + toNumber(payment.amount), 0);
      const reimbursements = (ownExpenses || [])
        .filter(expense => monthOf(expense.date || expense.createdAt) === month)
        .filter(expense => (expense.projectName || expense.project || group.project) === group.project)
        .filter(expense => safeText(expense.status) === 'Возмещено')
        .filter(expense => matchByPerson(expense, performer))
        .reduce((sum, expense) => sum + toNumber(expense.amount), 0);
      const paid = (projectPayments || [])
        .reduce((sum, payment) => sum + performerPaymentAmount(payment, group, month), 0);
      group.advances = advances;
      group.reimbursements = reimbursements;
      group.retention = group.isContractor ? Math.round(group.accrued * 0.05) : 0;
      group.paid = paid;
      group.payable = Math.max(0, group.accrued - group.advances - group.retention - group.paid);
      group.margin = group.customer - group.accrued;
    });
    return Object.values(byKey).sort((a, b) => b.accrued - a.accrued);
  }, [rows, accountablePayments, ownExpenses, projectPayments, month, projectFilter]);

  const performerNames = useMemo(() => [...new Set((workJournal || []).map(work => safeText(work.masterName || work.master_name)).filter(Boolean))].sort(), [workJournal]);
  const projectNames = useMemo(() => [...new Set([...(projects || []).map(project => safeText(project.name)), ...(workJournal || []).map(work => safeText(work.project))].filter(Boolean))].sort(), [projects, workJournal]);

  const summary = groups.reduce((acc, group) => {
    acc.accrued += group.accrued;
    acc.customer += group.customer;
    acc.advances += group.advances;
    acc.retention += group.retention;
    acc.paid += group.paid;
    acc.payable += group.payable;
    acc.margin += group.margin;
    return acc;
  }, { accrued: 0, customer: 0, advances: 0, retention: 0, paid: 0, payable: 0, margin: 0 });

  const actGroups = useMemo(() => {
    return groups.map(group => ({
      key: group.key,
      staffId: group.staffId,
      performerName: group.performerName,
      project: group.project,
      workPackage: group.workPackage,
      workPackages: group.workPackage,
      accrued: group.accrued,
      rows: group.rows.length,
      workJournalIds: group.rows.map(row => row.id).filter(Boolean),
    }));
  }, [groups]);

  const existingActFor = (staffId, performerName, project, workPackage) => {
    const normalizedName = personKey(performerName);
    const normalizedPackage = safeText(workPackage || 'Основная');
    return (interimActs || []).find(act => {
      if (safeText(act.status) === 'Аннулирован') return false;
      if (safeText(act.project) !== safeText(project)) return false;
      if (safeText(act.workPackage || act.work_package || 'Основная') !== normalizedPackage) return false;
      if (dateOnly(act.periodStart) !== periodStart || dateOnly(act.periodEnd) !== periodEnd) return false;
      const idMatch = staffId && Number(act.masterId) === Number(staffId);
      const nameMatch = personKey(act.masterName) === normalizedName;
      return idMatch || nameMatch;
    });
  };

  const saveClosingAct = async actGroup => {
    if (!actGroup || !actGroup.project || !periodStart || !periodEnd || savingKey) return;
    const existingAct = existingActFor(actGroup.staffId, actGroup.performerName, actGroup.project, actGroup.workPackage);
    if (existingAct) {
      window.alert('Акт за этот месяц уже зафиксирован во вкладке «Акты».');
      return;
    }
    setSavingKey(actGroup.key);
    try {
      const contract = (contracts || []).find(item =>
        Number(item.masterId) === Number(actGroup.staffId) &&
        safeText(item.project) === safeText(actGroup.project) &&
        safeText(item.status) !== 'Аннулирован'
      );
      const response = await fetch(API + '/interim-acts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          masterId: Number(actGroup.staffId) || 0,
          masterName: actGroup.performerName,
          project: actGroup.project,
          workPackage: actGroup.workPackage || 'Основная',
          periodStart,
          periodEnd,
          totalAmount: Math.round(actGroup.accrued * 100) / 100,
          paidAmount: 0,
          contractId: contract ? contract.id : null,
          workJournalIds: actGroup.workJournalIds || [],
        }),
      });
      if (!response.ok) throw new Error(await response.text());
      await refreshData?.();
    } catch (error) {
      window.alert('Не удалось зафиксировать акт: ' + (error?.message || error));
    } finally {
      setSavingKey('');
    }
  };

  const saveAllClosingActs = async () => {
    const unsaved = actGroups.filter(group => !existingActFor(group.staffId, group.performerName, group.project, group.workPackage));
    for (const group of unsaved) {
      await saveClosingAct(group);
    }
  };

  const payPerformerGroup = async group => {
    if (!group?.project || group.payable <= 0) return;
    const savedAct = existingActFor(group.staffId, group.performerName, group.project, group.workPackage);
    if (!savedAct) {
      window.alert('Сначала зафиксируйте акт по подтверждённым работам. Оплата без акта заблокирована.');
      return;
    }
    const defaultAmount = Math.round(group.payable * 100) / 100;
    const raw = window.prompt(
      'Сумма выплаты исполнителю ' + group.performerName + ' за ' + month + ':',
      String(defaultAmount)
    );
    if (!raw) return;
    const amount = toNumber(raw);
    if (amount <= 0) return;
    if (amount > group.payable && !window.confirm('Сумма больше остатка к выплате. Всё равно провести?')) return;
    try {
      const response = await fetch(API + '/interim-acts/' + savedAct.id + '/pay', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          amount,
          note: performerPaymentNote({ ...group, month }) + ' · акт #' + savedAct.id,
          paidDate: new Date().toISOString().split('T')[0],
          paidBy: user?.name || '',
        }),
      });
      if (!response.ok) throw new Error(await response.text());
      await refreshData?.();
    } catch (error) {
      window.alert('Не удалось провести выплату: ' + (error?.message || error));
    }
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px', flexWrap: 'wrap', gap: '8px' }}>
        <div>
          <b style={{ color: C.text, fontSize: '15px' }}>📘 Закрытие исполнителей</b>
          <p style={{ color: C.textSec, margin: '3px 0 0', fontSize: '12px' }}>Подтвержденные работы ЖПР → акт/реестр бухгалтерии → авансы, удержания, остаток к выплате.</p>
        </div>
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          <button
            onClick={saveAllClosingActs}
            disabled={savingKey || actGroups.every(group => existingActFor(group.staffId, group.performerName, group.project, group.workPackage))}
            style={{
              ...(btnO || btnG),
              opacity: savingKey || actGroups.every(group => existingActFor(group.staffId, group.performerName, group.project, group.workPackage)) ? 0.55 : 1,
            }}
          >
            <Save size={14} />
            Зафиксировать месяц
          </button>
          <button
            onClick={() => showPreview && showPreview(buildPrintHtml({ month, rows, summary }), 'Реестр закрытия исполнителей — ' + month)}
            style={btnB}
          >
            <Printer size={14} />
            Печать реестра
          </button>
        </div>
      </div>

      <div style={{ ...card, padding: '14px', marginBottom: '14px', backgroundColor: C.bg }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(180px,1fr))', gap: '10px' }}>
          <input type="month" value={month} onChange={event => setMonth(event.target.value)} style={{ ...inp, marginBottom: 0 }} />
          <select value={projectFilter} onChange={event => setProjectFilter(event.target.value)} style={{ ...inp, marginBottom: 0 }}>
            <option value="">Все объекты</option>
            {projectNames.map(name => <option key={name} value={name}>{name}</option>)}
          </select>
          <select value={performerFilter} onChange={event => setPerformerFilter(event.target.value)} style={{ ...inp, marginBottom: 0 }}>
            <option value="">Все исполнители</option>
            {performerNames.map(name => <option key={name} value={name}>{name}</option>)}
          </select>
          <div style={{ position: 'relative' }}>
            <Search size={14} style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: C.textMuted }} />
            <input placeholder="Поиск по работе, помещению, исполнителю" value={listSearch} onChange={event => setListSearch(event.target.value)} style={{ ...inp, marginBottom: 0, paddingLeft: '32px' }} />
          </div>
        </div>
        {blockedRows.length > 0 && (
          <p style={{ color: C.warning, margin: '10px 0 0', fontSize: '12px', fontWeight: 700 }}>
            Не попадут в акт: {blockedRows.length} подтверждённых строк без помещения или исполнительской суммы. Исправьте ЖПР перед закрытием месяца.
          </p>
        )}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(150px,1fr))', gap: '10px', marginBottom: '14px' }}>
        <div style={{ ...card, padding: '12px', backgroundColor: C.bg }}><p style={{ color: C.textSec, margin: '0 0 4px', fontSize: '11px' }}>Исполнителей/пакетов</p><b style={{ color: C.text }}>{groups.length}</b></div>
        <div style={{ ...card, padding: '12px', backgroundColor: C.successLight }}><p style={{ color: C.success, margin: '0 0 4px', fontSize: '11px' }}>Начислено</p><b style={{ color: C.success }}>{money(summary.accrued)}</b></div>
        <div style={{ ...card, padding: '12px', backgroundColor: C.warningLight }}><p style={{ color: C.warning, margin: '0 0 4px', fontSize: '11px' }}>Авансы/подотчет</p><b style={{ color: C.warning }}>{money(summary.advances)}</b></div>
        <div style={{ ...card, padding: '12px', backgroundColor: C.warningLight }}><p style={{ color: C.warning, margin: '0 0 4px', fontSize: '11px' }}>Гарантийное удержание</p><b style={{ color: C.warning }}>{money(summary.retention)}</b></div>
        <div style={{ ...card, padding: '12px', backgroundColor: C.bg }}><p style={{ color: C.textSec, margin: '0 0 4px', fontSize: '11px' }}>Уже выплачено</p><b style={{ color: C.text }}>{money(summary.paid)}</b></div>
        <div style={{ ...card, padding: '12px', backgroundColor: C.infoLight }}><p style={{ color: C.info, margin: '0 0 4px', fontSize: '11px' }}>К выплате</p><b style={{ color: C.info }}>{money(summary.payable)}</b></div>
        <div style={{ ...card, padding: '12px', backgroundColor: summary.margin >= 0 ? C.successLight : C.dangerLight }}><p style={{ color: summary.margin >= 0 ? C.success : C.danger, margin: '0 0 4px', fontSize: '11px' }}>Разница заказчик/исполнитель</p><b style={{ color: summary.margin >= 0 ? C.success : C.danger }}>{money(summary.margin)}</b></div>
      </div>

      {groups.length === 0 ? (
        <div style={{ ...card, padding: '28px', textAlign: 'center', color: C.textMuted }}>
          Подтвержденных работ за выбранный период нет.
        </div>
      ) : (
        groups.map(group => {
          const open = expandedKey === group.key;
          const actGroup = actGroups.find(item =>
            item.project === group.project &&
            item.workPackage === group.workPackage &&
            item.performerName === group.performerName &&
            Number(item.staffId || 0) === Number(group.staffId || 0)
          );
          const savedAct = existingActFor(group.staffId, group.performerName, group.project, group.workPackage);
          return (
            <div key={group.key} style={{ ...card, padding: 0, marginBottom: '10px', overflow: 'hidden', borderLeft: '3px solid ' + (group.payable > 0 ? C.accent : C.success) }}>
              <div
                onClick={() => setExpandedKey(open ? '' : group.key)}
                style={{ padding: '14px', display: 'grid', gridTemplateColumns: 'minmax(220px,1fr) repeat(5,minmax(100px,auto))', gap: '10px', alignItems: 'center', cursor: 'pointer', overflowX: 'auto' }}
              >
                <div>
                  <b style={{ color: C.text, fontSize: '14px' }}>{group.performerName}</b>
                  <p style={{ color: C.textSec, margin: '2px 0 0', fontSize: '11px' }}>{group.project} · {group.workPackage} · {group.rows.length} строк</p>
                </div>
                <div><p style={{ color: C.textMuted, margin: 0, fontSize: '10px' }}>Начислено</p><b style={{ color: C.success }}>{money(group.accrued)}</b></div>
                <div><p style={{ color: C.textMuted, margin: 0, fontSize: '10px' }}>Авансы</p><b style={{ color: C.warning }}>{money(group.advances)}</b></div>
                <div><p style={{ color: C.textMuted, margin: 0, fontSize: '10px' }}>Удерж. 5%</p><b style={{ color: C.warning }}>{money(group.retention)}</b></div>
                <div><p style={{ color: C.textMuted, margin: 0, fontSize: '10px' }}>Выплачено / остаток</p><b style={{ color: C.info }}>{money(group.paid)} / {money(group.payable)}</b></div>
                <div style={{ display: 'flex', gap: '6px', alignItems: 'center', flexWrap: 'wrap' }}>
                  <button
                    onClick={event => {
                      event.stopPropagation();
                      payPerformerGroup(group);
                    }}
                    disabled={group.payable <= 0}
                    style={{ ...(btnO || btnG), padding: '6px 10px', fontSize: '11px', opacity: group.payable > 0 ? 1 : 0.55 }}
                  >
                    <CreditCard size={12} />
                    Выплатить
                  </button>
                  {savedAct ? (
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', color: C.success, fontSize: '11px', fontWeight: 700 }}>
                      <CheckCircle2 size={13} />
                      акт №{savedAct.id}
                    </span>
                  ) : (
                    <button
                      onClick={event => {
                        event.stopPropagation();
                        saveClosingAct(actGroup);
                      }}
                      disabled={savingKey === actGroup?.key}
                      style={{ ...(btnO || btnG), padding: '6px 10px', fontSize: '11px', opacity: savingKey === actGroup?.key ? 0.55 : 1 }}
                    >
                      <Save size={12} />
                      Сохранить
                    </button>
                  )}
                  <button
                    onClick={event => {
                      event.stopPropagation();
                      showPreview && showPreview(buildPrintHtml({ month, rows: group.rows, summary: group }), 'Закрытие — ' + group.performerName + ' — ' + group.project);
                    }}
                    style={{ ...btnG, padding: '6px 10px', fontSize: '11px' }}
                  >
                    <FileText size={12} />
                    Акт
                  </button>
                </div>
              </div>
              {open && (
                <div style={{ padding: '0 14px 14px' }}>
                  {group.reimbursements > 0 && <p style={{ color: C.textMuted, margin: '0 0 8px', fontSize: '11px' }}>Возмещенные траты за период: {money(group.reimbursements)}. Они показаны для сверки, но не уменьшают сумму акта.</p>}
                  <div style={{ overflow: 'auto' }}>
                    <table style={tbl}>
                      <thead>
                        <tr>
                          <th style={tblH}>Дата</th>
                          <th style={tblH}>Помещение</th>
                          <th style={tblH}>Работа</th>
                          <th style={tblH}>Объем</th>
                          <th style={tblH}>Цена исп.</th>
                          <th style={tblH}>Начислено</th>
                          <th style={tblH}>Заказчик</th>
                        </tr>
                      </thead>
                      <tbody>
                        {group.rows.map(row => (
                          <tr key={row.id}>
                            <td style={tblC}>{row.date || '—'}</td>
                            <td style={tblC}>{row.roomName}</td>
                            <td style={tblC}>{row.description}</td>
                            <td style={tblC}>{row.quantity + ' ' + row.unit}</td>
                            <td style={tblC}>{money(row.unitPrice)}</td>
                            <td style={{ ...tblC, color: C.success, fontWeight: 700 }}>{money(row.executionTotal)}</td>
                            <td style={tblC}>{money(row.customerTotal)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          );
        })
      )}
    </div>
  );
}
