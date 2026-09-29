const escape = value => String(value ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));
export const conditions = { as_recorded: 'Соответствует учёту', missing: 'Не найден', damaged: 'Повреждён', found: 'Найден' };
export const actions = { create: 'Начало сверки', save: 'Сохранён пересчёт', submit: 'Передано на проверку', return: 'Возвращено на пересчёт', cancel: 'Отменено', approve: 'Утверждено' };

export function buildInventoryReport(data) {
  const { inventory, rows, history } = data;
  return `<h2>Ведомость инвентаризации №${escape(inventory.id)}</h2>
    <p>${escape(inventory.project)} · ${escape(inventory.date)}<br>Статус: ${escape(inventory.status)}<br>Создал: ${escape(inventory.createdBy || inventory.created_by)}<br>${escape(inventory.notes)}</p>
    <table border="1" cellpadding="6" style="width:100%;border-collapse:collapse"><thead><tr><th>Позиция</th><th>По учёту</th><th>Факт</th><th>Расхождение / причина</th></tr></thead><tbody>
    ${rows.map(row => `<tr><td>${escape(row.name)}<br>${escape(row.inventoryNumber || row.package)}</td><td>${escape(row.kind === 'tool' ? `${row.status} · ${row.holderName || ''}` : `${row.expected ?? '—'} ${row.unit || ''}`)}</td><td>${escape(row.kind === 'tool' ? conditions[row.condition] || 'Не проверено' : row.actual ?? 'Не пересчитано')}</td><td>${escape(row.difference ?? '')}<br>${escape(row.reason || row.notes)}</td></tr>`).join('')}
    </tbody></table><h3>История решений</h3>
    ${history.map(event => `<p>${escape(actions[event.action])} · ${escape(event.actorName)} · ${escape(event.createdAt)}<br>${escape(event.reason)}</p>`).join('')}
    <p>Расхождения по инструменту требуют отдельной операции в истории ответственности. Денежное возмещение этой ведомостью не назначается.</p>
    <p style="margin-top:36px">Проверил ____________________ &nbsp; Утвердил ____________________</p>`;
}
