import { POSITION_INSTRUCTIONS, TB_INSTRUCTIONS } from '../constants/documentTemplates';
import { EXPENSE_CATEGORIES } from '../constants/catalogs';
import { docEsc, normalizeDocDate, workDocDate } from './documentFormatUtils';

const companyTitle = (companyRequisites = {}, companyName = '', fallback = '_____') => (
  companyRequisites.fullName || companyRequisites.shortName || companyName || fallback
);

const formatPrescriptionDate = (value) => {
  if (!value) return '«___» __________ 20__ г.';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const months = [
    'января',
    'февраля',
    'марта',
    'апреля',
    'мая',
    'июня',
    'июля',
    'августа',
    'сентября',
    'октября',
    'ноября',
    'декабря',
  ];
  return `«${String(date.getDate()).padStart(2, '0')}» ${months[date.getMonth()]} ${date.getFullYear()} г.`;
};

const formatShortDate = (value) => {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return `${String(date.getDate()).padStart(2, '0')}.${String(date.getMonth() + 1).padStart(2, '0')}.${date.getFullYear()}`;
};

export const fmtDocMoney = (value) => `${Math.round(Number(value || 0)).toLocaleString('ru-RU')} ₽`;

export const directorDocStyles = () => '<style>'
  + '.dir-title{text-align:center;font-weight:800;font-size:17px;margin:0 0 4px;color:#111827}'
  + '.dir-sub{text-align:center;font-size:11px;color:#6b7280;margin:0 0 16px}'
  + '.dir-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin:12px 0 16px}'
  + '.dir-card{border:1px solid #cbd5e1;border-radius:8px;padding:8px;background:#f8fafc}'
  + '.dir-card span{display:block;color:#64748b;font-size:10px}'
  + '.dir-card b{display:block;font-size:15px;margin-top:2px;color:#111827}'
  + '.dir-section{margin-top:18px;border-top:1.5px solid #334155;padding-top:9px;break-inside:avoid}'
  + '.dir-section h3{font-size:13px;margin:0 0 8px;color:#111827}'
  + '.dir-table{width:100%;border-collapse:collapse;font-size:10.5px;margin:6px 0}'
  + '.dir-table th,.dir-table td{border:1px solid #64748b;padding:4px 5px;vertical-align:top}'
  + '.dir-table th{background:#f1f5f9;font-weight:700;color:#111827}'
  + '.dir-risk{border:1px solid #f59e0b;background:#fffbeb;border-radius:6px;padding:6px 8px;margin:5px 0;font-size:11px}'
  + '.dir-danger{border-color:#ef4444;background:#fef2f2}'
  + '.dir-ok{border:1px solid #22c55e;background:#f0fdf4;border-radius:6px;padding:6px 8px;margin:5px 0;font-size:11px}'
  + '.dir-muted{color:#64748b}'
  + '</style>';

export const buildDirectorBriefReportDocContent = (date, context = {}) => {
  const {
    companyName = '',
    user = null,
    projects = [],
    workJournal = [],
    inspectionOrders = [],
    ownExpenses = [],
    supplierInvoices = [],
    lowStock = [],
    lowMainStock = [],
    projectBudgetSpent = () => ({ total: 0 }),
  } = context;
  const targetDate = normalizeDocDate(date) || new Date().toISOString().split('T')[0];
  const fmtDate = (value) => new Date((normalizeDocDate(value) || targetDate) + 'T00:00:00').toLocaleDateString('ru-RU');
  const activeProjects = projects.filter((project) => !project.archived && project.status !== 'Завершён');
  const todayWorks = workJournal.filter((work) => workDocDate(work) === targetDate);
  const pendingWorks = workJournal.filter((work) => !work.status || work.status === 'На проверке' || work.status === 'Автоматически из сметы');
  const worksWithoutPhoto = todayWorks.filter((work) => Number(work.quantity || 0) > 0 && !work.photoUrl);
  const overdueProjects = activeProjects.filter((project) => project.deadline && project.deadline < targetDate);
  const openInspectionOrders = inspectionOrders.filter((order) => order.status !== 'Закрыто');
  const pendingExpenses = ownExpenses.filter((expense) => expense.status === 'Ожидает');
  const supplierInvoiceRows = supplierInvoices.filter((invoice) => (
    invoice.status === 'На утверждении' || invoice.status === 'Утверждён' || invoice.status === 'Частично оплачен' || !invoice.status
  ));
  const supplierDebt = supplierInvoiceRows.reduce((sum, invoice) => (
    sum + Math.max(0, Number(invoice.amount || invoice.totalAmount || 0) - Number(invoice.paidAmount || 0))
  ), 0);
  const totalBudget = activeProjects.reduce((sum, project) => sum + Number(project.budget || 0), 0);
  const totalSpent = activeProjects.reduce((sum, project) => sum + projectBudgetSpent(project).total, 0);
  const todaySum = todayWorks.reduce((sum, work) => sum + Number(work.total || 0), 0);
  const actions = [];
  overdueProjects.slice(0, 8).forEach((project) => actions.push({ type: 'Сроки', priority: 'Критично', target: project.name, action: 'Проверить план работ и ответственного', sum: '' }));
  pendingWorks.slice(0, 8).forEach((work) => actions.push({ type: 'Работы', priority: 'Проверка', target: work.project || 'Без объекта', action: 'Подтвердить или вернуть: ' + (work.description || 'работа без описания'), sum: fmtDocMoney(work.total) }));
  worksWithoutPhoto.slice(0, 6).forEach((work) => actions.push({ type: 'Фото', priority: 'Внимание', target: work.project || 'Без объекта', action: 'Запросить фото: ' + (work.description || 'работа'), sum: '' }));
  lowStock.slice(0, 6).forEach((material) => actions.push({ type: 'Материалы', priority: 'Внимание', target: material.project || 'Объект', action: 'Пополнить ' + material.name + ' до минимума', sum: '' }));
  supplierInvoiceRows.slice(0, 6).forEach((invoice) => actions.push({
    type: 'Счёт',
    priority: invoice.status === 'На утверждении' || !invoice.status ? 'Согласовать' : 'Оплатить',
    target: invoice.projectName || invoice.project || 'Без объекта',
    action: (invoice.supplierName || 'Поставщик') + ' №' + (invoice.invoiceNumber || invoice.id || ''),
    sum: fmtDocMoney(invoice.amount || invoice.totalAmount),
  }));
  let html = directorDocStyles();
  html += '<div class="dir-title">СВОДКА ДИРЕКТОРА</div>';
  html += '<div class="dir-sub">' + docEsc(companyName || 'СтройКа') + ' · ' + docEsc(fmtDate(targetDate)) + ' · сформировал: ' + docEsc(user?.name || '') + '</div>';
  html += '<div class="dir-grid">';
  html += '<div class="dir-card"><span>Активных объектов</span><b>' + activeProjects.length + '</b></div>';
  html += '<div class="dir-card"><span>Работ за день</span><b>' + todayWorks.length + '</b></div>';
  html += '<div class="dir-card"><span>Сумма работ</span><b>' + fmtDocMoney(todaySum) + '</b></div>';
  html += '<div class="dir-card"><span>Счета к оплате</span><b>' + fmtDocMoney(supplierDebt) + '</b></div>';
  html += '</div>';
  html += '<div class="dir-section"><h3>Финансовый контур</h3><table class="dir-table"><tr><th>Показатель</th><th>Сумма</th><th>Комментарий</th></tr>';
  html += '<tr><td>Бюджет активных объектов</td><td>' + fmtDocMoney(totalBudget) + '</td><td>Сумма бюджетов по активным объектам</td></tr>';
  html += '<tr><td>Себестоимость/факт</td><td>' + fmtDocMoney(totalSpent) + '</td><td>' + docEsc(totalBudget > 0 ? Math.round(totalSpent / totalBudget * 100) + '% от бюджета' : 'бюджет не заполнен') + '</td></tr>';
  html += '<tr><td>Возмещения сотрудникам</td><td>' + fmtDocMoney(pendingExpenses.reduce((sum, expense) => sum + Number(expense.amount || 0), 0)) + '</td><td>' + pendingExpenses.length + ' заявок ожидают решения</td></tr>';
  html += '</table></div>';
  html += '<div class="dir-section"><h3>Что сделать сегодня</h3>';
  if (actions.length) {
    html += '<table class="dir-table"><tr><th>N</th><th>Блок</th><th>Приоритет</th><th>Объект</th><th>Действие</th><th>Сумма</th></tr>';
    actions.slice(0, 18).forEach((action, index) => {
      html += '<tr><td>' + (index + 1) + '</td><td>' + docEsc(action.type) + '</td><td>' + docEsc(action.priority) + '</td><td>' + docEsc(action.target) + '</td><td>' + docEsc(action.action) + '</td><td>' + docEsc(action.sum) + '</td></tr>';
    });
    html += '</table>';
  } else {
    html += '<div class="dir-ok">Критичных действий по загруженным данным не найдено.</div>';
  }
  html += '</div>';
  html += '<div class="dir-section"><h3>Риски</h3>';
  [
    { label: 'Просроченные объекты', value: overdueProjects.length, danger: true },
    { label: 'Работы на проверке', value: pendingWorks.length, danger: pendingWorks.length > 0 },
    { label: 'Работы за день без фото', value: worksWithoutPhoto.length, danger: worksWithoutPhoto.length > 0 },
    { label: 'Открытые замечания ГСН', value: openInspectionOrders.length, danger: openInspectionOrders.length > 0 },
    { label: 'Низкие остатки на объектах', value: lowStock.length, danger: lowStock.length > 0 },
    { label: 'Низкие остатки на основном складе', value: lowMainStock.length, danger: lowMainStock.length > 0 },
  ].forEach((risk) => {
    html += '<div class="' + (risk.danger ? 'dir-risk dir-danger' : 'dir-ok') + '"><b>' + docEsc(risk.label) + ': ' + risk.value + '</b></div>';
  });
  html += '</div>';
  return html;
};

export const buildMovementDocContent = (movement = {}, items = [], context = {}) => {
  const { companyRequisites = {}, companyName = '', userName = '' } = context;
  let html = '<h2 style="text-align:center">НАКЛАДНАЯ НА ВНУТРЕННЕЕ ПЕРЕМЕЩЕНИЕ (М-11)</h2>';
  html += `<p style="text-align:center">${companyTitle(companyRequisites, companyName)}</p>`;
  html += `<table><tr><th>Откуда</th><td>${movement.fromLocation}</td><th>Куда</th><td>${movement.toLocation}</td></tr>`;
  html += `<tr><th>Дата</th><td>${new Date().toLocaleDateString('ru-RU')}</td><th>Кто отправил</th><td>${userName}</td></tr></table>`;
  html += '<table><tr><th>N</th><th>Наименование</th><th>Ед.</th><th>Кол-во</th><th>Принял</th></tr>';
  items.forEach((item, index) => {
    html += `<tr><td>${index + 1}</td><td>${item.name}</td><td>${item.unit}</td><td>${item.quantity}</td><td style="min-width:120px"></td></tr>`;
  });
  html += `</table><div class="signatures"><div class="sig"><div class="sig-line">Отпустил: ${userName}</div></div><div class="sig"><div class="sig-line">Принял: _______________</div></div><div class="sig"><div class="sig-line">Водитель: _______________</div></div></div>`;
  return html;
};

export const buildM15DocContent = (transfer = {}, context = {}) => {
  const { companyRequisites = {}, companyName = '' } = context;
  const orgName = companyTitle(companyRequisites, companyName);
  let html = '<style>.m15-tbl{border-collapse:collapse;width:100%;font-size:11px}.m15-tbl th,.m15-tbl td{border:1px solid #333;padding:5px 6px}.m15-tbl th{background:#f3f4f6}</style>';
  html += '<h3 style="text-align:center;margin:8px 0">Унифицированная форма № М-15</h3>';
  html += `<h2 style="text-align:center;margin:0 0 4px">НАКЛАДНАЯ № ${transfer.id} на отпуск материалов на сторону</h2>`;
  html += '<p style="text-align:center;font-size:11px;color:#444">Утверждена Постановлением Госкомстата России от 30.10.1997 № 71а</p>';
  html += `<table class="m15-tbl"><tr><th>Организация</th><td>${orgName}</td><th>Дата</th><td>${formatShortDate(transfer.transferDate || transfer.date)}</td></tr>`;
  html += `<tr><th>Отправитель</th><td>${transfer.fromLocation || 'Основной склад'}</td><th>Получатель</th><td>${transfer.toPerson || ''} (${transfer.toPersonRole || ''})</td></tr>`;
  html += `<tr><th>Объект</th><td>${transfer.projectName || ''}</td><th>Пакет работ</th><td>${transfer.workPackage || 'общий'}</td></tr></table>`;
  html += '<table class="m15-tbl" style="margin-top:12px"><tr><th>№</th><th>Наименование материала</th><th>Ед.изм.</th><th>Количество</th><th>Примечание</th></tr>';
  html += `<tr><td>1</td><td>${transfer.materialName || ''}</td><td>${transfer.unit || ''}</td><td>${transfer.quantity || 0}</td><td>${transfer.notes || ''}</td></tr>`;
  html += '</table>';
  html += '<div style="margin-top:24px;display:grid;grid-template-columns:1fr 1fr;gap:30px">';
  html += '<div><div style="font-size:11px;font-weight:600;margin-bottom:30px">Отпустил:</div><div style="border-bottom:1px solid #333;min-height:18px"></div><div style="font-size:9px;color:#555;margin-top:2px">(должность, ФИО, подпись)</div></div>';
  html += `<div><div style="font-size:11px;font-weight:600;margin-bottom:30px">Получил:</div><div style="border-bottom:1px solid #333;min-height:18px">${transfer.toPerson || ''}</div><div style="font-size:9px;color:#555;margin-top:2px">(должность, ФИО, подпись)</div></div>`;
  html += '</div>';
  return html;
};

export const buildKS14DocContent = (project = {}, context = {}) => {
  const { companyRequisites = {}, companyName = '' } = context;
  const orgName = companyTitle(companyRequisites, companyName);
  let html = '<h3 style="text-align:center;margin:6px 0">Унифицированная форма № КС-14</h3>';
  html += '<h2 style="text-align:center;margin:0 0 4px">АКТ ПРИЁМКИ ОБЪЕКТА ГОСУДАРСТВЕННОЙ ПРИЁМОЧНОЙ КОМИССИЕЙ</h2>';
  html += '<p style="text-align:center;font-size:11px;color:#444">Утверждена Постановлением Госкомстата России от 30.10.1997 № 71а</p>';
  html += `<p style="font-size:12px;margin:14px 0"><b>Объект:</b> ${project.name} · <b>Адрес:</b> ${project.address || project.city || '____________'}</p>`;
  html += `<p style="font-size:12px"><b>Заказчик:</b> ${project.client || '____________'} · <b>Подрядчик:</b> ${orgName}</p>`;
  html += '<p style="font-size:12px;margin:14px 0">Государственная приёмочная комиссия в составе:</p>';
  html += '<ul style="font-size:12px"><li>Председатель комиссии (представитель заказчика)</li><li>Представитель государственного строительного надзора</li><li>Представитель пожарного надзора</li><li>Представитель санитарно-эпидемиологической службы</li><li>Представитель проектной организации</li>';
  html += `<li>Представитель генподрядчика — ${orgName}</li></ul>`;
  html += '<p style="font-size:12px;margin:14px 0">Произвела осмотр законченного строительством объекта и установила, что объект соответствует утверждённому проекту, требованиям технических регламентов и нормативной документации. Объект <b>принят</b> в эксплуатацию.</p>';
  html += '<div style="margin-top:30px;display:grid;grid-template-columns:1fr 1fr;gap:20px">';
  html += '<div><div style="font-size:11px;font-weight:600;margin-bottom:30px">Председатель комиссии:</div><div style="border-bottom:1px solid #333;min-height:18px"></div></div>';
  html += '<div><div style="font-size:11px;font-weight:600;margin-bottom:30px">Представитель ГСН:</div><div style="border-bottom:1px solid #333;min-height:18px"></div></div>';
  html += '<div><div style="font-size:11px;font-weight:600;margin-bottom:30px">Представитель пожнадзора:</div><div style="border-bottom:1px solid #333;min-height:18px"></div></div>';
  html += '<div><div style="font-size:11px;font-weight:600;margin-bottom:30px">Представитель СЭС:</div><div style="border-bottom:1px solid #333;min-height:18px"></div></div>';
  html += '<div><div style="font-size:11px;font-weight:600;margin-bottom:30px">Проектная организация:</div><div style="border-bottom:1px solid #333;min-height:18px"></div></div>';
  html += `<div><div style="font-size:11px;font-weight:600;margin-bottom:30px">Генподрядчик:</div><div style="border-bottom:1px solid #333;min-height:18px">${companyRequisites.directorName || orgName}</div></div>`;
  html += '</div>';
  return html;
};

export const buildIGDDocContent = (projectName, context = {}) => {
  const { companyRequisites = {}, companyName = '' } = context;
  const orgName = companyTitle(companyRequisites, companyName);
  let html = '<h2 style="text-align:center;margin:8px 0">ИСПОЛНИТЕЛЬНАЯ ГЕОДЕЗИЧЕСКАЯ ДОКУМЕНТАЦИЯ</h2>';
  html += '<p style="text-align:center;font-size:11px;color:#444">по СП 126.13330 «Геодезические работы в строительстве»</p>';
  html += `<p style="font-size:12px"><b>Объект:</b> ${projectName}</p>`;
  html += `<p style="font-size:12px"><b>Подрядчик:</b> ${orgName}</p>`;
  html += '<h3 style="margin-top:14px;font-size:13px">Перечень исполнительных схем (составляется геодезистом):</h3>';
  html += '<ul style="font-size:12px;line-height:1.7">';
  html += '<li>Схема расположения главных осей здания</li>';
  html += '<li>Схема расположения свай / фундамента (с отклонениями от проекта)</li>';
  html += '<li>Высотная схема цоколя и фундаментной плиты</li>';
  html += '<li>Схема расположения колонн каждого этажа</li>';
  html += '<li>Схема геодезической разбивки внутренних осей</li>';
  html += '<li>Поэтажные планы с фактическими размерами</li>';
  html += '<li>Профиль наружных сетей</li>';
  html += '<li>Сводный план фактического положения объекта на участке</li>';
  html += '</ul>';
  html += '<p style="font-size:11px;color:#666;margin-top:14px">⚠️ Схемы выполняются на бумаге/AutoCAD по СП 126.13330.2017. Должны содержать: фактические координаты, отметки, отклонения от проекта, подписи геодезиста и прораба.</p>';
  html += '<div style="margin-top:30px;display:grid;grid-template-columns:1fr 1fr;gap:20px">';
  html += '<div><div style="font-size:11px;font-weight:600;margin-bottom:30px">Геодезист:</div><div style="border-bottom:1px solid #333;min-height:18px"></div></div>';
  html += '<div><div style="font-size:11px;font-weight:600;margin-bottom:30px">Производитель работ:</div><div style="border-bottom:1px solid #333;min-height:18px"></div></div>';
  html += '</div>';
  return html;
};

export const buildM2DocContent = (supplier, items = [], projectName, recipientName, recipientPassport, context = {}) => {
  const { companyRequisites = {}, companyName = '' } = context;
  const orgName = companyTitle(companyRequisites, companyName);
  const num = String(Date.now()).slice(-6);
  const today = new Date().toISOString().split('T')[0];
  const validUntil = new Date(Date.now() + 15 * 24 * 3600 * 1000).toISOString().split('T')[0];
  let html = '<style>.m2-tbl{border-collapse:collapse;width:100%;font-size:11px;margin:8px 0}.m2-tbl th,.m2-tbl td{border:1px solid #333;padding:5px 6px}.m2-tbl th{background:#f3f4f6}</style>';
  html += '<h3 style="text-align:center;margin:6px 0">Унифицированная форма № М-2</h3>';
  html += `<h2 style="text-align:center;margin:0 0 6px">ДОВЕРЕННОСТЬ № ${num}</h2>`;
  html += '<p style="text-align:center;font-size:11px;color:#444">Утверждена Постановлением Госкомстата России от 30.10.1997 № 71а</p>';
  html += `<p style="font-size:12px"><b>Дата выдачи:</b> ${formatPrescriptionDate(today)}</p>`;
  html += `<p style="font-size:12px"><b>Действительна по:</b> ${formatPrescriptionDate(validUntil)} (срок 15 дней)</p>`;
  html += `<p style="font-size:12px"><b>Доверитель (организация):</b> ${orgName}</p>`;
  if (companyRequisites.inn) html += `<p style="font-size:12px"><b>ИНН:</b> ${companyRequisites.inn}${companyRequisites.kpp ? ` · КПП: ${companyRequisites.kpp}` : ''}</p>`;
  html += `<p style="font-size:12px"><b>Поставщик:</b> ${supplier ? supplier.name || supplier : '____________'}${supplier && supplier.inn ? ` · ИНН: ${supplier.inn}` : ''}</p>`;
  if (projectName) html += `<p style="font-size:12px"><b>Объект назначения:</b> ${projectName}</p>`;
  html += `<p style="font-size:12px;margin:10px 0">Уполномачивает гражданина <b>${recipientName || '____________'}</b>${recipientPassport ? `, паспорт: ${recipientPassport}` : ''} получить от поставщика следующие материальные ценности:</p>`;
  html += '<table class="m2-tbl"><tr><th>№</th><th>Наименование</th><th>Ед.изм.</th><th>Кол-во (цифрами)</th><th>Кол-во (прописью)</th></tr>';
  items.forEach((item, index) => {
    html += `<tr><td>${index + 1}</td><td>${item.name || ''}</td><td>${item.unit || ''}</td><td>${item.quantity || 0}</td><td>${item.qtyText || ''}</td></tr>`;
  });
  if (items.length === 0) html += '<tr><td>1</td><td colspan="4" style="color:#888">(укажите материалы)</td></tr>';
  html += '</table>';
  html += '<p style="font-size:12px;margin:16px 0">Доверенность недействительна без предъявления документа, удостоверяющего личность.</p>';
  html += '<div style="margin-top:30px;display:grid;grid-template-columns:1fr 1fr;gap:20px">';
  html += `<div><div style="font-size:11px;font-weight:600;margin-bottom:30px">Руководитель:</div><div style="border-bottom:1px solid #333;min-height:18px">${companyRequisites.directorName || ''}</div><div style="font-size:9px;color:#555;margin-top:2px">(подпись, ФИО)</div></div>`;
  html += `<div><div style="font-size:11px;font-weight:600;margin-bottom:30px">Главный бухгалтер:</div><div style="border-bottom:1px solid #333;min-height:18px">${companyRequisites.accountantName || ''}</div><div style="font-size:9px;color:#555;margin-top:2px">(подпись, ФИО)</div></div>`;
  html += '</div>';
  html += '<p style="margin-top:20px;font-size:10px;text-align:center">М.П.</p>';
  html += '<p style="margin-top:16px;font-size:11px;text-align:center;color:#555"><b>Подпись получателя</b>, удостоверяющая образец подписи: ___________________________</p>';
  return html;
};

export const buildAOSKDocContent = (projectName, context = {}) => {
  const { companyRequisites = {}, companyName = '', projects = [], hiddenActs = [] } = context;
  const orgName = companyTitle(companyRequisites, companyName);
  const project = projects.find((item) => item.name === projectName) || {};
  const acts = hiddenActs.filter((act) => act.projectName === projectName);
  const responsibleActs = acts.filter((act) => {
    const workName = String(act.workName || '').toLowerCase();
    return ['фундамент', 'арматур', 'бетон', 'каркас', 'несущ', 'перекрыт', 'колонн', 'балк'].some((keyword) => workName.includes(keyword));
  });
  let html = '<style>.aosk-title{text-align:center;font-weight:700;font-size:14px;margin:18px 0 4px}.aosk-sub{text-align:center;font-size:13px;margin:0 0 14px}.aosk-item{margin:8px 0;font-size:12px;line-height:1.5}.aosk-tbl{border-collapse:collapse;width:100%;font-size:11px;margin:8px 0}.aosk-tbl th,.aosk-tbl td{border:1px solid #333;padding:4px 6px}.aosk-tbl th{background:#f3f4f6}</style>';
  html += `<div style="margin:6px 0;font-size:12px"><b>${orgName}</b></div>`;
  html += '<div class="aosk-title">АКТ</div><div class="aosk-sub">освидетельствования ответственных конструкций</div>';
  html += `<div class="aosk-item"><b>Объект:</b> ${projectName || ''}</div>`;
  html += `<div class="aosk-item"><b>Заказчик:</b> ${project.client || '____________'}</div>`;
  html += `<div class="aosk-item"><b>Подрядчик:</b> ${orgName}</div>`;
  html += `<div class="aosk-item"><b>Дата:</b> ${formatPrescriptionDate(new Date().toISOString().slice(0, 10))}</div>`;
  html += '<p style="font-size:12px;margin:14px 0 8px">Комиссия в составе представителей застройщика, технадзора, генподрядчика и субподрядчика провела освидетельствование следующих ответственных конструкций:</p>';
  if (responsibleActs.length === 0) {
    html += '<p style="text-align:center;color:#888;font-size:11px;padding:14px">Записей по ответственным конструкциям нет — ведутся через АОСР (СНиП 12-01-2004)</p>';
  } else {
    html += '<table class="aosk-tbl"><tr><th>№</th><th>Конструкция</th><th>Объём</th><th>Раздел сметы</th><th>Подписан</th><th>Связан с АОСР</th></tr>';
    responsibleActs.forEach((act, index) => {
      html += `<tr><td>${index + 1}</td><td>${act.workName || ''}</td><td>${act.quantity || 0} ${act.unit || ''}</td><td>${act.sectionName || '—'}</td><td>${act.status === 'Подписан' ? '✅' : `⏳ ${act.status || ''}`}</td><td>${act.actNumber}</td></tr>`;
    });
    html += '</table>';
  }
  html += '<p style="font-size:12px;margin:14px 0">При выполнении конструкций соблюдены требования: СНиП 3.03.01 (бетонные и железобетонные конструкции), ГОСТ 26633 (бетоны тяжёлые), ГОСТ 5781 (арматура).</p>';
  html += '<p style="font-size:12px"><b>Заключение комиссии:</b> ответственные конструкции выполнены в соответствии с проектной документацией и техническими регламентами. Разрешается производство последующих работ.</p>';
  html += '<div style="margin-top:30px;display:grid;grid-template-columns:1fr 1fr;gap:20px">';
  html += '<div><div style="font-size:11px;font-weight:600;margin-bottom:30px">Представитель застройщика (заказчика):</div><div style="border-bottom:1px solid #333;min-height:18px"></div><div style="font-size:9px;color:#555;margin-top:2px">(должность, ФИО, подпись)</div></div>';
  html += '<div><div style="font-size:11px;font-weight:600;margin-bottom:30px">Представитель технического надзора:</div><div style="border-bottom:1px solid #333;min-height:18px"></div><div style="font-size:9px;color:#555;margin-top:2px">(должность, ФИО, подпись)</div></div>';
  html += `<div><div style="font-size:11px;font-weight:600;margin-bottom:30px">Представитель генподрядчика:</div><div style="border-bottom:1px solid #333;min-height:18px">${companyRequisites.directorName || ''}</div><div style="font-size:9px;color:#555;margin-top:2px">(должность, ФИО, подпись)</div></div>`;
  html += '<div><div style="font-size:11px;font-weight:600;margin-bottom:30px">Представитель проектной организации:</div><div style="border-bottom:1px solid #333;min-height:18px"></div><div style="font-size:9px;color:#555;margin-top:2px">(должность, ФИО, подпись)</div></div>';
  html += '</div>';
  html += '<p style="margin-top:20px;font-size:10px;color:#555;text-align:center">Форма соответствует СНиП 12-01-2004 (Приложение 4). Документ обязателен для приёмки несущих/ответственных конструкций.</p>';
  return html;
};

export const buildKS11DocContent = (project = {}, context = {}) => {
  const { companyRequisites = {}, companyName = '', hiddenActs = [], projectPlanDone = () => ({ done: 0 }) } = context;
  const orgName = companyTitle(companyRequisites, companyName);
  const planDone = projectPlanDone(project);
  const projectActs = hiddenActs.filter((act) => act.projectName === project.name);
  const signedActs = projectActs.filter((act) => act.status === 'Подписан').length;
  let html = '<style>.ks-tbl{border-collapse:collapse;width:100%;font-size:11px}.ks-tbl th,.ks-tbl td{border:1px solid #333;padding:5px 6px}.ks-tbl th{background:#f3f4f6}</style>';
  html += '<h3 style="text-align:center;margin:6px 0">Унифицированная форма № КС-11</h3>';
  html += '<h2 style="text-align:center;margin:0 0 4px">АКТ ПРИЁМКИ ЗАКОНЧЕННОГО СТРОИТЕЛЬСТВОМ ОБЪЕКТА</h2>';
  html += '<p style="text-align:center;font-size:11px;color:#444">Утверждена Постановлением Госкомстата России от 30.10.1997 № 71а</p>';
  html += `<p style="font-size:12px"><b>Объект:</b> ${project.name}</p>`;
  html += `<p style="font-size:12px"><b>Адрес:</b> ${project.address || project.city || '____________'}</p>`;
  html += `<p style="font-size:12px"><b>Заказчик:</b> ${project.client || '____________'}</p>`;
  html += `<p style="font-size:12px"><b>Подрядчик:</b> ${orgName}</p>`;
  html += `<p style="font-size:12px"><b>Дата подписания:</b> ${formatPrescriptionDate(new Date().toISOString().slice(0, 10))}</p>`;
  html += '<h3 style="margin-top:14px;font-size:13px">1. Характеристики выполненных работ:</h3>';
  html += `<table class="ks-tbl"><tr><td>Бюджет по договору</td><td>${Math.round(Number(project.budget || 0)).toLocaleString('ru-RU')} ₽</td></tr>`;
  html += `<tr><td>Выполнено по смете</td><td>${Math.round(planDone.done).toLocaleString('ru-RU')} ₽</td></tr>`;
  html += `<tr><td>Срок строительства</td><td>${project.startDate || '____'} — ${project.deadline || '____'}</td></tr>`;
  html += `<tr><td>АОСР подписанных / всего</td><td>${signedActs} / ${projectActs.length}</td></tr></table>`;
  html += '<h3 style="margin-top:14px;font-size:13px">2. Заключение приёмочной комиссии:</h3>';
  html += `<p style="font-size:12px">Объект <b>${project.name}</b> выполнен в соответствии с проектной документацией, техническими регламентами и условиями договора подряда. Все скрытые работы освидетельствованы и приняты согласно АОСР. Объект пригоден к эксплуатации.</p>`;
  html += '<div style="margin-top:30px;display:grid;grid-template-columns:1fr 1fr;gap:20px">';
  html += `<div><div style="font-size:11px;font-weight:600;margin-bottom:30px">Заказчик:</div><div style="border-bottom:1px solid #333;min-height:18px">${project.client || ''}</div></div>`;
  html += `<div><div style="font-size:11px;font-weight:600;margin-bottom:30px">Подрядчик:</div><div style="border-bottom:1px solid #333;min-height:18px">${companyRequisites.directorName || orgName}</div></div>`;
  html += '</div>';
  return html;
};

export const buildSpecJournalDocContent = (projectName, kind, context = {}) => {
  const { companyRequisites = {}, companyName = '', workJournal = [] } = context;
  const orgName = companyTitle(companyRequisites, companyName);
  const keywordsByKind = {
    welding: ['свар', 'наплавка', 'шов', 'электрод'],
    concrete: ['бетон', 'стяжк', 'залив', 'раствор', 'цемент'],
    assembly: ['монтаж', 'сборн', 'установк', 'панел', 'плит', 'блок'],
    anticorrosion: ['антикорр', 'покрас', 'грунт', 'окрашивание', 'лак'],
    insulation: ['изоляц', 'утепл', 'гидро', 'пароизол', 'шумоизол'],
    piling: ['свай', 'забивк', 'буронабивн', 'шпунт'],
  };
  const titles = { welding: 'СВАРОЧНЫХ', concrete: 'БЕТОННЫХ', assembly: 'МОНТАЖА СБОРНЫХ ж/б КОНСТРУКЦИЙ', anticorrosion: 'АНТИКОРРОЗИОННОЙ ЗАЩИТЫ', insulation: 'ИЗОЛЯЦИОННЫХ', piling: 'СВАЙНЫХ' };
  const norms = { welding: 'РД-03-606-03', concrete: 'ГОСТ 31108-2020 / СП 70.13330', assembly: 'СП 70.13330', anticorrosion: 'СНиП 3.04.03-85', insulation: 'СП 71.13330', piling: 'СП 24.13330' };
  const keywords = keywordsByKind[kind] || [];
  const filtered = workJournal.filter((work) => work.project === projectName && keywords.some((keyword) => String(work.description || '').toLowerCase().includes(keyword)));
  let html = '<style>.sp-tbl{border-collapse:collapse;width:100%;font-size:11px;margin:8px 0}.sp-tbl th,.sp-tbl td{border:1px solid #333;padding:5px 6px}.sp-tbl th{background:#f3f4f6}</style>';
  html += `<h2 style="text-align:center;margin:6px 0">ЖУРНАЛ ${titles[kind]} РАБОТ</h2>`;
  html += `<p style="text-align:center;font-size:11px;color:#444">по ${norms[kind]}</p>`;
  html += `<p style="font-size:12px"><b>Объект:</b> ${projectName} · <b>Подрядчик:</b> ${orgName}</p>`;
  if (filtered.length === 0) {
    html += `<p style="text-align:center;color:#888;font-size:11px;padding:20px">Записей по ${String(titles[kind] || '').toLowerCase()} работам в журнале не найдено. Используются ключевые слова: ${keywords.join(', ')}</p>`;
  } else {
    html += '<table class="sp-tbl"><tr><th>№</th><th>Дата</th><th>Описание работы</th><th>Ед.</th><th>Кол-во</th><th>Исполнитель</th><th>ИТР</th><th>Нормативы</th><th>Качество</th></tr>';
    filtered.forEach((work, index) => {
      html += `<tr><td>${index + 1}</td><td>${work.date || ''}</td><td>${work.description || ''}${work.hiddenWork ? ' 🔒' : ''}</td><td>${work.unit || ''}</td><td>${work.quantity || 0}</td><td>${work.masterName || ''}</td><td>${work.responsibleItr || '—'}</td><td>${work.normatives || '—'}</td><td>${work.qualityStatus || work.status || ''}</td></tr>`;
    });
    html += '</table>';
  }
  html += '<div style="margin-top:24px;display:grid;grid-template-columns:1fr 1fr;gap:20px">';
  html += '<div><div style="font-size:11px;font-weight:600;margin-bottom:30px">Производитель работ:</div><div style="border-bottom:1px solid #333;min-height:18px"></div></div>';
  html += '<div><div style="font-size:11px;font-weight:600;margin-bottom:30px">Технадзор:</div><div style="border-bottom:1px solid #333;min-height:18px"></div></div>';
  html += '</div>';
  html += `<p style="margin-top:16px;font-size:10px;color:#666;text-align:center">Журнал формируется автоматически из общего журнала работ по ключевым словам. По ${norms[kind]} допустимо ведение отдельного спецжурнала.</p>`;
  return html;
};

export const buildSupplementaryAgreementDocContent = (unexpectedWork = {}, project = {}, context = {}) => {
  const { companyRequisites = {}, companyName = '' } = context;
  const orgName = companyTitle(companyRequisites, companyName);
  const number = unexpectedWork.id || '____';
  const isReduction = unexpectedWork.changeType === 'Исключение объёма';
  const total = Math.round(Math.abs(Number(unexpectedWork.total || 0))).toLocaleString('ru-RU');
  let html = `<h2 style="text-align:center;margin:6px 0">ДОПОЛНИТЕЛЬНОЕ СОГЛАШЕНИЕ № ${number}</h2>`;
  html += `<p style="text-align:center;font-size:11px;color:#444">к договору подряда на объект «${project.name}»</p>`;
  html += `<div style="display:flex;justify-content:space-between;font-size:11px;margin:14px 0"><span>г. ${project.city || '____________'}</span><span>${formatPrescriptionDate(unexpectedWork.approvedAt || new Date().toISOString().slice(0, 10))}</span></div>`;
  html += `<p style="font-size:12px;line-height:1.6">${project.client || '____________'}, именуемый в дальнейшем <b>«Заказчик»</b>, в лице руководителя, с одной стороны, и ${orgName}, именуемый <b>«Подрядчик»</b>, в лице ${companyRequisites.directorName || 'руководителя'}, с другой стороны, заключили настоящее дополнительное соглашение о нижеследующем:</p>`;
  html += '<h3 style="font-size:13px;margin-top:14px">1. Предмет соглашения</h3>';
  html += `<p style="font-size:12px">Стороны согласовали изменение к смете: <b>${unexpectedWork.changeType || 'Работа вне сметы'}</b>${unexpectedWork.reason ? ` Причина: ${unexpectedWork.reason}.` : ''}</p>`;
  html += '<table style="border-collapse:collapse;width:100%;font-size:11px;margin:8px 0"><tr style="background:#f3f4f6"><th style="border:1px solid #333;padding:5px 6px">Наименование работ</th><th style="border:1px solid #333;padding:5px 6px">Ед.</th><th style="border:1px solid #333;padding:5px 6px">Кол-во</th><th style="border:1px solid #333;padding:5px 6px">Цена</th><th style="border:1px solid #333;padding:5px 6px">Сумма</th></tr>';
  html += `<tr><td style="border:1px solid #333;padding:5px 6px">${unexpectedWork.description || ''}</td><td style="border:1px solid #333;padding:5px 6px">${unexpectedWork.unit || ''}</td><td style="border:1px solid #333;padding:5px 6px">${unexpectedWork.deltaQuantity || unexpectedWork.quantity || 0}</td><td style="border:1px solid #333;padding:5px 6px">${Math.round(Number(unexpectedWork.price || 0)).toLocaleString('ru-RU')}</td><td style="border:1px solid #333;padding:5px 6px">${isReduction ? '- ' : ''}${total}</td></tr></table>`;
  html += '<h3 style="font-size:13px;margin-top:14px">2. Стоимость и порядок оплаты</h3>';
  html += isReduction
    ? `<p style="font-size:12px">Стоимость работ по договорной смете уменьшается на <b>${total} ₽</b>. Уменьшенный объём не подлежит включению в акты КС как выполненная работа.</p>`
    : `<p style="font-size:12px">Общая стоимость дополнительных работ по настоящему соглашению составляет <b>${total} ₽</b>. Оплата производится Заказчиком после фактического выполнения работ и подписания акта приёмки.</p>`;
  html += '<h3 style="font-size:13px;margin-top:14px">3. Сроки выполнения</h3>';
  html += '<p style="font-size:12px">Подрядчик обязуется выполнить работы в течение 30 (тридцати) дней с даты подписания настоящего соглашения.</p>';
  html += '<h3 style="font-size:13px;margin-top:14px">4. Прочие условия</h3>';
  html += '<p style="font-size:12px">В остальном применяются условия основного договора подряда. Соглашение составлено в 2 экземплярах — по одному для каждой стороны.</p>';
  html += '<div style="margin-top:30px;display:grid;grid-template-columns:1fr 1fr;gap:30px">';
  html += `<div><div style="font-size:11px;font-weight:600;margin-bottom:30px">ЗАКАЗЧИК:</div><div style="border-bottom:1px solid #333;min-height:18px">${project.client || ''}</div><div style="font-size:9px;color:#555;margin-top:2px">(должность, ФИО, подпись)</div></div>`;
  html += `<div><div style="font-size:11px;font-weight:600;margin-bottom:30px">ПОДРЯДЧИК:</div><div style="border-bottom:1px solid #333;min-height:18px">${companyRequisites.directorName || orgName}</div><div style="font-size:9px;color:#555;margin-top:2px">(должность, ФИО, подпись)</div></div>`;
  html += '</div>';
  return html;
};

export const buildExecPackageDocContent = (project = {}, context = {}) => {
  const {
    hiddenActs = [],
    materialInspections = [],
    cableJournal = [],
    tbJournal = [],
    prescriptionsList = [],
  } = context;
  const acts = hiddenActs.filter((act) => act.projectName === project.name);
  const inspections = materialInspections.filter((inspection) => inspection.projectName === project.name);
  const cables = cableJournal.filter((item) => item.projectName === project.name);
  const tb = tbJournal.filter((entry) => entry.project === project.name);
  const prescriptions = prescriptionsList.filter((item) => item.projectName === project.name);
  let html = '<h2 style="text-align:center;margin:8px 0">ПАКЕТ ИСПОЛНИТЕЛЬНОЙ ДОКУМЕНТАЦИИ</h2>';
  html += '<p style="text-align:center;font-size:11px;color:#444">для сдачи объекта в Госстройнадзор</p>';
  html += `<p style="font-size:12px;text-align:center;margin:14px 0"><b>${project.name}</b></p>`;
  html += '<h3 style="margin-top:14px;font-size:13px">Состав пакета:</h3>';
  html += '<table style="border-collapse:collapse;width:100%;font-size:11px"><tr style="background:#f3f4f6"><th style="border:1px solid #333;padding:5px 6px">№</th><th style="border:1px solid #333;padding:5px 6px">Документ</th><th style="border:1px solid #333;padding:5px 6px">Кол-во</th><th style="border:1px solid #333;padding:5px 6px">Норматив</th></tr>';
  const items = [
    ['Общий журнал работ (РД-11-05-2007, форма ЖПР)', '1', 'РД-11-05-2007'],
    ['Акты освидетельствования скрытых работ (АОСР)', `${acts.length} (${acts.filter((act) => act.status === 'Подписан').length} подп.)`, 'СНиП 12-01-2004'],
    ['Акты освидетельствования ответственных конструкций (АОСК)', 'см. АОСР', 'СНиП 12-01-2004'],
    ['Журнал входного контроля материалов', inspections.length, 'СП 48.13330.2019'],
    ['Журнал кабельной продукции', cables.length, 'СП 76.13330'],
    ['Журнал инструктажей ТБ', tb.length, 'ГОСТ 12.0.004-2015'],
    ['Исполнительная геодезическая документация (ИГД)', 'см. ИГД', 'СП 126.13330'],
    ['Сертификаты и паспорта на материалы', 'см. журнал входного контроля', '—'],
    ['Акт КС-11 (приёмка законченного объекта)', '1', 'Госкомстат № 71а'],
    ['Акт КС-14 (госприёмка)', '1 (если ФЗ-44)', 'Госкомстат № 71а'],
    ['Предписания и ответы на них', prescriptions.length, 'МДС 12-46.2008'],
  ];
  items.forEach((item, index) => {
    html += `<tr><td style="border:1px solid #333;padding:5px 6px">${index + 1}</td><td style="border:1px solid #333;padding:5px 6px">${item[0]}</td><td style="border:1px solid #333;padding:5px 6px">${item[1]}</td><td style="border:1px solid #333;padding:5px 6px">${item[2]}</td></tr>`;
  });
  html += '</table>';
  html += '<p style="font-size:11px;color:#666;margin-top:18px">⚠️ Перед сдачей в Госстройнадзор все журналы распечатать, прошить, пронумеровать страницы. АОСР должны быть подписаны 4 сторонами. Сертификаты на материалы — оригиналы или заверенные копии.</p>';
  return html;
};

export const buildVATBookDocContent = (periodFrom, periodTo, context = {}) => {
  const {
    companyRequisites = {},
    companyName = '',
    supplierInvoices = [],
    interimActs = [],
  } = context;
  const req = companyRequisites || {};
  const orgName = req.fullName || req.shortName || companyName || '_____';
  const inRange = (date) => !date ? false : (!periodFrom || date >= periodFrom) && (!periodTo || date <= periodTo);
  const purchases = supplierInvoices.filter((invoice) => (
    (invoice.status === 'Оплачен' || invoice.status === 'Утверждён') && inRange(invoice.invoiceDate)
  ));
  const sales = interimActs.filter((act) => inRange(act.periodEnd || act.periodStart));
  const totalPurchase = purchases.reduce((sum, invoice) => sum + Number(invoice.amount || 0), 0);
  const totalPurchaseVAT = purchases.reduce((sum, invoice) => sum + Number(invoice.vatAmount || 0), 0);
  const totalSales = sales.reduce((sum, act) => sum + Number(act.totalAmount || 0), 0);
  const estVATSales = Math.round(totalSales / 120 * 20);
  let html = '<style>.vat-tbl{border-collapse:collapse;width:100%;font-size:11px;margin:8px 0}.vat-tbl th,.vat-tbl td{border:1px solid #333;padding:5px 6px}.vat-tbl th{background:#f3f4f6}</style>';
  html += '<h2 style="text-align:center;margin:6px 0">КНИГА ПОКУПОК И ПРОДАЖ (НДС)</h2>';
  html += '<p style="text-align:center;font-size:11px;color:#444">Налогоплательщик: <b>' + orgName + '</b> · ИНН: ' + (req.inn || '____________') + '</p>';
  html += '<p style="text-align:center;font-size:11px;color:#444">Период: ' + (periodFrom || '__.__.____') + ' — ' + (periodTo || '__.__.____') + '</p>';
  html += '<h3 style="margin-top:14px;font-size:13px">Книга покупок (входящие счета от поставщиков)</h3>';
  if (purchases.length === 0) {
    html += '<p style="font-size:11px;color:#888">За период покупок нет</p>';
  } else {
    html += '<table class="vat-tbl"><tr><th>№</th><th>Дата</th><th>Поставщик</th><th>№ счёта</th><th>Сумма с НДС</th><th>В т.ч. НДС</th><th>Статус</th></tr>';
    purchases.forEach((purchase, index) => {
      html += '<tr><td>' + (index + 1) + '</td><td>' + (purchase.invoiceDate || '') + '</td><td>' + (purchase.supplierName || '') + '</td><td>' + (purchase.invoiceNumber || '') + '</td><td style="text-align:right">' + Math.round(Number(purchase.amount || 0)).toLocaleString('ru-RU') + '</td><td style="text-align:right">' + Math.round(Number(purchase.vatAmount || 0)).toLocaleString('ru-RU') + '</td><td>' + purchase.status + '</td></tr>';
    });
    html += '<tr style="background:#fef3c7"><td colspan="4"><b>ИТОГО покупки:</b></td><td style="text-align:right"><b>' + Math.round(totalPurchase).toLocaleString('ru-RU') + ' ₽</b></td><td style="text-align:right"><b>' + Math.round(totalPurchaseVAT).toLocaleString('ru-RU') + ' ₽</b></td><td></td></tr>';
    html += '</table>';
  }
  html += '<h3 style="margin-top:14px;font-size:13px">Книга продаж (выставленные акты выполненных работ)</h3>';
  if (sales.length === 0) {
    html += '<p style="font-size:11px;color:#888">За период продаж нет</p>';
  } else {
    html += '<table class="vat-tbl"><tr><th>№</th><th>Период</th><th>Объект</th><th>Контрагент</th><th>Сумма</th><th>НДС (20%)</th></tr>';
    sales.forEach((sale, index) => {
      const vat = Math.round(Number(sale.totalAmount || 0) / 120 * 20);
      html += '<tr><td>' + (index + 1) + '</td><td>' + ((sale.periodStart || '') + ' — ' + (sale.periodEnd || '')) + '</td><td>' + (sale.project || '') + '</td><td>' + (sale.masterName || '') + '</td><td style="text-align:right">' + Math.round(Number(sale.totalAmount || 0)).toLocaleString('ru-RU') + '</td><td style="text-align:right">' + vat.toLocaleString('ru-RU') + '</td></tr>';
    });
    html += '<tr style="background:#d1fae5"><td colspan="4"><b>ИТОГО продажи:</b></td><td style="text-align:right"><b>' + Math.round(totalSales).toLocaleString('ru-RU') + ' ₽</b></td><td style="text-align:right"><b>' + estVATSales.toLocaleString('ru-RU') + ' ₽</b></td></tr>';
    html += '</table>';
  }
  html += '<div style="margin-top:20px;padding:14px;background:#f3f4f6;border-radius:8px;font-size:12px">';
  html += '<b>Итог по НДС за период:</b><br/>';
  html += 'НДС к вычету (покупки): <b>' + Math.round(totalPurchaseVAT).toLocaleString('ru-RU') + ' ₽</b><br/>';
  html += 'НДС к начислению (продажи): <b>' + estVATSales.toLocaleString('ru-RU') + ' ₽</b><br/>';
  html += '<b style="color:' + (estVATSales - totalPurchaseVAT > 0 ? '#dc2626' : '#059669') + '">НДС к уплате в бюджет: ' + (estVATSales - totalPurchaseVAT).toLocaleString('ru-RU') + ' ₽</b>';
  html += '</div>';
  html += '<p style="margin-top:14px;font-size:10px;color:#666;text-align:center">Расчёт ориентировочный. Финальные суммы определяются по налоговой декларации (ст.169-172 НК РФ). Для ОСН.</p>';
  return html;
};

export const buildSupervisorMonthlyReportDocContent = (projectName, periodFrom, periodTo, context = {}) => {
  const {
    companyRequisites = {},
    companyName = '',
    projects = [],
    hiddenActs = [],
    supervisorActs = [],
    prescriptionsList = [],
    user = null,
  } = context;
  const req = companyRequisites || {};
  const orgName = req.fullName || req.shortName || companyName || '_____';
  const project = projects.find((item) => item.name === projectName) || {};
  const inRange = (date) => !date ? false : (!periodFrom || date >= periodFrom) && (!periodTo || date <= periodTo);
  const acts = hiddenActs.filter((act) => act.projectName === projectName && inRange(act.workDate));
  const supActs = supervisorActs.filter((act) => act.projectName === projectName && inRange(act.date));
  const prescriptions = prescriptionsList.filter((prescription) => (
    prescription.projectName === projectName && prescription.issuedByRole === 'Технадзор' && inRange(prescription.deadline)
  ));
  let html = '<h2 style="text-align:center;margin:8px 0">МЕСЯЧНЫЙ ОТЧЁТ ТЕХНАДЗОРА</h2>';
  html += '<p style="text-align:center;font-size:12px;color:#444">Объект: <b>' + projectName + '</b> · Период: ' + (periodFrom || '__.__.____') + ' — ' + (periodTo || '__.__.____') + '</p>';
  html += '<p style="font-size:11px"><b>Заказчик:</b> ' + (project.client || '____________') + ' · <b>Подрядчик:</b> ' + orgName + '</p>';
  html += '<h3 style="margin-top:18px">1. Освидетельствование скрытых работ (' + acts.length + ')</h3>';
  if (acts.length === 0) {
    html += '<p style="font-size:11px;color:#888">За период скрытых работ не предъявлялось</p>';
  } else {
    html += '<table style="border-collapse:collapse;width:100%;font-size:11px"><tr style="background:#f3f4f6"><th style="border:1px solid #333;padding:4px">№ акта</th><th style="border:1px solid #333;padding:4px">Работа</th><th style="border:1px solid #333;padding:4px">Дата</th><th style="border:1px solid #333;padding:4px">Подпись технадзора</th></tr>';
    acts.forEach((act) => {
      html += '<tr><td style="border:1px solid #333;padding:4px">' + act.actNumber + '</td><td style="border:1px solid #333;padding:4px">' + act.workName + '</td><td style="border:1px solid #333;padding:4px">' + (act.workDate || '') + '</td><td style="border:1px solid #333;padding:4px">' + (act.signedSupervisor ? '✅ ' + act.signedSupervisor : '⏳') + '</td></tr>';
    });
    html += '</table>';
  }
  html += '<h3 style="margin-top:18px">2. Акты осмотра (' + supActs.length + ')</h3>';
  if (supActs.length === 0) {
    html += '<p style="font-size:11px;color:#888">За период не составлялись</p>';
  } else {
    supActs.forEach((act) => {
      html += '<div style="border:1px solid #ddd;padding:10px;margin:6px 0;font-size:11px;border-radius:4px"><b>' + act.actNumber + ' · ' + act.actType + '</b> (' + act.date + ')<br/>' + (act.description || '') + (act.findings ? '<br/><b>Обнаружено:</b> ' + act.findings : '') + (act.recommendations ? '<br/><b>Рекомендации:</b> ' + act.recommendations : '') + '</div>';
    });
  }
  html += '<h3 style="margin-top:18px">3. Предписания технадзора (' + prescriptions.length + ')</h3>';
  if (prescriptions.length === 0) {
    html += '<p style="font-size:11px;color:#888">Предписаний не выдавалось</p>';
  } else {
    prescriptions.forEach((prescription) => {
      html += '<div style="border-left:3px solid ' + (prescription.status === 'Закрыто' ? '#10b981' : '#f59e0b') + ';padding:8px 10px;margin:6px 0;font-size:11px"><b>' + (prescription.violation || prescription.description || '(пусто)') + '</b><br/>Статус: ' + (prescription.status || '') + (prescription.deadline ? ' · до ' + prescription.deadline : '') + '</div>';
    });
  }
  html += '<div style="margin-top:30px;display:grid;grid-template-columns:1fr;gap:30px"><div><div style="font-size:11px;font-weight:600;margin-bottom:30px">Технадзор:</div><div style="border-bottom:1px solid #333;min-height:18px">' + (user ? user.name : '') + '</div><div style="font-size:9px;color:#555;margin-top:2px">(должность, ФИО, подпись)</div></div></div>';
  return html;
};

export const buildInventoryDocContent = (inventory = {}, items = [], context = {}) => {
  const { companyRequisites = {}, companyName = '' } = context;
  const totalShortage = items.filter((item) => item.difference < 0).reduce((sum, item) => sum + Math.abs(item.difference) * item.price, 0);
  const totalSurplus = items.filter((item) => item.difference > 0).reduce((sum, item) => sum + item.difference * item.price, 0);
  let html = `<h2 style="text-align:center">АКТ ИНВЕНТАРИЗАЦИИ № ${inventory.id}</h2>`;
  html += `<p style="text-align:center">${companyTitle(companyRequisites, companyName)}</p>`;
  html += `<table><tr><th>Объект</th><td>${inventory.project}</td></tr><tr><th>Дата</th><td>${inventory.date}</td></tr><tr><th>Провёл</th><td>${inventory.created_by || inventory.createdBy || ''}</td></tr></table>`;
  html += '<table><tr><th>N</th><th>Наименование</th><th>Ед.</th><th>По учёту</th><th>Факт</th><th>Разница</th><th>Цена</th><th>Сумма</th></tr>';
  items.forEach((item, index) => {
    const sum = Math.abs(item.difference || 0) * Number(item.price || 0);
    html += `<tr><td>${index + 1}</td><td>${item.materialName}</td><td>${item.unit}</td><td>${item.expected}</td><td>${item.actual}</td><td style="color:${item.difference < 0 ? 'red' : item.difference > 0 ? 'green' : 'black'}">${item.difference > 0 ? '+' : ''}${item.difference}</td><td>${Number(item.price || 0).toLocaleString()}</td><td>${item.difference !== 0 ? sum.toLocaleString() : '0'}</td></tr>`;
  });
  html += `</table><p><b>Итого недостача: ${totalShortage.toLocaleString()} руб.</b></p><p><b>Итого излишек: ${totalSurplus.toLocaleString()} руб.</b></p>`;
  html += `<div class="signatures"><div class="sig"><div class="sig-line">Директор<br/>${companyRequisites.directorName || ''}</div></div><div class="sig"><div class="sig-line">Прораб</div></div><div class="sig"><div class="sig-line">Кладовщик</div></div><div class="sig"><div class="sig-line">Мастер</div></div></div>`;
  return html;
};

export const buildPrescriptionDocContent = (prescription = {}, context = {}) => {
  const { companyRequisites = {}, companyName = '', project = {} } = context;
  const orgName = companyTitle(companyRequisites, companyName);
  let html = '<style>'
    + '.pr-meta{margin:6px 0;font-size:12px}'
    + '.pr-title{text-align:center;font-weight:700;font-size:15px;margin:18px 0 6px}'
    + '.pr-sub{text-align:center;font-size:13px;margin:0 0 18px;color:#444}'
    + '.pr-row{display:flex;justify-content:space-between;font-size:12px;margin:4px 0}'
    + '.pr-item{margin:10px 0;font-size:12px;line-height:1.5}'
    + '.pr-block{border:1px solid #333;padding:10px;margin:8px 0;font-size:12px;line-height:1.5;min-height:50px;border-radius:4px}'
    + '.pr-sigs{margin-top:30px;display:grid;grid-template-columns:1fr 1fr;gap:30px}'
    + '.pr-sig-label{font-weight:600;margin-bottom:30px;font-size:11px}'
    + '.pr-sig-line{border-bottom:1px solid #333;min-height:18px;font-size:12px;font-weight:600}'
    + '.pr-sig-sub{font-size:9px;color:#555;margin-top:2px}'
    + '</style>';
  html += `<div class="pr-meta"><b>${orgName}</b></div>`;
  html += `<div class="pr-title">ПРЕДПИСАНИЕ № ${prescription.number || prescription.id || '____'}</div>`;
  html += '<div class="pr-sub">об устранении выявленных нарушений на объекте строительства</div>';
  html += `<div class="pr-row"><span>${project.city || 'г. ____________'}</span><span>${formatPrescriptionDate(new Date().toISOString().slice(0, 10))}</span></div>`;
  html += `<div class="pr-item"><b>Объект:</b> ${prescription.projectName || '____________'}</div>`;
  html += `<div class="pr-item"><b>Заказчик:</b> ${project.client || '____________'}</div>`;
  html += `<div class="pr-item"><b>Кем выдано:</b> ${prescription.issuedBy || '____________'} (${prescription.issuedByRole || '____________'})</div>`;
  html += `<div class="pr-item"><b>Приоритет:</b> ${prescription.priority || '—'}</div>`;
  html += `<div class="pr-item"><b>Описание нарушения:</b><div class="pr-block">${((prescription.violation || prescription.description || '').replace(/\n/g, '<br/>') || '(не указано)')}</div></div>`;
  if (prescription.deadline) html += `<div class="pr-item"><b>Срок устранения:</b> ${formatPrescriptionDate(prescription.deadline)}</div>`;
  if (prescription.responsible) html += `<div class="pr-item"><b>Ответственный за устранение:</b> ${prescription.responsible}</div>`;
  html += `<div class="pr-item"><b>Статус:</b> ${prescription.status || 'Открыто'}</div>`;
  if (prescription.photoUrl) html += '<div class="pr-item"><b>Фотофиксация нарушения прилагается.</b></div>';
  html += '<div class="pr-sigs">';
  html += `<div><div class="pr-sig-label">Выдал предписание:</div><div class="pr-sig-line">${prescription.issuedBy || ''}</div><div class="pr-sig-sub">(должность, ФИО, подпись)</div></div>`;
  html += '<div><div class="pr-sig-label">Получил, обязуюсь устранить:</div><div class="pr-sig-line"></div><div class="pr-sig-sub">(должность, ФИО подрядчика, подпись)</div></div>';
  html += '</div>';
  html += '<p style="margin-top:30px;font-size:10px;color:#555;text-align:center">Форма соответствует методическим указаниям МДС 12-46.2008. Подлежит исполнению в указанный срок.</p>';
  return html;
};

export const buildTBContentDoc = (entry = {}, context = {}) => {
  const { companyRequisites = {}, companyName = '' } = context;
  const instruction = TB_INSTRUCTIONS[entry.type] || '<p>Общие требования безопасности.</p>';
  let html = `<h2 style="text-align:center">${String(entry.type || '').toUpperCase()}</h2>`;
  html += `<p>Организация: ${companyTitle(companyRequisites, companyName)}</p>`;
  html += `<p>Объект: <b>${entry.project}</b> | Дата: <b>${entry.date}</b></p>${instruction}`;
  html += '<table><tr><th>N</th><th>ФИО</th><th>Должность</th><th>Подпись</th><th>Дата</th></tr>';
  (entry.participants || []).forEach((participant, index) => {
    html += `<tr><td>${index + 1}</td><td>${participant}</td><td></td><td style="min-width:120px"></td><td>${entry.date}</td></tr>`;
  });
  html += '</table><div class="signatures"><div class="sig"><div class="sig-line">Инструктаж провёл</div></div></div>';
  return html;
};

export const buildPricelistDocContent = (pricelist = {}, items = [], context = {}) => {
  const { companyRequisites = {}, companyName = '' } = context;
  const categories = [...new Set(items.map((item) => item.category))];
  let html = `<h2 style="text-align:center">ПРАЙС-ЛИСТ</h2><p><b>${companyTitle(companyRequisites, companyName, '')}</b> | ${pricelist.name} | ${new Date().toLocaleDateString('ru-RU')}</p>`;
  categories.forEach((category) => {
    html += `<h3 style="color:#f97316;border-bottom:2px solid #f97316;padding-bottom:5px">${category || 'Общее'}</h3><table><tr><th>Наименование</th><th>Ед.</th><th>Цена (руб.)</th></tr>`;
    items.filter((item) => item.category === category).forEach((item) => {
      html += `<tr><td>${item.name}</td><td>${item.unit}</td><td>${(item.price * pricelist.coefficient).toLocaleString()}</td></tr>`;
    });
    html += '</table>';
  });
  return html;
};

export const buildPositionInstructionDocContent = (role, name, context = {}) => {
  const { companyRequisites = {}, companyName = '' } = context;
  const instruction = POSITION_INSTRUCTIONS[role] || '<h2>ДОЛЖНОСТНАЯ ИНСТРУКЦИЯ</h2>';
  return `${instruction}<p><b>Организация:</b> ${companyTitle(companyRequisites, companyName)}</p><div class="signatures"><div class="sig"><div class="sig-line">Директор<br/>${companyRequisites.directorName || ''}</div></div><div class="sig"><div class="sig-line">Ознакомлен<br/><b>${name}</b></div></div></div>`;
};

export const buildPassportDocContent = (project = {}, context = {}) => {
  const {
    companyRequisites = {},
    companyName = '',
    rooms = [],
    roomWindows = [],
    roomDoors = [],
    expByCategory = () => ({}),
    isFinanceRole = () => false,
    getRoomNetWall = () => 0,
    calcWindowArea = () => 0,
    calcDoorArea = () => 0,
    calcWindowReveals = () => 0,
    calcDoorReveals = () => 0,
  } = context;

  const projectRooms = rooms.filter((room) => room.project === project.name);
  const categoryTotals = expByCategory(project.name);
  const totalExpenses = Object.values(categoryTotals).reduce((sum, value) => sum + value, 0);
  let html = `<h2 style="text-align:center">ПАСПОРТ ОБЪЕКТА</h2><h3 style="text-align:center">${project.name}</h3>`;
  html += `<p>Организация: ${companyTitle(companyRequisites, companyName)}</p>`;
  html += `<table><tr><th>Заказчик</th><td>${project.client}</td></tr>${isFinanceRole() ? `<tr><th>Бюджет</th><td>${project.budget.toLocaleString()} руб.</td></tr>` : ''}<tr><th>Статус</th><td>${project.status}</td></tr></table>`;
  html += '<h3>ПОМЕЩЕНИЯ:</h3><table><tr><th>Помещение</th><th>Пол м2</th><th>Стены м2</th><th>Чистые стены</th><th>Потолок м2</th><th>Тип потолка</th><th>Окна</th><th>Двери</th></tr>';
  projectRooms.forEach((room) => {
    const wins = roomWindows.filter((windowItem) => windowItem.room_id === room.id);
    const doors = roomDoors.filter((door) => door.room_id === room.id);
    const netWall = getRoomNetWall(room);
    const winInfo = wins.length > 0 ? `${wins.length}шт/${wins.reduce((sum, windowItem) => sum + calcWindowArea(windowItem), 0).toFixed(1)}м2` : '—';
    const doorInfo = doors.length > 0 ? `${doors.length}шт/${doors.reduce((sum, door) => sum + calcDoorArea(door), 0).toFixed(1)}м2` : '—';
    html += `<tr><td>${room.name}</td><td>${room.floorArea}</td><td>${room.wallArea}</td><td>${netWall}</td><td>${room.ceilingArea}</td><td>${room.ceiling_type || room.ceilingType || '—'}</td><td>${winInfo}</td><td>${doorInfo}</td></tr>`;
  });
  html += '</table>';
  if (projectRooms.length > 0) {
    html += '<h3>ОТКОСЫ:</h3><table><tr><th>Помещение</th><th>Откосы окон м2</th><th>Откосы дверей м2</th></tr>';
    projectRooms.forEach((room) => {
      const wins = roomWindows.filter((windowItem) => windowItem.room_id === room.id);
      const doors = roomDoors.filter((door) => door.room_id === room.id);
      const winReveals = wins.reduce((sum, windowItem) => sum + calcWindowReveals(windowItem), 0).toFixed(2);
      const doorReveals = doors.reduce((sum, door) => sum + calcDoorReveals(door), 0).toFixed(2);
      html += `<tr><td>${room.name}</td><td>${winReveals}</td><td>${doorReveals}</td></tr>`;
    });
    html += '</table>';
  }
  if (isFinanceRole()) {
    html += '<h3>ФИНАНСЫ:</h3><table>';
    EXPENSE_CATEGORIES.forEach((category) => {
      html += `<tr><td>${category.label}</td><td>${Number(categoryTotals[category.id] || 0).toLocaleString()} руб.</td></tr>`;
    });
    const budget = Number(project.budget || 0);
    html += `<tr><td><b>Итого:</b></td><td><b>${totalExpenses.toLocaleString()} руб.</b></td></tr>`;
    html += `<tr><td>Бюджет:</td><td>${budget.toLocaleString()} руб.</td></tr>`;
    html += `<tr><td><b>Остаток:</b></td><td><b>${(budget - totalExpenses).toLocaleString()} руб.</b></td></tr></table>`;
  }
  return html;
};
