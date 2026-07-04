import { fmtMeasure } from '../measureUtils';

export const buildMasterActDocContent = (act = {}, context = {}) => {
  const {
    companyRequisites = null,
    companyName = '',
    masterProfiles = [],
    workJournal = [],
    actPayments = [],
    tools = [],
    ownExpenses = [],
    accountablePayments = [],
  } = context;
  const profile = masterProfiles.find((item) => item.userId === act.masterId);
  const req = companyRequisites || {};
  const companyNameDoc = req.fullName || req.shortName || companyName || '_____';
  const inPeriod = (value) => {
    if (!value) return false;
    const day = String(value).split('T')[0];
    return day >= (act.periodStart || '0000-01-01') && day <= (act.periodEnd || '9999-12-31');
  };
  const workPayUnitPrice = (work) => Number(work.executionPricePerUnit || 0) || (Number(work.executionTotal || 0) / Math.max(1, Number(work.quantity || 0)));
  const workPayTotal = (work) => Number(work.executionTotal || 0);
  const actPackage = String(act.workPackage || '').trim();
  const works = workJournal.filter((item) => (
    item.masterId === act.masterId
    && item.project === act.project
    && item.status === 'Подтверждено'
    && inPeriod(item.confirmedAt || item.date)
    && (!actPackage || String(item.workPackage || item.work_package || 'Основная').trim() === actPackage)
  ));
  const payments = actPayments.filter((item) => item.actId === act.id);
  const toolDeductions = tools
    .filter((item) => item.masterName === act.masterName && item.issueType === 'В счёт зарплаты')
    .reduce((sum, item) => sum + item.cost, 0);
  const ownExpsReimbursed = (ownExpenses || []).filter((item) => (
    (item.employeeId === act.masterId || item.employeeName === act.masterName)
    && item.projectName === act.project
    && item.status === 'Возмещено'
    && inPeriod(item.date)
  ));
  const ownExpReimbSum = ownExpsReimbursed.reduce((sum, item) => sum + Number(item.amount || 0), 0);
  const advancesGiven = (accountablePayments || []).filter((item) => (
    (item.recipientId === act.masterId || item.recipientName === act.masterName)
    && item.projectName === act.project
    && inPeriod(item.date)
  ));
  const advanceSum = advancesGiven.reduce((sum, item) => sum + Number(item.amount || 0), 0);
  let html = '<h2 style="text-align:center">АКТ ВЫПОЛНЕННЫХ РАБОТ № ' + act.id + '</h2>';
  html += '<p>Заказчик: <b>' + companyNameDoc + '</b> | Исполнитель: <b>' + act.masterName + '</b></p>';
  html += '<p>Объект: <b>' + act.project + '</b> | Раздел: <b>' + (act.workPackage || 'Все разделы') + '</b> | Период: ' + act.periodStart + ' — ' + act.periodEnd + '</p>';
  if (profile) html += '<p>ИНН: ' + profile.inn + ' | ' + profile.bankName + ' | Р/с: ' + profile.bankAccount + '</p>';
  html += '<table><tr><th>N</th><th>Работа</th><th>Помещение</th><th>Ед.</th><th>Кол-во</th><th>Цена</th><th>Сумма</th></tr>';
  works.forEach((work, index) => {
    html += '<tr><td>' + (index + 1) + '</td><td>' + work.description + '</td><td>' + (work.roomName || '—') + '</td><td>' + work.unit + '</td><td>' + work.quantity + '</td><td>' + workPayUnitPrice(work).toLocaleString() + '</td><td>' + workPayTotal(work).toLocaleString() + '</td></tr>';
  });
  const totalAmt = act.totalAmount || 0;
  const paidAmt = act.paidAmount || 0;
  html += '<tr><td colspan="6"><b>ИТОГО начислено:</b></td><td><b>' + totalAmt.toLocaleString() + ' руб.</b></td></tr>';
  if (toolDeductions > 0) html += '<tr><td colspan="6">Удержания (инструмент):</td><td style="color:red">-' + toolDeductions.toLocaleString() + ' руб.</td></tr>';
  html += '<tr><td colspan="6"><b>К выплате по работам:</b></td><td><b>' + (totalAmt - toolDeductions).toLocaleString() + ' руб.</b></td></tr>';
  if (payments.length > 0) {
    html += '<tr><td colspan="7"><b>История оплат по акту:</b></td></tr>';
    payments.forEach((payment) => {
      html += '<tr><td colspan="3">' + payment.date + '</td><td colspan="2">' + payment.paymentType + '</td><td>' + payment.paidBy + '</td><td>' + payment.amount.toLocaleString() + ' руб.</td></tr>';
    });
  }
  html += '<tr><td colspan="6">Оплачено по акту:</td><td>' + paidAmt.toLocaleString() + ' руб.</td></tr>';
  html += '<tr><td colspan="6"><b>Остаток к выплате:</b></td><td><b style="color:red">' + (totalAmt - toolDeductions - paidAmt).toLocaleString() + ' руб.</b></td></tr></table>';
  if (ownExpsReimbursed.length > 0 || advancesGiven.length > 0) {
    html += '<h3 style="margin-top:18px">📒 Сопутствующие операции по сотруднику в периоде</h3>';
    html += '<p style="font-size:11px;color:#666">Не входят в сумму акта — показаны для сверки с бухгалтерией</p>';
    html += '<table><tr><th>Дата</th><th>Тип</th><th>Описание</th><th>Сумма</th></tr>';
    ownExpsReimbursed.forEach((item) => {
      html += '<tr><td>' + (item.date || '') + '</td><td>💸 Возмещено по «Моим тратам»</td><td>' + (item.description || '') + '</td><td>' + Number(item.amount || 0).toLocaleString() + ' руб.</td></tr>';
    });
    advancesGiven.forEach((item) => {
      html += '<tr><td>' + (item.date || '') + '</td><td>📤 Выдано в подотчёт</td><td>' + (item.purpose || item.notes || '') + '</td><td>' + Number(item.amount || 0).toLocaleString() + ' руб.</td></tr>';
    });
    if (ownExpReimbSum > 0) html += '<tr><td colspan="3"><b>Итого возмещено трат:</b></td><td><b>' + ownExpReimbSum.toLocaleString() + ' руб.</b></td></tr>';
    if (advanceSum > 0) html += '<tr><td colspan="3"><b>Итого выдано в подотчёт:</b></td><td><b>' + advanceSum.toLocaleString() + ' руб.</b></td></tr>';
    html += '</table>';
  }
  html += '<div class="signatures"><div class="sig"><div class="sig-line">Выполнил<br/>' + act.masterName + '</div></div><div class="sig"><div class="sig-line">Принял (прораб)</div></div><div class="sig"><div class="sig-line">' + companyNameDoc + '<br/>' + (req.directorName || '') + '</div></div></div>';
  return html;
};

export const buildBrigadeActDocContent = (contract = {}, context = {}) => {
  const {
    companyRequisites = null,
    companyName = '',
    allBrigadeItems = [],
  } = context;
  const items = (allBrigadeItems || []).filter((item) => Number(item.contractId) === Number(contract.id) && Number(item.doneQuantity || 0) > 0);
  const req = companyRequisites || {};
  const total = items.reduce((sum, item) => sum + Math.round(Number(item.doneQuantity || 0) * Number(item.priceBrigade || 0)), 0);
  let html = '<h2 style="text-align:center">АКТ ВЫПОЛНЕННЫХ РАБОТ</h2>';
  html += '<p>Заказчик работ: <b>' + (req.fullName || req.shortName || companyName || '') + '</b></p>';
  html += '<p>Объект: <b>' + (contract.projectName || '') + '</b> | Исполнитель: <b>' + (contract.brigadeName || '') + '</b>' + (contract.contractorType ? ' (' + contract.contractorType + ')' : '') + '</p>';
  html += '<table><tr><th>N</th><th>Наименование работ</th><th>Ед.</th><th>Выполнено</th><th>Цена</th><th>Сумма</th></tr>';
  if (items.length === 0) html += '<tr><td colspan="6" style="text-align:center;color:#777">Выполненных работ нет</td></tr>';
  items.forEach((item, index) => {
    const sum = Math.round(Number(item.doneQuantity || 0) * Number(item.priceBrigade || 0));
    html += '<tr><td>' + (index + 1) + '</td><td>' + (item.name || '') + '</td><td>' + (item.unit || '') + '</td><td>' + fmtMeasure(Number(item.doneQuantity || 0), item.unit) + '</td><td>' + Number(item.priceBrigade || 0).toLocaleString('ru-RU') + '</td><td>' + sum.toLocaleString('ru-RU') + '</td></tr>';
  });
  html += '<tr><td colspan="5"><b>ИТОГО к оплате:</b></td><td><b>' + total.toLocaleString('ru-RU') + ' руб.</b></td></tr></table>';
  html += '<p style="font-size:11px;color:#555">Объёмы соответствуют выполнению, отмеченному мастером в смете объекта (единый источник данных).</p>';
  html += '<div class="signatures"><div class="sig"><div class="sig-line">Сдал (исполнитель)<br/>' + (contract.brigadeName || '') + '</div></div><div class="sig"><div class="sig-line">Принял<br/>' + (req.directorName || '') + '</div></div></div>';
  return html;
};
