import { docEsc, normalizeDocDate, parseWorkMaterials, photoCount, workDocDate } from './documentFormatUtils';
import { fmtMeasure } from './measureUtils';
import {
  companyTitle,
  directorDocStyles,
  fmtDocMoney,
  formatHiddenActDate,
  formatJournalDate,
  formatShortDate,
} from './printDocumentShared';

export { directorDocStyles, fmtDocMoney } from './printDocumentShared';

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

export const buildDailyObjectReportDocContent = (date, context = {}) => {
  const {
    companyRequisites = {},
    companyName = '',
    user = null,
    projects = [],
    workJournal = [],
  } = context;
  const orgName = companyTitle(companyRequisites || {}, companyName, 'СтройКа');
  const targetDate = normalizeDocDate(date);
  const works = workJournal.filter((work) => workDocDate(work) === targetDate);
  const activeProjectNames = new Set(projects.filter((project) => (
    !project.archived && project.status !== 'Завершён'
  )).map((project) => project.name).filter(Boolean));
  const projectsWithWorks = Array.from(new Set(works.map((work) => work.project || 'Без объекта'))).sort((a, b) => a.localeCompare(b, 'ru'));
  const missingProjects = Array.from(activeProjectNames).filter((name) => !projectsWithWorks.includes(name)).sort((a, b) => a.localeCompare(b, 'ru'));
  const totalAmount = works.reduce((sum, work) => sum + Number(work.total || 0), 0);
  const confirmedCount = works.filter((work) => work.status === 'Подтверждено').length;
  const pendingCount = works.filter((work) => !work.status || work.status === 'На проверке' || work.status === 'Автоматически из сметы').length;
  const hiddenCount = works.filter((work) => work.hiddenWork).length;
  const fmtMoney = (value) => `${Math.round(Number(value || 0)).toLocaleString('ru-RU')} ₽`;
  const fmtDate = (value) => {
    const normalized = normalizeDocDate(value);
    return normalized ? new Date(normalized + 'T00:00:00').toLocaleDateString('ru-RU') : '';
  };
  let html = '<style>'
    + '.dor-title{text-align:center;font-weight:700;font-size:17px;margin:0 0 4px}'
    + '.dor-sub{text-align:center;font-size:11px;color:#555;margin:0 0 16px}'
    + '.dor-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin:12px 0 16px}'
    + '.dor-card{border:1px solid #bbb;border-radius:8px;padding:8px;background:#fafafa}'
    + '.dor-card b{display:block;font-size:15px;margin-top:2px}'
    + '.dor-muted{color:#666;font-size:10px}'
    + '.dor-section{margin-top:18px;border-top:1.5px solid #333;padding-top:8px;break-inside:avoid}'
    + '.dor-section h3{font-size:13px;margin:0 0 8px}'
    + '.dor-table{width:100%;border-collapse:collapse;font-size:10.5px;margin:6px 0}'
    + '.dor-table th,.dor-table td{border:1px solid #555;padding:4px 5px;vertical-align:top}'
    + '.dor-table th{background:#f1f5f9;font-weight:700}'
    + '.dor-risk{margin:4px 0;padding:5px 7px;border:1px solid #f59e0b;background:#fffbeb;border-radius:6px;font-size:11px}'
    + '.dor-ok{margin:4px 0;padding:5px 7px;border:1px solid #22c55e;background:#f0fdf4;border-radius:6px;font-size:11px}'
    + '.dor-empty{padding:14px;border:1px dashed #aaa;border-radius:8px;color:#666;text-align:center}'
    + '</style>';
  html += '<div class="dor-title">ЕЖЕДНЕВНЫЙ ОТЧЕТ ПО ОБЪЕКТАМ</div>';
  html += '<div class="dor-sub">' + docEsc(orgName) + ' · ' + docEsc(fmtDate(date)) + ' · сформировал: ' + docEsc(user?.name || '') + '</div>';
  html += '<div class="dor-grid">';
  html += '<div class="dor-card"><span class="dor-muted">Записей</span><b>' + works.length + '</b></div>';
  html += '<div class="dor-card"><span class="dor-muted">Подтверждено</span><b>' + confirmedCount + '</b></div>';
  html += '<div class="dor-card"><span class="dor-muted">На проверке</span><b>' + pendingCount + '</b></div>';
  html += '<div class="dor-card"><span class="dor-muted">Сумма</span><b>' + fmtMoney(totalAmount) + '</b></div>';
  html += '</div>';
  if (!works.length) {
    html += '<div class="dor-empty">За выбранную дату работы в журнале не зафиксированы.</div>';
  }
  projectsWithWorks.forEach((projectName) => {
    const list = works.filter((work) => (work.project || 'Без объекта') === projectName);
    const project = projects.find((item) => item.name === projectName) || {};
    const byStatus = list.reduce((acc, work) => {
      const key = work.status || 'Без статуса';
      acc[key] = (acc[key] || 0) + 1;
      return acc;
    }, {});
    const byUnit = list.reduce((acc, work) => {
      if (work.unit && Number(work.quantity || 0) > 0) acc[work.unit] = (acc[work.unit] || 0) + Number(work.quantity || 0);
      return acc;
    }, {});
    const projectSum = list.reduce((sum, work) => sum + Number(work.total || 0), 0);
    const materialsList = [];
    list.forEach((work) => parseWorkMaterials(work.materialsUsed).forEach((material) => materialsList.push({
      work: work.description || '',
      name: material.name || material.materialName || material.material || String(material),
      qty: material.quantity || material.qty || '',
      unit: material.unit || '',
    })));
    const risks = [];
    list.forEach((work) => {
      const label = work.description || 'Запись без описания';
      if (!work.status || work.status === 'На проверке' || work.status === 'Автоматически из сметы') risks.push(label + ': требуется подтверждение.');
      if (work.status === 'Отклонено') risks.push(label + ': работа отклонена.');
      if (!work.photoUrl && Number(work.quantity || 0) > 0) risks.push(label + ': нет фотофиксации.');
      if (work.hiddenWork) risks.push(label + ': скрытая работа, проверить АОСР.');
      if (work.qualityStatus && !(String(work.qualityStatus).toLowerCase().includes('прин') || String(work.qualityStatus).toLowerCase().includes('норм'))) risks.push(label + ': статус качества - ' + work.qualityStatus + '.');
      if ((work.comment || '').toLowerCase().includes('материал') && !work.materialsUsed) risks.push(label + ': в комментарии есть материалы, но списание не указано.');
    });
    html += '<div class="dor-section">';
    html += '<h3>' + docEsc(projectName) + '</h3>';
    html += '<p><b>Заказчик:</b> ' + docEsc(project.client || 'не указан') + ' &nbsp; <b>Статус объекта:</b> ' + docEsc(project.status || '') + '</p>';
    html += '<p><b>Записей:</b> ' + list.length + ' &nbsp; <b>Статусы:</b> ' + Object.entries(byStatus).map(([key, value]) => docEsc(key) + ': ' + value).join(', ') + ' &nbsp; <b>Сумма:</b> ' + fmtMoney(projectSum) + '</p>';
    html += '<p><b>Объемы:</b> ' + (Object.keys(byUnit).length ? Object.entries(byUnit).map(([unit, qty]) => fmtMeasure(qty, unit)).join(', ') : 'нет данных') + '</p>';
    html += '<table class="dor-table"><tr><th>N</th><th>Работа</th><th>Раздел</th><th>Исполнитель</th><th>Кол-во</th><th>Статус</th><th>Комментарий</th><th>Фото</th></tr>';
    list.forEach((work, index) => {
      html += '<tr><td>' + (index + 1) + '</td><td>' + docEsc(work.description || '') + '</td><td>' + docEsc(work.sectionName || '') + '</td><td>' + docEsc(work.masterName || work.master_name || '') + '</td><td>' + docEsc(fmtMeasure(work.quantity, work.unit)) + '</td><td>' + docEsc(work.status || '') + '</td><td>' + docEsc(work.comment || '') + '</td><td>' + photoCount(work.photoUrl) + '</td></tr>';
    });
    html += '</table>';
    if (materialsList.length) {
      html += '<p><b>Материалы:</b></p><table class="dor-table"><tr><th>Работа</th><th>Материал</th><th>Кол-во</th></tr>';
      materialsList.slice(0, 25).forEach((material) => {
        html += '<tr><td>' + docEsc(material.work) + '</td><td>' + docEsc(material.name) + '</td><td>' + docEsc(String(material.qty || '') + ' ' + String(material.unit || '')) + '</td></tr>';
      });
      html += '</table>';
    } else {
      html += '<p><b>Материалы:</b> списания в журнале не указаны.</p>';
    }
    const dedupRisks = Array.from(new Set(risks));
    if (dedupRisks.length) {
      dedupRisks.slice(0, 12).forEach((risk) => { html += '<div class="dor-risk">' + docEsc(risk) + '</div>'; });
    } else {
      html += '<div class="dor-ok">Критичных отклонений по данным журнала не найдено.</div>';
    }
    html += '</div>';
  });
  if (missingProjects.length) {
    html += '<div class="dor-section"><h3>Объекты без записей за день</h3><p>' + missingProjects.map(docEsc).join(', ') + '</p></div>';
  }
  html += '<div class="dor-section"><h3>Итоговые действия</h3><ul>';
  html += pendingCount ? '<li>Проверить и подтвердить работы со статусом "На проверке".</li>' : '<li>Все зафиксированные работы подтверждены или не требуют проверки по статусу.</li>';
  html += hiddenCount ? '<li>Проверить АОСР/исполнительную документацию по скрытым работам: ' + hiddenCount + '.</li>' : '';
  html += '<li>Уточнить материалы по объектам, где списания не заполнены.</li>';
  html += '<li>Запросить фотофиксацию по строкам без фото.</li>';
  html += '</ul></div>';
  return html;
};

export const buildJPRDocContent = (projectName, context = {}) => {
  const {
    companyRequisites = null,
    companyName = '',
    projects = [],
    users = [],
    workJournal = [],
    hiddenActs = [],
    materialInspections = [],
    prescriptionsList = [],
    tbJournal = [],
    cableJournal = [],
    weatherLog = [],
  } = context;
  const works = workJournal.filter((item) => item.project === projectName && item.status === 'Подтверждено');
  const project = projects.find((item) => item.name === projectName) || {};
  const req = companyRequisites || {};
  const orgName = req.fullName || req.shortName || companyName || '_____';
  const itr = users.filter((item) => ['прораб', 'главный_инженер', 'стройконтроль'].includes(item.role));
  const acts = hiddenActs.filter((item) => item.projectName === projectName);
  const inspections = (materialInspections || []).filter((item) => item.projectName === projectName);
  const prescs = (prescriptionsList || []).filter((item) => item.projectName === projectName);
  const tb = (tbJournal || []).filter((item) => item.project === projectName);
  const cables = (cableJournal || []).filter((item) => item.projectName === projectName);
  const byDate = {};
  works.forEach((work) => {
    if (!byDate[work.date]) byDate[work.date] = {};
    if (!byDate[work.date][work.masterName]) byDate[work.date][work.masterName] = [];
    byDate[work.date][work.masterName].push(work);
  });
  let html = '<style>'
    + '.jpr-title{text-align:center;font-weight:700;font-size:15px;margin:14px 0 4px}'
    + '.jpr-sub{text-align:center;font-size:12px;margin:0 0 16px;color:#444}'
    + '.jpr-section{margin-top:18px;border-top:1.5px solid #333;padding-top:8px}'
    + '.jpr-section h3{font-size:13px;margin:4px 0 8px;font-weight:700;color:#111}'
    + '.jpr-table{border-collapse:collapse;width:100%;font-size:11px;margin:6px 0}'
    + '.jpr-table th,.jpr-table td{border:1px solid #555;padding:4px 6px;vertical-align:top}'
    + '.jpr-table th{background:#f3f4f6;font-weight:600}'
    + '.jpr-row{display:grid;grid-template-columns:200px 1fr;gap:4px 10px;font-size:11px;margin:4px 0}'
    + '.jpr-sigs{margin-top:24px;display:grid;grid-template-columns:1fr 1fr;gap:30px}'
    + '.jpr-sig-line{border-bottom:1px solid #333;min-height:18px;font-size:12px;font-weight:600}'
    + '.jpr-sig-sub{font-size:9px;color:#555;margin-top:2px}'
    + '</style>';
  html += '<div class="jpr-title">ОБЩИЙ ЖУРНАЛ РАБОТ</div>';
  html += '<div class="jpr-sub">по форме РД-11-05-2007 «Порядок ведения общего и (или) специального журнала учёта выполнения работ при строительстве»</div>';
  html += '<div class="jpr-row"><span><b>Объект капитального строительства:</b></span><span>' + (projectName || '____________') + '</span></div>';
  html += '<div class="jpr-row"><span><b>Местоположение:</b></span><span>' + (project.address || project.city || '____________') + '</span></div>';
  html += '<div class="jpr-row"><span><b>Застройщик (тех. заказчик):</b></span><span>' + (project.client || '____________') + '</span></div>';
  html += '<div class="jpr-row"><span><b>Лицо, осуществляющее строительство:</b></span><span>' + orgName + '</span></div>';
  html += '<div class="jpr-row"><span><b>Срок строительства:</b></span><span>' + (project.startDate || '__.__.____') + ' — ' + (project.deadline || '__.__.____') + '</span></div>';
  html += '<div class="jpr-row"><span><b>Дата составления журнала:</b></span><span>' + new Date().toLocaleDateString('ru-RU') + '</span></div>';
  html += '<div class="jpr-section"><h3>Раздел 1. Список инженерно-технического персонала, занятых строительством</h3>';
  html += '<table class="jpr-table"><tr><th>№</th><th>ФИО</th><th>Должность</th><th>Период работы</th></tr>';
  itr.forEach((item, index) => { html += '<tr><td>' + (index + 1) + '</td><td>' + (item.name || '') + '</td><td>' + (item.role || '') + '</td><td>—</td></tr>'; });
  if (itr.length === 0) html += '<tr><td colspan="4" style="text-align:center;color:#888">(не указаны)</td></tr>';
  html += '</table></div>';
  html += '<div class="jpr-section"><h3>Раздел 2. Сведения о стройконтроле застройщика/заказчика</h3>';
  html += '<p style="font-size:11px;color:#444">Технический надзор / стройконтроль осуществляется лицами с подписями в АОСР и актах осмотра. См. раздел 3 настоящего журнала и Раздел 6 (АОСР).</p></div>';
  html += '<div class="jpr-section"><h3>Раздел 3. Сведения о выполнении работ (по датам)</h3>';
  if (Object.keys(byDate).length === 0) {
    html += '<p style="color:#888;font-size:11px;text-align:center">Подтверждённых записей по проекту нет</p>';
  } else {
    Object.keys(byDate).sort().forEach((date) => {
      const weather = weatherLog.find((item) => item.projectName === projectName && item.date === date);
      html += '<p style="font-weight:700;margin-top:8px">' + date + (weather ? ' · 🌤 ' + weather.condition + ', ' + weather.temperature + '°C' : '') + '</p>';
      Object.keys(byDate[date]).forEach((masterName) => {
        html += '<p style="font-size:11px;margin:3px 0;color:#444">Исполнитель: <b>' + masterName + '</b></p>';
        html += '<table class="jpr-table"><tr><th>№</th><th>Вид работ</th><th>Раздел сметы</th><th>Ед.</th><th>Кол-во</th><th>Нормативы</th><th>ИТР</th><th>Принял</th></tr>';
        byDate[date][masterName].forEach((work, index) => {
          html += '<tr><td>' + (index + 1) + '</td><td>' + (work.description || '') + (work.unexpectedWorkId ? ' <b>🆕</b>' : '') + (work.hiddenWork ? ' <b>🔒</b>' : '') + '</td><td>' + (work.sectionName || '—') + '</td><td>' + (work.unit || '') + '</td><td>' + (work.quantity || 0) + '</td><td>' + (work.normatives || '—') + '</td><td>' + (work.responsibleItr || '—') + '</td><td>' + (work.confirmedBy || '') + '</td></tr>';
        });
        html += '</table>';
      });
    });
  }
  html += '</div>';
  html += '<div class="jpr-section"><h3>Раздел 4. Сведения о стройконтроле лица, осуществляющего строительство</h3>';
  html += '<p style="font-size:11px;color:#444">Контроль качества осуществляется ИТР генподрядчика. Зафиксированные предписания: ' + prescs.length + ' (см. Раздел 7).</p></div>';
  html += '<div class="jpr-section"><h3>Раздел 5. Сведения о входном контроле материалов</h3>';
  if (inspections.length === 0) {
    html += '<p style="color:#888;font-size:11px;text-align:center">Записей входного контроля нет (ведётся в отдельном журнале СП 48.13330.2019)</p>';
  } else {
    html += '<table class="jpr-table"><tr><th>№</th><th>Дата</th><th>Материал</th><th>Поставщик</th><th>Партия</th><th>Сертификат</th><th>Результат</th></tr>';
    inspections.slice(0, 30).forEach((item, index) => {
      html += '<tr><td>' + (index + 1) + '</td><td>' + (item.receivedAt || '') + '</td><td>' + (item.materialName || '') + '</td><td>' + (item.supplier || '') + '</td><td>' + (item.batchNumber || '—') + '</td><td>' + (item.certificateNumber || item.passportNumber || '—') + '</td><td>' + (item.visualInspectionResult || (item.inspected ? 'Проверено' : '—')) + '</td></tr>';
    });
    html += '</table>';
  }
  html += '</div>';
  html += '<div class="jpr-section"><h3>Раздел 6. Перечень специальных журналов и актов</h3>';
  html += '<table class="jpr-table"><tr><th>Документ</th><th>Записей</th><th>Норматив</th></tr>';
  html += '<tr><td>АОСР — акты освидетельствования скрытых работ</td><td>' + acts.length + ' (' + acts.filter((item) => item.status === 'Подписан').length + ' подписано)</td><td>СНиП 12-01-2004</td></tr>';
  html += '<tr><td>Журнал входного контроля материалов</td><td>' + inspections.length + '</td><td>СП 48.13330.2019</td></tr>';
  html += '<tr><td>Журнал кабельной продукции</td><td>' + cables.length + '</td><td>СП 76.13330, ПУЭ</td></tr>';
  html += '<tr><td>Журнал инструктажей ТБ</td><td>' + tb.length + '</td><td>ГОСТ 12.0.004-2015</td></tr>';
  html += '</table></div>';
  html += '<div class="jpr-section"><h3>Раздел 7. Сведения о замечаниях и предписаниях контролирующих органов</h3>';
  if (prescs.length === 0) {
    html += '<p style="color:#888;font-size:11px;text-align:center">Предписаний нет</p>';
  } else {
    html += '<table class="jpr-table"><tr><th>№</th><th>Дата</th><th>Кем выдано</th><th>Описание нарушения</th><th>Срок</th><th>Статус</th></tr>';
    prescs.forEach((item, index) => {
      html += '<tr><td>' + (index + 1) + '</td><td>' + (item.deadline || '') + '</td><td>' + (item.issuedBy || '') + ' (' + (item.issuedByRole || '') + ')</td><td>' + (item.violation || item.description || '') + '</td><td>' + (item.deadline || '') + '</td><td>' + (item.status || '') + '</td></tr>';
    });
    html += '</table>';
  }
  html += '</div>';
  html += '<div class="jpr-sigs">';
  html += '<div><div style="font-size:11px;font-weight:600;margin-bottom:30px">Ответственный за ведение журнала (производитель работ):</div><div class="jpr-sig-line"></div><div class="jpr-sig-sub">(должность, ФИО, подпись)</div></div>';
  html += '<div><div style="font-size:11px;font-weight:600;margin-bottom:30px">Представитель застройщика (технадзора):</div><div class="jpr-sig-line"></div><div class="jpr-sig-sub">(должность, ФИО, подпись)</div></div>';
  html += '</div>';
  html += '<p style="margin-top:18px;font-size:10px;color:#666;text-align:center">Журнал ведётся в соответствии с РД-11-05-2007 и СП 48.13330.2019 «Организация строительства». Является обязательным документом исполнительной документации.</p>';
  return html;
};

export const buildKS2DocContent = (project = {}, data = {}, context = {}) => {
  const { companyRequisites = {}, companyName = '' } = context;
  const {
    sourceItems = [],
    additionalVolumeItems = [],
    outsideEstimateItems = [],
  } = data;
  const req = companyRequisites || {};
  const tableRows = (rows) => rows.map((item, index) => (
    '<tr><td>' + (index + 1) + '</td><td>' + (item.description || '') + '</td><td>' + (item.unit || '') + '</td><td>' + (item.quantity || '') + '</td><td>' + Number(item.pricePerUnit || 0).toLocaleString() + '</td><td>' + Number(item.total || 0).toLocaleString() + '</td></tr>'
  )).join('');
  const sectionTable = (title, rows) => {
    const total = rows.reduce((sum, item) => sum + Number(item.total || 0), 0);
    return '<h3>' + title + '</h3>'
      + '<table><tr><th>N</th><th>Наименование работ</th><th>Ед.</th><th>Кол-во</th><th>Цена</th><th>Сумма</th></tr>'
      + tableRows(rows)
      + '<tr><td colspan="5"><b>Итого по разделу:</b></td><td><b>' + total.toLocaleString() + ' руб.</b></td></tr></table>';
  };
  const mainTotal = sourceItems.reduce((sum, item) => sum + Number(item.total || 0), 0);
  const changesTotal = [...additionalVolumeItems, ...outsideEstimateItems].reduce((sum, item) => sum + Number(item.total || 0), 0);
  let html = '<h2 style="text-align:center">УНИФИЦИРОВАННАЯ ФОРМА КС-2</h2><h3 style="text-align:center">АКТ О ПРИЁМКЕ ВЫПОЛНЕННЫХ РАБОТ</h3>';
  html += '<table><tr><th>Организация</th><td>' + (req.fullName || companyName || '') + '</td><th>Объект</th><td>' + (project.name || '') + '</td></tr></table>';
  html += sectionTable('Раздел 1. Основные работы (по смете)', sourceItems).replace('Итого по разделу:', 'Итого по разделу 1:');
  if (additionalVolumeItems.length > 0) html += sectionTable('Раздел 2. Дополнительные объёмы к строкам сметы', additionalVolumeItems).replace('Итого по разделу:', 'Итого по разделу 2:');
  if (outsideEstimateItems.length > 0) html += sectionTable('Раздел 3. Работы вне сметы', outsideEstimateItems).replace('Итого по разделу:', 'Итого по разделу 3:');
  html += '<p style="text-align:right;font-size:14px"><b>ВСЕГО к оплате: ' + (mainTotal + changesTotal).toLocaleString() + ' руб.</b></p>';
  html += '<div class="signatures"><div class="sig"><div class="sig-line">Сдал: ' + (req.directorName || '') + '</div></div><div class="sig"><div class="sig-line">Принял:</div></div></div>';
  return html;
};

export const buildKS3DocContent = (project = {}, context = {}) => {
  const {
    companyRequisites = null,
    companyName = '',
    ks2ItemsFromEstimate = () => [],
    estimateChangeRowsForDocs = () => [],
  } = context;
  const rows = ks2ItemsFromEstimate(project);
  const bySection = {};
  rows.forEach((row) => {
    const key = row.section || 'Работы по смете';
    bySection[key] = (bySection[key] || 0) + Number(row.total || 0);
  });
  const worksTotal = rows.reduce((sum, row) => sum + Number(row.total || 0), 0);
  const additionalVolumeItems = estimateChangeRowsForDocs(project.name, 'additional');
  const outsideEstimateItems = estimateChangeRowsForDocs(project.name, 'outside');
  const addTotal = additionalVolumeItems.reduce((sum, item) => sum + Number(item.total || 0), 0);
  const outTotal = outsideEstimateItems.reduce((sum, item) => sum + Number(item.total || 0), 0);
  const grand = worksTotal + addTotal + outTotal;
  const req = companyRequisites || {};
  let html = '<h2 style="text-align:center">УНИФИЦИРОВАННАЯ ФОРМА № КС-3</h2><h3 style="text-align:center">СПРАВКА О СТОИМОСТИ ВЫПОЛНЕННЫХ РАБОТ И ЗАТРАТ</h3>';
  html += '<table><tr><th>Организация (подрядчик)</th><td>' + (req.fullName || req.shortName || companyName || '_____') + '</td><th>Объект</th><td>' + project.name + '</td></tr></table>';
  html += '<table><tr><th>N</th><th>Наименование работ и затрат</th><th>Стоимость выполненных работ (руб.)</th></tr>';
  let index = 0;
  Object.keys(bySection).forEach((section) => {
    index += 1;
    html += '<tr><td>' + index + '</td><td>' + section + '</td><td style="text-align:right">' + Math.round(bySection[section]).toLocaleString('ru-RU') + '</td></tr>';
  });
  if (addTotal > 0) {
    index += 1;
    html += '<tr><td>' + index + '</td><td>Дополнительные объёмы к строкам сметы</td><td style="text-align:right">' + addTotal.toLocaleString('ru-RU') + '</td></tr>';
  }
  if (outTotal > 0) {
    index += 1;
    html += '<tr><td>' + index + '</td><td>Работы вне сметы</td><td style="text-align:right">' + outTotal.toLocaleString('ru-RU') + '</td></tr>';
  }
  if (index === 0) html += '<tr><td colspan="3" style="text-align:center;color:#777">Выполненных работ по смете пока нет</td></tr>';
  html += '<tr><td colspan="2"><b>ИТОГО выполнено работ:</b></td><td style="text-align:right"><b>' + Math.round(grand).toLocaleString('ru-RU') + ' руб.</b></td></tr>';
  html += '<tr><td colspan="2">в т.ч. НДС 20%:</td><td style="text-align:right">' + Math.round(grand / 120 * 20).toLocaleString('ru-RU') + ' руб.</td></tr>';
  html += '</table>';
  html += '<p style="font-size:11px;color:#555">Стоимость рассчитана по выполненным позициям сметы (цена заказчику) и соответствует Разделу 1 формы КС-2 за отчётный период.</p>';
  html += '<div class="signatures"><div class="sig"><div class="sig-line">Подрядчик<br/>' + (req.directorName || '') + '</div></div><div class="sig"><div class="sig-line">Заказчик</div></div></div>';
  return html;
};

export {
  buildEstimateReconciliationDocContent,
  buildEstimateMeasurementComparisonDocContent,
  buildWorkJournalEstimateReconciliationDocContent,
  buildMaterialNormCoverageDocContent,
  buildSupplyControlReportDocContent,
  buildEstimateControlReportDocContent,
  buildEstimateDiffDocContent,
} from './print/estimateControlDocumentBuilders';

export {
  buildMasterActDocContent,
  buildBrigadeActDocContent,
} from './print/contractorActDocumentBuilders';

export const buildHiddenActDocContent = (act = {}, context = {}) => {
  const { companyRequisites = null, companyName = '' } = context;
  const req = companyRequisites || {};
  const orgName = req.fullName || req.shortName || companyName || '_____';
  const photoCnt = (act.photos || '').split(',').filter(Boolean).length;
  const certCnt = (act.certificates || '').split(',').filter(Boolean).length;
  const sig = (label, name, date) => (
    '<div class="hwa-sig">'
      + '<div class="hwa-sig-label">' + label + '</div>'
      + '<div class="hwa-sig-line">' + (name || '') + '</div>'
      + '<div class="hwa-sig-sub">(должность, ФИО, подпись)</div>'
      + '<div class="hwa-sig-date">' + (date ? formatHiddenActDate(date) : '«___» __________ 20__ г.') + '</div>'
      + '</div>'
  );
  const concl = act.conclusion || 'Работы выполнены в соответствии с проектной документацией, требованиями технических регламентов, СНиП и ТУ. Разрешается производство последующих работ.';
  let html = '';
  html += '<style>'
    + '.hwa-meta{margin:6px 0;font-size:12px}'
    + '.hwa-title{text-align:center;font-weight:700;font-size:14px;margin:18px 0 4px}'
    + '.hwa-sub{text-align:center;font-size:13px;margin:0 0 18px}'
    + '.hwa-row{display:flex;justify-content:space-between;font-size:12px;margin:4px 0}'
    + '.hwa-item{margin:8px 0;font-size:12px;line-height:1.5}'
    + '.hwa-item b{display:inline-block;min-width:18px}'
    + '.hwa-val{display:inline-block;border-bottom:1px solid #333;min-width:60%;padding:1px 4px}'
    + '.hwa-block{border-top:1px solid #333;margin-top:6px;padding-top:8px;font-size:12px;line-height:1.5}'
    + '.hwa-sigs{margin-top:30px;display:grid;grid-template-columns:1fr 1fr;gap:20px}'
    + '.hwa-sig{font-size:11px}'
    + '.hwa-sig-label{font-weight:600;margin-bottom:30px}'
    + '.hwa-sig-line{border-bottom:1px solid #333;min-height:18px;font-size:12px;font-weight:600}'
    + '.hwa-sig-sub{font-size:10px;color:#555;margin-top:2px}'
    + '.hwa-sig-date{margin-top:8px;font-size:11px}'
    + '@media print{.hwa-title{font-size:13px}}'
    + '</style>';
  html += '<div class="hwa-meta"><b>' + orgName + '</b></div>';
  html += '<div class="hwa-title">АКТ</div>';
  html += '<div class="hwa-sub">освидетельствования скрытых работ № <b>' + act.actNumber + '</b></div>';
  html += '<div class="hwa-row"><span>' + (act.city ? act.city : 'г. ____________') + '</span><span>' + formatHiddenActDate(act.workDate || new Date().toISOString().slice(0, 10)) + '</span></div>';
  html += '<div class="hwa-item"><b>Объект капитального строительства:</b> <span class="hwa-val">' + (act.projectName || '') + '</span></div>';
  html += '<div class="hwa-item"><b>Представители:</b><br/>';
  html += '— застройщика (технического заказчика): <span class="hwa-val">' + (act.signedCustomer || '') + '</span><br/>';
  html += '— лица, осуществляющего строительный контроль: <span class="hwa-val">' + (act.signedSupervisor || '') + '</span><br/>';
  html += '— лица, осуществляющего строительство (генподрядчик): <span class="hwa-val">' + (act.signedContractor || '') + '</span><br/>';
  html += '— лица, выполнившего работы, подлежащие освидетельствованию: <span class="hwa-val">' + (act.signedSubcontractor || act.brigade || '') + '</span>';
  html += '</div>';
  html += '<div class="hwa-item">произвели осмотр работ, выполненных <span class="hwa-val">' + (act.brigade || '') + '</span>, и составили настоящий акт о нижеследующем:</div>';
  html += '<div class="hwa-item"><b>1.</b> К освидетельствованию предъявлены следующие работы: <span class="hwa-val">' + (act.workName || '') + '</span> в объёме <b>' + act.quantity + ' ' + (act.unit || '') + '</b>' + (act.sectionName ? ' (раздел сметы «' + act.sectionName + '»)' : '') + '.</div>';
  html += '<div class="hwa-item"><b>2.</b> Работы выполнены по проектной документации: <span class="hwa-val">' + (act.projectDocs || '_______________________________________') + '</span></div>';
  html += '<div class="hwa-item"><b>3.</b> При выполнении работ применены: <br/><div class="hwa-block">' + (act.materialsUsed || '_______________________________________').replace(/\n/g, '<br/>') + '</div></div>';
  html += '<div class="hwa-item"><b>4.</b> Предъявлены документы, подтверждающие соответствие работ предъявляемым к ним требованиям: фотофиксация скрытых работ — <b>' + photoCnt + '</b> шт.; сертификаты, паспорта, протоколы испытаний — <b>' + certCnt + '</b> шт. (прилагаются к настоящему акту).</div>';
  html += '<div class="hwa-item"><b>5.</b> Освидетельствованы скрытые работы: <span class="hwa-val">' + (act.workName || '') + '</span></div>';
  html += '<div class="hwa-item"><b>6.</b> Дата окончания работ: <b>' + formatHiddenActDate(act.workDate) + '</b></div>';
  html += '<div class="hwa-item"><b>7.</b> Заключение:<br/><div class="hwa-block">' + concl.replace(/\n/g, '<br/>') + '</div></div>';
  html += '<div class="hwa-sigs">';
  html += sig('Представитель застройщика (технического заказчика):', act.signedCustomer, act.signedCustomerAt);
  html += sig('Представитель лица, осуществляющего строительный контроль:', act.signedSupervisor, act.signedSupervisorAt);
  html += sig('Представитель лица, осуществляющего строительство (генподрядчик):', act.signedContractor, act.signedContractorAt);
  html += sig('Представитель лица, выполнившего работы (субподрядчик):', act.signedSubcontractor || act.brigade, act.signedSubcontractorAt);
  html += '</div>';
  html += '<p style="margin-top:30px;font-size:10px;color:#555;text-align:center">Форма составлена согласно СНиП 12-01-2004 (Приложение 3). Документ сопровождает приёмку скрытых работ перед их закрытием последующими конструкциями.</p>';
  return html;
};

export const buildWorkJournalDocContent = (records = [], projectName, dateFrom, dateTo, context = {}) => {
  const { companyRequisites = null, companyName = '', projects = [] } = context;
  const req = companyRequisites || {};
  const orgName = req.fullName || req.shortName || companyName || '_____';
  const project = projects.find((item) => item.name === projectName) || {};
  const sum = records.reduce((total, record) => total + Number(record.total || 0), 0);
  let html = '<style>'
    + '.wj-meta{margin:6px 0;font-size:11px}'
    + '.wj-title{text-align:center;font-weight:700;font-size:14px;margin:14px 0 4px}'
    + '.wj-sub{text-align:center;font-size:12px;margin:0 0 14px;color:#444}'
    + '.wj-info{display:grid;grid-template-columns:160px 1fr;gap:4px 10px;font-size:11px;margin:10px 0}'
    + '.wj-tbl{border-collapse:collapse;width:100%;font-size:10px;margin-top:10px}'
    + '.wj-tbl th,.wj-tbl td{border:1px solid #333;padding:4px 5px;vertical-align:top}'
    + '.wj-tbl th{background:#f3f4f6;font-weight:600;text-align:center}'
    + '.wj-tbl td.num{text-align:right;white-space:nowrap}'
    + '.wj-foot{margin-top:18px;font-size:11px;color:#444}'
    + '.wj-sigs{margin-top:30px;display:grid;grid-template-columns:1fr 1fr;gap:30px}'
    + '.wj-sig-label{font-weight:600;margin-bottom:30px;font-size:11px}'
    + '.wj-sig-line{border-bottom:1px solid #333;min-height:18px;font-size:12px;font-weight:600}'
    + '.wj-sig-sub{font-size:9px;color:#555;margin-top:2px}'
    + '</style>';
  html += '<div class="wj-meta"><b>' + orgName + '</b></div>';
  html += '<div class="wj-title">ЖУРНАЛ УЧЁТА ВЫПОЛНЕННЫХ РАБОТ</div>';
  html += '<div class="wj-sub">(унифицированная форма № КС-6а, ОКУД 0322005)</div>';
  html += '<div class="wj-info">';
  html += '<span>Заказчик:</span><b>' + (project.client || '____________') + '</b>';
  html += '<span>Подрядчик:</span><b>' + orgName + '</b>';
  html += '<span>Объект:</span><b>' + (projectName || '____________') + '</b>';
  html += '<span>Период:</span><b>' + (dateFrom ? formatJournalDate(dateFrom) : '__.__.____') + ' — ' + (dateTo ? formatJournalDate(dateTo) : '__.__.____') + '</b>';
  html += '</div>';
  html += '<table class="wj-tbl"><thead><tr>';
  html += '<th style="width:24px">№</th><th style="width:60px">Дата</th><th style="width:90px">Раздел сметы</th><th>Наименование работ</th><th style="width:36px">Ед.</th><th style="width:46px">Объём</th><th style="width:100px">Исполнитель</th><th style="width:100px">Ответств. ИТР</th><th style="width:80px">Погода</th><th style="width:90px">Качество</th><th style="width:80px">Стоимость, ₽</th>';
  html += '</tr></thead><tbody>';
  records.forEach((record, index) => {
    html += '<tr>';
    html += '<td class="num">' + (index + 1) + '</td>';
    html += '<td>' + formatJournalDate(record.date) + '</td>';
    html += '<td>' + (record.sectionName || '—') + '</td>';
    html += '<td>' + (record.description || '') + (record.hiddenWork ? ' <b>🔒</b>' : '') + '</td>';
    html += '<td>' + (record.unit || '') + '</td>';
    html += '<td class="num">' + (record.quantity || 0) + '</td>';
    html += '<td>' + (record.masterName || '—') + '</td>';
    html += '<td>' + (record.responsibleItr || '—') + '</td>';
    html += '<td>' + (record.weather || '—') + '</td>';
    html += '<td>' + (record.qualityStatus || record.status || '—') + '</td>';
    html += '<td class="num">' + Number(record.total || 0).toLocaleString('ru-RU') + '</td>';
    html += '</tr>';
  });
  html += '<tr><td colspan="10" style="text-align:right;font-weight:700">ИТОГО, ₽:</td><td class="num" style="font-weight:700">' + sum.toLocaleString('ru-RU') + '</td></tr>';
  html += '</tbody></table>';
  html += '<div class="wj-foot">Журнал ведётся в соответствии с РД-11-05-2007 «Порядок ведения общего и (или) специального журналов учёта выполнения работ при строительстве» и СП 48.13330.2019 «Организация строительства».</div>';
  html += '<div class="wj-sigs">';
  html += '<div><div class="wj-sig-label">Должностное лицо, ответственное за совершение операций и правильность их оформления:</div><div class="wj-sig-line"></div><div class="wj-sig-sub">(должность, подпись, ФИО)</div></div>';
  html += '<div><div class="wj-sig-label">Представитель технического надзора заказчика:</div><div class="wj-sig-line"></div><div class="wj-sig-sub">(должность, подпись, ФИО)</div></div>';
  html += '</div>';
  return html;
};

export const buildMaterialInspectionDocContent = (records = [], projectName, dateFrom, dateTo, context = {}) => {
  const { companyRequisites = null, companyName = '', projects = [] } = context;
  const req = companyRequisites || {};
  const orgName = req.fullName || req.shortName || companyName || '_____';
  const project = projects.find((item) => item.name === projectName) || {};
  let html = '<style>'
    + '.mic-meta{margin:6px 0;font-size:11px}'
    + '.mic-title{text-align:center;font-weight:700;font-size:14px;margin:14px 0 4px}'
    + '.mic-sub{text-align:center;font-size:12px;margin:0 0 14px;color:#444}'
    + '.mic-info{display:grid;grid-template-columns:160px 1fr;gap:4px 10px;font-size:11px;margin:10px 0}'
    + '.mic-tbl{border-collapse:collapse;width:100%;font-size:10px;margin-top:10px}'
    + '.mic-tbl th,.mic-tbl td{border:1px solid #333;padding:4px 5px;vertical-align:top}'
    + '.mic-tbl th{background:#f3f4f6;font-weight:600;text-align:center}'
    + '.mic-tbl td.num{text-align:right;white-space:nowrap}'
    + '.mic-foot{margin-top:18px;font-size:11px;color:#444}'
    + '.mic-sigs{margin-top:30px;display:grid;grid-template-columns:1fr 1fr;gap:30px}'
    + '.mic-sig-label{font-weight:600;margin-bottom:30px;font-size:11px}'
    + '.mic-sig-line{border-bottom:1px solid #333;min-height:18px;font-size:12px;font-weight:600}'
    + '.mic-sig-sub{font-size:9px;color:#555;margin-top:2px}'
    + '</style>';
  html += '<div class="mic-meta"><b>' + orgName + '</b></div>';
  html += '<div class="mic-title">ЖУРНАЛ ВХОДНОГО КОНТРОЛЯ МАТЕРИАЛОВ, КОНСТРУКЦИЙ И ИЗДЕЛИЙ</div>';
  html += '<div class="mic-sub">по СП 48.13330.2019 «Организация строительства», §7.1</div>';
  html += '<div class="mic-info">';
  html += '<span>Заказчик:</span><b>' + (project.client || '____________') + '</b>';
  html += '<span>Подрядчик:</span><b>' + orgName + '</b>';
  html += '<span>Объект:</span><b>' + (projectName || '____________') + '</b>';
  html += '<span>Период:</span><b>' + (dateFrom ? formatJournalDate(dateFrom) : '__.__.____') + ' — ' + (dateTo ? formatJournalDate(dateTo) : '__.__.____') + '</b>';
  html += '</div>';
  html += '<table class="mic-tbl"><thead><tr>';
  html += '<th style="width:24px">№</th><th style="width:60px">Дата приёмки</th><th>Наименование материала</th><th style="width:36px">Ед.</th><th style="width:50px">Кол-во</th><th style="width:110px">Поставщик</th><th style="width:70px">Партия №</th><th style="width:80px">Паспорт №</th><th style="width:80px">Сертификат №</th><th style="width:80px">Протокол №</th><th style="width:90px">Результат осмотра</th><th style="width:90px">Проверил (ФИО)</th><th style="width:60px">Дата осмотра</th><th>Замечания</th>';
  html += '</tr></thead><tbody>';
  records.forEach((record, index) => {
    html += '<tr>';
    html += '<td class="num">' + (index + 1) + '</td>';
    html += '<td>' + formatJournalDate(record.receivedAt) + '</td>';
    html += '<td>' + (record.materialName || '') + '</td>';
    html += '<td>' + (record.unit || '') + '</td>';
    html += '<td class="num">' + (record.quantity || 0) + '</td>';
    html += '<td>' + (record.supplier || '—') + '</td>';
    html += '<td>' + (record.batchNumber || '—') + '</td>';
    html += '<td>' + (record.passportNumber || '—') + '</td>';
    html += '<td>' + (record.certificateNumber || '—') + '</td>';
    html += '<td>' + (record.testProtocolNumber || '—') + '</td>';
    html += '<td>' + (record.visualInspectionResult || '—') + '</td>';
    html += '<td>' + (record.inspectorName || '—') + '</td>';
    html += '<td>' + formatJournalDate(record.inspectedAt) + '</td>';
    html += '<td>' + (record.remarks || '') + '</td>';
    html += '</tr>';
  });
  html += '</tbody></table>';
  html += '<div class="mic-foot">Журнал ведётся в соответствии с СП 48.13330.2019 «Организация строительства» и ГОСТ 24297-2013 «Верификация закупленной продукции. Организация и методы контроля».</div>';
  html += '<div class="mic-sigs">';
  html += '<div><div class="mic-sig-label">Ответственное за входной контроль лицо:</div><div class="mic-sig-line"></div><div class="mic-sig-sub">(должность, подпись, ФИО)</div></div>';
  html += '<div><div class="mic-sig-label">Представитель технического надзора заказчика:</div><div class="mic-sig-line"></div><div class="mic-sig-sub">(должность, подпись, ФИО)</div></div>';
  html += '</div>';
  return html;
};

export const buildCableJournalDocContent = (records = [], projectName, dateFrom, dateTo, context = {}) => {
  const {
    companyRequisites = null,
    companyName = '',
    projects = [],
    cableTypeOf = (cable) => cable?.cableType || 'Кабель',
  } = context;
  const req = companyRequisites || {};
  const orgName = req.fullName || req.shortName || companyName || '_____';
  const project = projects.find((item) => item.name === projectName) || {};
  let html = '<style>'
    + '.cab-meta{margin:6px 0;font-size:11px}'
    + '.cab-title{text-align:center;font-weight:700;font-size:14px;margin:14px 0 4px}'
    + '.cab-sub{text-align:center;font-size:12px;margin:0 0 14px;color:#444}'
    + '.cab-info{display:grid;grid-template-columns:160px 1fr;gap:4px 10px;font-size:11px;margin:10px 0}'
    + '.cab-tbl{border-collapse:collapse;width:100%;font-size:10px;margin-top:10px}'
    + '.cab-tbl th,.cab-tbl td{border:1px solid #333;padding:4px 5px;vertical-align:top}'
    + '.cab-tbl th{background:#f3f4f6;font-weight:600;text-align:center}'
    + '.cab-tbl td.num{text-align:right;white-space:nowrap}'
    + '.cab-foot{margin-top:18px;font-size:11px;color:#444}'
    + '.cab-sigs{margin-top:30px;display:grid;grid-template-columns:1fr 1fr;gap:30px}'
    + '.cab-sig-label{font-weight:600;margin-bottom:30px;font-size:11px}'
    + '.cab-sig-line{border-bottom:1px solid #333;min-height:18px;font-size:12px;font-weight:600}'
    + '.cab-sig-sub{font-size:9px;color:#555;margin-top:2px}'
    + '</style>';
  html += '<div class="cab-meta"><b>' + orgName + '</b></div>';
  html += '<div class="cab-title">ЖУРНАЛ КАБЕЛЬНОЙ ПРОДУКЦИИ</div>';
  html += '<div class="cab-sub">по СП 76.13330 «Электротехнические устройства» и ПУЭ</div>';
  html += '<div class="cab-info">';
  html += '<span>Заказчик:</span><b>' + (project.client || '____________') + '</b>';
  html += '<span>Подрядчик:</span><b>' + orgName + '</b>';
  html += '<span>Объект:</span><b>' + (projectName || '____________') + '</b>';
  html += '<span>Период:</span><b>' + (dateFrom ? formatJournalDate(dateFrom) : '__.__.____') + ' — ' + (dateTo ? formatJournalDate(dateTo) : '__.__.____') + '</b>';
  html += '</div>';
  html += '<table class="cab-tbl"><thead><tr>';
  html += '<th style="width:22px">№</th><th style="width:54px">Дата приёмки</th><th style="width:76px">Тип системы</th><th>Марка кабеля</th><th style="width:42px">Сечение, мм²</th><th style="width:32px">Жил</th><th style="width:50px">Длина, м (с барабана)</th><th style="width:50px">№ барабана/бухты</th><th style="width:80px">Изготовитель</th><th style="width:80px">Сертификат №</th><th style="width:42px">R изоляции ДО, МΩ</th><th style="width:42px">R изоляции ПОСЛЕ, МΩ</th><th>Место прокладки</th><th style="width:80px">Способ прокладки</th><th style="width:54px">Дата монтажа</th><th style="width:90px">Ответств. ИТР</th>';
  html += '</tr></thead><tbody>';
  records.forEach((record, index) => {
    html += '<tr>';
    html += '<td class="num">' + (index + 1) + '</td>';
    html += '<td>' + formatJournalDate(record.receivedAt) + '</td>';
    html += '<td>' + (cableTypeOf(record) || '—') + '</td>';
    html += '<td>' + (record.cableBrand || '') + '</td>';
    html += '<td class="num">' + (record.crossSection || '—') + '</td>';
    html += '<td class="num">' + (record.coresCount || '—') + '</td>';
    html += '<td class="num">' + (record.lengthReceived || 0) + '</td>';
    html += '<td>' + (record.drumNumber || '—') + '</td>';
    html += '<td>' + (record.manufacturer || '—') + '</td>';
    html += '<td>' + (record.certificateNumber || '—') + '</td>';
    html += '<td class="num">' + (record.insulationBefore || '—') + '</td>';
    html += '<td class="num">' + (record.insulationAfter || '—') + '</td>';
    html += '<td>' + (record.installationLocation || '—') + '</td>';
    html += '<td>' + (record.installationMethod || '—') + '</td>';
    html += '<td>' + formatJournalDate(record.installedAt) + '</td>';
    html += '<td>' + (record.responsibleItr || '—') + '</td>';
    html += '</tr>';
  });
  html += '</tbody></table>';
  html += '<div class="cab-foot">Журнал ведётся для силовой электрики, СКС/интернет, слаботочных систем и пожарной сигнализации. Нормативную базу уточняют по типу системы: СП 76.13330, ПУЭ, ГОСТ Р 50571, СП 6.13130, СП 484.1311500, ГОСТ Р 53315 и проектная документация. Перед сдачей — обязательны проверки и измерения по применимому типу кабеля.</div>';
  html += '<div class="cab-sigs">';
  html += '<div><div class="cab-sig-label">Ответственный за кабельные/слаботочные работы (ИТР):</div><div class="cab-sig-line"></div><div class="cab-sig-sub">(должность, подпись, ФИО)</div></div>';
  html += '<div><div class="cab-sig-label">Представитель технического надзора заказчика:</div><div class="cab-sig-line"></div><div class="cab-sig-sub">(должность, подпись, ФИО)</div></div>';
  html += '</div>';
  return html;
};

export const buildInvoiceDocContent = (data = {}, context = {}) => {
  const { companyRequisites = {}, companyName = '' } = context;
  const {
    inv = {},
    invoiceRows = { items: [] },
    estimateControlRows = [],
    estimateControlIssues = [],
    vatCalc = { base: 0, vat: 0, total: 0 },
    qrUrl = '',
    isSupplyDelivery = false,
    compositeCount = 0,
  } = data;
  let html = '<h2 style="text-align:center">ПРИХОДНАЯ НАКЛАДНАЯ № ' + (inv.number || '') + '</h2>';
  html += '<p style="text-align:center">' + companyTitle(companyRequisites, companyName) + '</p>';
  if (qrUrl) html += '<div style="float:right;margin-bottom:10px"><img src="' + qrUrl + '" width="100" height="100"/><p style="font-size:10px;text-align:center">QR накладной</p></div>';
  html += '<table><tr><th>Дата</th><td>' + (inv.date || '') + '</td><th>Поставщик</th><td>' + (inv.supplierName || '') + '</td></tr>';
  html += '<tr><th>Принял</th><td>' + (inv.acceptedBy || '') + '</td><th>Место</th><td>' + (inv.location === 'Основной склад' ? 'Основной склад' : inv.project || '') + '</td></tr>';
  html += '<tr><th>НДС</th><td colspan="3">' + (inv.vat || '') + '</td></tr></table>';
  if (isSupplyDelivery) {
    html += '<p style="font-size:11px;color:#0f766e;margin:6px 0">Источник: поставка снабжения #' + (inv.supplyDeliveryId || inv.sourceId || '') + (inv.supplyRequestId ? ' по заявке #' + inv.supplyRequestId : '') + '. В материальном контроле это поступление учитывается в колонке «Поставки».</p>';
  }
  if (invoiceRows.reconstructed) {
    html += '<p style="font-size:11px;color:#666;margin:6px 0">Строки восстановлены из ' + invoiceRows.source + ', потому что в старой накладной был сохранён только итог.</p>';
  }
  if ((inv.location || '') !== 'Основной склад' && estimateControlRows.length > 0) {
    const color = estimateControlIssues.length ? '#b91c1c' : '#047857';
    html += '<p style="font-size:11px;color:' + color + ';margin:6px 0"><b>Сметный контроль:</b> ' + (estimateControlIssues.length ? 'есть замечания: ' + estimateControlIssues.length : 'все строки сопоставлены со сметой') + (compositeCount ? '; комплектация укрупненных работ: ' + compositeCount : '') + '</p>';
  }
  html += '<table><tr><th>N</th><th>Наименование товара</th><th>Категория</th><th>Кол-во</th><th>Ед.</th><th>Сумма</th><th>План</th><th>До</th><th>После</th><th>Сметный контроль</th></tr>';
  (invoiceRows.items || []).forEach((item, index) => {
    const rowSum = Number(item.total || 0) || Number(item.quantity || 0) * Number(item.price || 0);
    const ctrl = estimateControlRows[index] || {};
    const sourceText = ctrl.planSourceCount ? '; сметных строк: ' + ctrl.planSourceCount : '';
    const sectionsText = (ctrl.sectionsList || []).length ? '; разделы: ' + (ctrl.sectionsList || []).slice(0, 3).join(', ') : '';
    const ctrlText = ctrl.status
      ? ctrl.status + (ctrl.detail ? '; ' + ctrl.detail : '') + sourceText + sectionsText + (ctrl.incomingText ? '; накладная: ' + ctrl.incomingText : '') + (ctrl.shortageText && ctrl.shortageText !== '—' ? '; докупить: ' + ctrl.shortageText : '') + (ctrl.overText && ctrl.overText !== '—' ? '; сверх: ' + ctrl.overText : '') + (ctrl.priceOverText && ctrl.priceOverText !== '—' ? '; дороже плана: ' + ctrl.priceOverText : '')
      : '—';
    html += '<tr><td>' + (index + 1) + '</td><td>' + (item.name || '') + '</td><td>' + (item.category || '—') + '</td><td>' + (item.quantity || '') + '</td><td>' + (item.unit || '') + '</td><td>' + rowSum.toLocaleString() + '</td><td>' + (ctrl.planText || '—') + '</td><td>' + (ctrl.beforeText || '—') + '</td><td>' + (ctrl.afterText || '—') + '</td><td>' + ctrlText + '</td></tr>';
  });
  html += '<tr><td colspan="9">Итого без НДС:</td><td>' + vatCalc.base.toLocaleString() + ' руб.</td></tr>';
  const invoiceVatRate = String(inv.vat || '').match(/НДС\s*(\d+(?:[,.]\d+)?)%/i);
  if (invoiceVatRate) {
    html += '<tr><td colspan="9">НДС ' + invoiceVatRate[1].replace(',', '.') + '%:</td><td>' + vatCalc.vat.toLocaleString() + ' руб.</td></tr><tr><td colspan="9"><b>Итого с НДС:</b></td><td><b>' + vatCalc.total.toLocaleString() + ' руб.</b></td></tr>';
  }
  html += '</table><div class="signatures"><div class="sig"><div class="sig-line">Поставщик</div></div><div class="sig"><div class="sig-line">Принял: ' + (inv.acceptedBy || '') + '</div></div></div>';
  const grouped = estimateControlRows.filter((row) => (row.planDetails || []).length > 1);
  if (grouped.length > 0) {
    html += '<h3 style="font-size:13px;margin:18px 0 6px">Расшифровка сметных групп накладной</h3>';
    html += '<table><tr><th>Материал накладной</th><th>Материал сметы</th><th>Пакет/раздел</th><th>Работа</th><th>Кол-во по строке</th><th>Сумма</th></tr>';
    grouped.forEach((ctrl) => (ctrl.planDetails || []).forEach((detail, index) => {
      html += '<tr><td>' + (index === 0 ? ctrl.name || '' : '') + '</td><td>' + (index === 0 ? ctrl.canonicalName || '' : '') + '</td><td>' + ((detail.packageName || 'Основная') + ' / ' + (detail.sectionName || '')) + '</td><td>' + (detail.workName || '—') + '</td><td>' + Number(detail.qty || 0).toLocaleString('ru-RU') + ' ' + (detail.unit || ctrl.rowUnit || '') + '</td><td>' + Math.round(Number(detail.sum || 0)).toLocaleString('ru-RU') + ' ₽</td></tr>';
    }));
    html += '</table>';
  }
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

export const buildM8DocContent = (data = {}, context = {}) => {
  const { companyRequisites = {}, companyName = '' } = context;
  const {
    projectName = '',
    masterName = '',
    periodFrom = '',
    periodTo = '',
    rows = [],
  } = data;
  const orgName = companyTitle(companyRequisites, companyName);
  let html = '<style>.m8-tbl{border-collapse:collapse;width:100%;font-size:11px;margin:8px 0}.m8-tbl th,.m8-tbl td{border:1px solid #333;padding:5px 6px}.m8-tbl th{background:#f3f4f6}.m8-over{background:#fee2e2}.m8-ok{background:#dcfce7}</style>';
  html += '<h3 style="text-align:center;margin:6px 0">Унифицированная форма № М-8</h3>';
  html += '<h2 style="text-align:center;margin:0 0 6px">ЛИМИТНО-ЗАБОРНАЯ КАРТА</h2>';
  html += '<p style="text-align:center;font-size:11px;color:#444">Утверждена Постановлением Госкомстата России от 30.10.1997 № 71а</p>';
  html += '<p style="font-size:12px"><b>Организация:</b> ' + orgName + '</p>';
  html += '<p style="font-size:12px"><b>Объект:</b> ' + projectName + (masterName ? ' · <b>Получатель:</b> ' + masterName : '') + '</p>';
  html += '<p style="font-size:12px"><b>Период:</b> ' + (periodFrom || '__.__.____') + ' — ' + (periodTo || '__.__.____') + '</p>';
  if (rows.length === 0) {
    html += '<p style="text-align:center;color:#888;font-size:11px;padding:14px">Нет данных за период</p>';
  } else {
    html += '<table class="m8-tbl"><tr><th>№</th><th>Наименование материала</th><th>Ед.</th><th>Лимит (по смете)</th><th>Отпущено за период</th><th>Остаток лимита</th></tr>';
    rows.forEach((row, index) => {
      const rem = row.limit - row.issued;
      const cls = row.limit > 0 && row.issued > row.limit ? 'm8-over' : rem >= 0 ? 'm8-ok' : '';
      html += '<tr class="' + cls + '"><td>' + (index + 1) + '</td><td>' + row.name + '</td><td>' + row.unit + '</td><td>' + row.limit.toLocaleString('ru-RU') + '</td><td>' + row.issued.toLocaleString('ru-RU') + '</td><td>' + rem.toLocaleString('ru-RU') + '</td></tr>';
    });
    html += '</table>';
  }
  html += '<div style="margin-top:24px;display:grid;grid-template-columns:1fr 1fr;gap:20px">';
  html += '<div><div style="font-size:11px;font-weight:600;margin-bottom:30px">Установил лимит (главный инженер):</div><div style="border-bottom:1px solid #333;min-height:18px"></div></div>';
  html += '<div><div style="font-size:11px;font-weight:600;margin-bottom:30px">Получатель:</div><div style="border-bottom:1px solid #333;min-height:18px">' + (masterName || '') + '</div></div>';
  html += '</div>';
  html += '<p style="margin-top:18px;font-size:10px;color:#666;text-align:center">Превышение лимита (красные строки) требует утверждения у главного инженера и письменного обоснования.</p>';
  return html;
};

export const buildMaterialRequirementDocContent = (data = {}, context = {}) => {
  const { companyRequisites = {}, companyName = '' } = context;
  const {
    projectName = '',
    activeEstimates = [],
    rows = [],
    normRows = [],
    normCtrl = { overRows: [], withoutNormRows: [] },
  } = data;
  const scalarText = (value) => {
    const number = Number(value || 0);
    return Number.isFinite(number)
      ? number.toLocaleString('ru-RU', { maximumFractionDigits: 6 })
      : '0';
  };
  const sourceMeasureText = (qty, unit) => (scalarText(qty) + ' ' + (unit || '')).trim();
  const normFormulaText = (work = {}) => {
    const formula = work.formula || {};
    const workUnit = formula.workUnit || work.unit || '';
    const materialUnit = formula.materialUnit || work.requiredUnit || '';
    const parts = [sourceMeasureText(formula.workQty ?? work.quantity ?? 0, workUnit)];
    if (Number(formula.qtyPerUnit || 0) > 0) {
      parts.push('x ' + scalarText(formula.qtyPerUnit) + ' ' + materialUnit + '/' + (workUnit || 'ед.'));
    }
    if (Number(formula.thicknessBaseMm || 0) > 0) {
      parts.push('x ' + scalarText(formula.thicknessMm || formula.thicknessBaseMm) + '/' + scalarText(formula.thicknessBaseMm));
    }
    return parts.join(' ') + ' = ' + sourceMeasureText(formula.requiredQty ?? work.requiredQty ?? 0, formula.requiredUnit || work.requiredUnit || '');
  };
  const orgName = companyTitle(companyRequisites, companyName);
  let html = '<style>.mr-tbl{border-collapse:collapse;width:100%;font-size:10.5px;margin:8px 0}.mr-tbl th,.mr-tbl td{border:1px solid #333;padding:5px 6px}.mr-tbl th{background:#f3f4f6}.mr-need{background:#fef3c7;font-weight:700}.mr-over{background:#dbeafe}.mr-out{background:#fee2e2}.mr-ok{background:#dcfce7}.mr-muted{font-size:9px;color:#666;font-weight:400}</style>';
  html += '<h2 style="text-align:center;margin:6px 0">ВЕДОМОСТЬ ПОТРЕБНОСТИ МАТЕРИАЛОВ</h2>';
  html += '<p style="text-align:center;font-size:11px;color:#444">по смете объекта и нормам расхода (смета / норма / контроль / заявки / в пути / накладные / поставки / перемещения / выдано / списано / остаток)</p>';
  html += '<p style="font-size:12px"><b>Объект:</b> ' + projectName + ' · <b>Подрядчик:</b> ' + orgName + '</p>';
  if (activeEstimates.length === 0) html += '<p style="color:#dc2626;font-size:12px;text-align:center;padding:14px">⚠️ Смета не загружена — план посчитать невозможно</p>';
  if (rows.length === 0) {
    html += '<p style="text-align:center;color:#888;font-size:11px;padding:14px">Материалов в смете нет</p>';
  } else {
    html += '<table class="mr-tbl"><tr><th>№</th><th>Материал</th><th>Работа-основание</th><th>Раздел</th><th>Ед.</th><th>Смета</th><th>Норма</th><th>Контроль</th><th>В заявках</th><th>В пути</th><th>Накладные</th><th>Поставки</th><th>Перемещено</th><th>Всего получено</th><th>Выдано</th><th>Списано</th><th>У мастеров</th><th>Остаток склада</th><th>Расчётный остаток</th><th>Расхождение</th><th>Докупить</th><th>Статус</th></tr>';
    rows.forEach((row, index) => {
      const invalid = (row.invalidPlanCount || 0) > 0;
      const review = !!row.reviewRequired || invalid || !!row.unitMismatch;
      const reviewReason = (row.reviewReasons || []).join('; ') || (invalid ? 'Некорректные строки сметы: ' + row.invalidPlanCount : 'Требуется проверка');
      const cls = review ? 'mr-need' : row.stockMismatch ? 'mr-out' : row.issued > 0 && row.usedWithoutIssue > 0 ? 'mr-out' : row.usedOverControlQty > 0 ? 'mr-out' : row.isOutsideEstimate ? 'mr-out' : row.normOverEstimateQty > 0 ? 'mr-need' : row.toBuy > 0 ? 'mr-need' : row.over > 0 ? 'mr-over' : 'mr-ok';
      const status = review ? 'проверить: ' + reviewReason : row.stockMismatch ? 'расхождение склада ' + row.stockDiff.toLocaleString('ru-RU') : row.issued > 0 && row.usedWithoutIssue > 0 ? 'списано сверх выдачи ' + row.usedWithoutIssue.toLocaleString('ru-RU') : row.usedOverControlQty > 0 ? 'расход сверх контроля ' + row.usedOverControlQty.toLocaleString('ru-RU') : row.isOutsideEstimate ? 'вне сметы ' + row.coveredWithPipeline.toLocaleString('ru-RU') : row.normOverEstimateQty > 0 ? 'норма выше сметы +' + row.normOverEstimateQty.toLocaleString('ru-RU') : row.toBuy > 0 ? 'докупить ' + row.toBuy.toLocaleString('ru-RU') : row.shortage > 0 ? 'закрывается заявками/поставками' : row.masterBalance > 0 ? 'у мастеров ' + row.masterBalance.toLocaleString('ru-RU') : row.over > 0 ? 'сверх ' + row.over.toLocaleString('ru-RU') : 'закрыто';
      const workCell = (row.workRefs || []).slice(0, 3).join('; ');
      const sourceCount = (row.planDetails || []).length;
      html += '<tr class="' + cls + '"><td>' + (index + 1) + '</td><td>' + row.name + (row.unitMismatch ? ' ⚠ ед.изм.' : '') + (sourceCount ? '<br><span class="mr-muted">строк сметы: ' + sourceCount + '</span>' : '') + (row.normSourceCount ? '<br><span class="mr-muted">норм: ' + row.normSourceCount + '</span>' : '') + (invalid ? '<br><span class="mr-muted">невалидных строк: ' + row.invalidPlanCount + '</span>' : '') + '</td><td>' + workCell + '</td><td>' + (row.sections || []).join(', ') + '</td><td>' + row.unit + '</td><td>' + row.planQty.toLocaleString('ru-RU') + '</td><td>' + Number(row.normPlanQty || 0).toLocaleString('ru-RU') + '</td><td>' + Number(row.controlPlanQty || 0).toLocaleString('ru-RU') + '</td><td>' + row.requested.toLocaleString('ru-RU') + '</td><td>' + row.inTransit.toLocaleString('ru-RU') + '</td><td>' + row.invoiceReceived.toLocaleString('ru-RU') + '</td><td>' + row.supplyReceived.toLocaleString('ru-RU') + '</td><td>' + row.movedNet.toLocaleString('ru-RU') + '</td><td>' + row.supplied.toLocaleString('ru-RU') + '</td><td>' + row.issued.toLocaleString('ru-RU') + '</td><td>' + row.used.toLocaleString('ru-RU') + '</td><td>' + row.masterBalance.toLocaleString('ru-RU') + '</td><td>' + row.stock.toLocaleString('ru-RU') + '</td><td>' + row.expectedStock.toLocaleString('ru-RU') + '</td><td>' + row.stockDiff.toLocaleString('ru-RU') + '</td><td>' + row.toBuy.toLocaleString('ru-RU') + '</td><td>' + status + '</td></tr>';
    });
    const totalSum = rows.reduce((sum, row) => sum + (row.planSum || 0), 0);
    html += '<tr style="background:#f3f4f6"><td colspan="5"><b>ИТОГО плановая стоимость материалов:</b></td><td colspan="17"><b>' + Math.round(totalSum).toLocaleString('ru-RU') + ' ₽</b></td></tr>';
    html += '</table>';

    const groupedRows = rows.filter((row) => (row.planDetails || []).length > 0);
    if (groupedRows.length > 0) {
      html += '<h3 style="font-size:13px;margin:18px 0 6px">Расшифровка строк сметы</h3>';
      html += '<p style="font-size:10px;color:#666;margin:0 0 6px">Для каждой строки показаны исходное количество из сметы, преобразование единицы и количество, вошедшее в закупочный план.</p>';
      html += '<table class="mr-tbl"><tr><th>Материал</th><th>Смета</th><th>Пакет</th><th>Раздел</th><th>Работа-основание</th><th>Строка материала</th><th>Исходное количество</th><th>В плане</th><th>Решение</th><th>Сумма</th></tr>';
      groupedRows.forEach((row) => (row.planDetails || []).forEach((detail, index) => {
        const sourceQty = detail.rawQty ?? detail.sourceQty ?? detail.qty ?? 0;
        const sourceUnit = detail.rawUnit || detail.sourceUnit || detail.unit || row.unit || '';
        const normalized = sourceMeasureText(detail.normalizedQty ?? detail.qty ?? 0, detail.normalizedUnit || detail.unit || row.unit || '');
        const conversion = detail.conversionApplied ? ' (преобразовано' + (Number(detail.normalizationFactor || 1) !== 1 ? ' x ' + scalarText(detail.normalizationFactor) : '') + ')' : '';
        html += '<tr><td>' + (index === 0 ? '<b>' + row.name + '</b><br><span class="mr-muted">итого ' + row.planQty.toLocaleString('ru-RU') + ' ' + row.unit + '</span>' : '') + '</td><td>' + (detail.estimateName || '') + '</td><td>' + (detail.packageName || 'Основная') + '</td><td>' + (detail.sectionName || '') + '</td><td>' + (detail.workName || '') + '</td><td>' + (detail.materialName || row.name) + '</td><td>' + sourceMeasureText(sourceQty, sourceUnit) + '</td><td>' + normalized + conversion + '</td><td>' + (row.reviewRequired ? 'Проверить' : 'В закупочном плане') + '</td><td>' + Math.round(Number(detail.sum || 0)).toLocaleString('ru-RU') + ' ₽</td></tr>';
      }));
      html += '</table>';
    }

    const reviewRows = rows.filter((row) => row.reviewRequired || (row.invalidPlanDetails || []).length > 0);
    if (reviewRows.length > 0) {
      html += '<h3 style="font-size:13px;margin:18px 0 6px">Строки сметы, исключённые из автоматической закупки</h3>';
      html += '<p style="font-size:10px;color:#666;margin:0 0 6px">Эти строки требуют проверки сметчиком: система не создаёт по ним заявки, чтобы не закупить ошибочное количество.</p>';
      html += '<table class="mr-tbl"><tr><th>Материал</th><th>Пакет</th><th>Раздел</th><th>Работа-основание</th><th>Количество</th><th>Сумма</th><th>Причина</th></tr>';
      reviewRows.forEach((row) => {
        const details = (row.invalidPlanDetails || []).length > 0
          ? row.invalidPlanDetails
          : (row.planDetails || []).length > 0 ? row.planDetails : [{}];
        details.forEach((detail) => {
          const reason = detail.reason || (row.reviewReasons || []).join('; ') || 'Проверить строку';
          html += '<tr class="mr-need"><td>' + row.name + '</td><td>' + (detail.packageName || 'Основная') + '</td><td>' + (detail.sectionName || '') + '</td><td>' + (detail.workName || '') + '</td><td>' + sourceMeasureText(detail.normalizedQty ?? detail.qty ?? row.planQty ?? 0, detail.normalizedUnit || detail.unit || row.unit || '') + '</td><td>' + Math.round(Number(detail.sum || 0)).toLocaleString('ru-RU') + ' ₽</td><td>' + reason + '</td></tr>';
        });
      });
      html += '</table>';
    }
  }

  if (normRows.length > 0) {
    html += '<h3 style="font-size:13px;margin:18px 0 6px">Нормативная потребность по работам</h3>';
    html += '<p style="font-size:10px;color:#666;margin:0 0 6px">Материалы рассчитаны из строк типа «Работа» по типовым нормам. Они участвуют в контрольной потребности и подсвечивают нехватку/перерасход, но не меняют активную смету заказчика.</p>';
    html += '<table class="mr-tbl"><tr><th>№</th><th>Материал по норме</th><th>Ед.</th><th>Потребность</th><th>Работы-источники</th><th>Норма</th></tr>';
    normRows.forEach((row, index) => {
      html += '<tr><td>' + (index + 1) + '</td><td>' + row.name + '</td><td>' + row.unit + '</td><td>' + row.planQty.toLocaleString('ru-RU') + '</td><td>' + row.works.slice(0, 4).map((work) => work.name).join('; ') + (row.works.length > 4 ? ' …' : '') + '</td><td>' + row.normSources.join('; ') + '</td></tr>';
    });
    html += '</table>';
    const normTraceRows = normRows.flatMap((row) => (row.works || []).map((work) => ({ row, work })));
    if (normTraceRows.length > 0) {
      html += '<h3 style="font-size:13px;margin:18px 0 6px">Расшифровка нормативного расчёта</h3>';
      html += '<p style="font-size:10px;color:#666;margin:0 0 6px">Нормативные строки используются как подсказка для контроля и не входят в автоматический закупочный план.</p>';
      html += '<table class="mr-tbl"><tr><th>Смета</th><th>Пакет</th><th>Раздел</th><th>Работа</th><th>Материал</th><th>Правило</th><th>Формула</th><th>Решение</th></tr>';
      normTraceRows.forEach(({ row, work }) => {
        html += '<tr><td>' + (work.estimateName || '') + '</td><td>' + (work.packageName || 'Основная') + '</td><td>' + (work.section || '') + '</td><td>' + (work.name || '') + '</td><td>' + row.name + '</td><td>' + (work.ruleId || '') + ' · ' + (work.ruleScope || 'base') + '</td><td>' + normFormulaText(work) + '</td><td>Нормативная подсказка, не закупать автоматически</td></tr>';
      });
      html += '</table>';
    }
  }
  if (normCtrl.overRows.length > 0 || normCtrl.withoutNormRows.length > 0) {
    html += '<h3 style="font-size:13px;margin:18px 0 6px">Контроль списания по нормам</h3>';
    html += '<p style="font-size:10px;color:#666;margin:0 0 6px">Перерасход требует проверки прорабом/сметчиком. Строки без нормы означают, что материал списали, но система не нашла правило расхода.</p>';
    html += '<table class="mr-tbl"><tr><th>№</th><th>Материал</th><th>Ед.</th><th>Факт списания</th><th>Норма</th><th>Отклонение</th><th>Работы</th><th>Статус</th></tr>';
    [...normCtrl.overRows, ...normCtrl.withoutNormRows.filter((row) => !normCtrl.overRows.some((over) => over.key === row.key))].forEach((row, index) => {
      const over = row.overQty > 0;
      const cls = over ? 'mr-out' : 'mr-need';
      const deviation = over ? ('+' + row.overQty.toLocaleString('ru-RU')) : ('без нормы ' + row.withoutNormQty.toLocaleString('ru-RU'));
      html += '<tr class="' + cls + '"><td>' + (index + 1) + '</td><td>' + row.name + '</td><td>' + row.unit + '</td><td>' + row.qty.toLocaleString('ru-RU') + '</td><td>' + (row.normQty > 0 ? row.normQty.toLocaleString('ru-RU') : '—') + '</td><td>' + deviation + '</td><td>' + row.works.slice(0, 4).map((work) => work.workName).join('; ') + (row.works.length > 4 ? ' …' : '') + '</td><td>' + (over ? 'проверить перерасход' : 'завести/уточнить норму') + '</td></tr>';
    });
    html += '</table>';
  }
  html += '<div style="margin-top:24px;display:grid;grid-template-columns:1fr 1fr;gap:20px">';
  html += '<div><div style="font-size:11px;font-weight:600;margin-bottom:30px">Сметчик / производитель работ:</div><div style="border-bottom:1px solid #333;min-height:18px"></div></div>';
  html += '<div><div style="font-size:11px;font-weight:600;margin-bottom:30px">Снабженец:</div><div style="border-bottom:1px solid #333;min-height:18px"></div></div>';
  html += '</div>';
  html += '<p style="margin-top:16px;font-size:10px;color:#666;text-align:center">Жёлтые строки — нужно докупить с учётом заявок и поставок в пути, синие — поставлено сверх сметы, красные — материал вне сметы. При разных единицах измерения строка помечается ⚠.</p>';
  return html;
};

export const buildM29DocContent = (data = {}, context = {}) => {
  const { companyRequisites = {}, companyName = '' } = context;
  const {
    projectName = '',
    periodFrom = '',
    periodTo = '',
    rows = [],
  } = data;
  const orgName = companyTitle(companyRequisites, companyName);
  let html = '<style>.m29-tbl{border-collapse:collapse;width:100%;font-size:11px;margin-top:10px}.m29-tbl th,.m29-tbl td{border:1px solid #333;padding:4px 6px}.m29-tbl th{background:#f3f4f6}.m29-over{color:#dc2626;font-weight:700}.m29-ok{color:#059669}</style>';
  html += '<h3 style="text-align:center;margin:6px 0">Унифицированная форма № М-29</h3>';
  html += '<h2 style="text-align:center;margin:0 0 4px">ОТЧЁТ О РАСХОДЕ ОСНОВНЫХ МАТЕРИАЛОВ</h2>';
  html += '<p style="text-align:center;font-size:11px;color:#444">в сопоставлении с производственными нормами (план/факт)</p>';
  html += '<p style="font-size:11px"><b>Объект:</b> ' + projectName + ' · <b>Подрядчик:</b> ' + orgName + ' · <b>Период:</b> ' + (periodFrom || '__.__.____') + ' — ' + (periodTo || '__.__.____') + '</p>';
  if (rows.length === 0) {
    html += '<p style="text-align:center;color:#888;padding:20px">Нет данных — не загружена смета или нет движений по материалам</p>';
  } else {
    html += '<table class="m29-tbl"><tr><th>№</th><th>Наименование материала</th><th>Ед.</th><th>План (смета)</th><th>Выдано мастерам</th><th>Факт (списано по ЖПР)</th><th>Отклонение</th><th>Статус</th></tr>';
    rows.forEach((row, index) => {
      const delta = row.fact - row.plan;
      const over = row.plan > 0 && delta > row.plan * 0.05;
      html += '<tr><td>' + (index + 1) + '</td><td>' + row.name + '</td><td>' + row.unit + '</td><td>' + row.plan.toLocaleString('ru-RU') + '</td><td>' + row.issued.toLocaleString('ru-RU') + '</td><td>' + row.fact.toLocaleString('ru-RU') + '</td><td class="' + (over ? 'm29-over' : 'm29-ok') + '">' + (delta > 0 ? '+' : '') + delta.toLocaleString('ru-RU') + '</td><td>' + (over ? '⚠️ перерасход >5%' : delta < 0 ? '✅ экономия' : '≈ в норме') + '</td></tr>';
    });
    html += '</table>';
  }
  html += '<div style="margin-top:24px;display:grid;grid-template-columns:1fr 1fr;gap:30px">';
  html += '<div><div style="font-size:11px;font-weight:600;margin-bottom:30px">Производитель работ:</div><div style="border-bottom:1px solid #333;min-height:18px"></div><div style="font-size:9px;color:#555;margin-top:2px">(должность, ФИО, подпись)</div></div>';
  html += '<div><div style="font-size:11px;font-weight:600;margin-bottom:30px">Главный инженер / технадзор:</div><div style="border-bottom:1px solid #333;min-height:18px"></div><div style="font-size:9px;color:#555;margin-top:2px">(должность, ФИО, подпись)</div></div>';
  html += '</div>';
  html += '<p style="margin-top:18px;font-size:10px;color:#666;text-align:center">Форма утверждена приказом ЦСУ СССР № 613, действует. Перерасход выше 5% от нормы требует объяснений и согласования с заказчиком.</p>';
  return html;
};

export {
  buildKS14DocContent,
  buildIGDDocContent,
  buildM2DocContent,
  buildAOSKDocContent,
  buildKS11DocContent,
  buildSpecJournalDocContent,
  buildSupplementaryAgreementDocContent,
  buildExecPackageDocContent,
  buildVATBookDocContent,
  buildSupervisorMonthlyReportDocContent,
  buildInventoryDocContent,
  buildPrescriptionDocContent,
  buildTBContentDoc,
  buildPricelistDocContent,
  buildPositionInstructionDocContent,
  buildPassportDocContent,
} from './print/regulatoryDocumentBuilders';
