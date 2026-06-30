import { POSITION_INSTRUCTIONS, TB_INSTRUCTIONS } from '../constants/documentTemplates';
import { EXPENSE_CATEGORIES } from '../constants/catalogs';

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
