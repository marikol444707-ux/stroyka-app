export const registryStatusLabels = {'Ожидает ответа':'Новая', 'Получено':'Ждём решения заказчика', 'Утверждено':'КП выбрано', 'Отклонено':'Отклонено', 'Отозвано':'Отозвано'};
export const registryDate = value => value ? new Date(value).toLocaleString('ru-RU') : 'Не указано';
const normalize = value => String(value || '').normalize('NFKC').toLocaleLowerCase('ru-RU').replace(/ё/g,'е').trim();

// Both inputs are the complete, authorized inbox snapshot, not one display page.
export function registryRows(requests, offers) {
  const grouped = new Map();
  offers.forEach(offer => {
    const id=String(offer.requestId);
    if (!grouped.has(id)) grouped.set(id,[]);
    grouped.get(id).push(offer);
  });
  return requests.filter(request=>grouped.has(String(request.id))).map(request=>{
    const quotes=grouped.get(String(request.id));
    const dates=quotes.map(q=>q.requestedAt).filter(value=>value && !Number.isNaN(new Date(value).getTime())).sort((a,b)=>new Date(a)-new Date(b));
    let items=request.itemsJson || request.items || [];
    if (typeof items==='string') { try { items=JSON.parse(items); } catch { items=[]; } }
    if (!Array.isArray(items)) items=[];
    const material=items.map(item=>item?.materialName || item?.name).filter(Boolean).join(', ') || request.materialName || 'Материалы не указаны';
    const statuses=[...new Set(quotes.map(q=>q.status || 'Статус неизвестен'))];
    return {id:request.id, company:String(request.companyId || ''), companyName:request.companyName || (request.companyId ? 'Компания №'+request.companyId : 'Заказчик не указан'), material, project:request.project || 'Объект не указан', requestedAt:dates[0], statuses, statusLabel:statuses.map(status=>registryStatusLabels[status] || status).join(' · ')};
  });
}
export function filterRegistryRows(rows,{query='',company='',status=''}={}) {
  const term=normalize(String(query).trim().replace(/^№\s*/,''));
  return rows.filter(row=>(!company || row.company===company) && (!status || row.statuses.includes(status)) && (!term || normalize(`${row.id} ${row.material} ${row.project}`).includes(term)));
}
function csvCell(value) {
  const text=String(value ?? '');
  // Quote every field and neutralize formula prefixes even after whitespace/control chars.
  // eslint-disable-next-line no-control-regex -- CSV formula checks must include leading control characters.
  const safe=/^[\s\u0000-\u001f]*[=+\-@＝＋－＠]/u.test(text) || /^[\t\r\n]/.test(text) ? "'"+text : text;
  return '"'+safe.replace(/"/g,'""')+'"';
}
export function registryCsv(rows) {
  const values=[['Заявка','Заказчик','Материалы','Объект','Запрос КП получен','Состояние КП'], ...rows.map(row=>[row.id,row.companyName,row.material,row.project,registryDate(row.requestedAt),row.statusLabel])];
  return '\uFEFF'+values.map(row=>row.map(csvCell).join(';')).join('\r\n')+'\r\n';
}
export function downloadRegistryCsv(rows) {
  const url=URL.createObjectURL(new Blob([registryCsv(rows)],{type:'text/csv;charset=utf-8'}));
  const link=document.createElement('a');
  link.href=url; link.download='supplier-requests.csv'; document.body.appendChild(link);
  link.click(); link.remove(); setTimeout(()=>URL.revokeObjectURL(url),1000);
}
