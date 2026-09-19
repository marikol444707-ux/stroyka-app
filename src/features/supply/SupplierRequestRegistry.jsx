import React from 'react';
import './supplierWorkspace.css';

const labels = {'Ожидает ответа':'Новая', 'Получено':'Ждём решения заказчика', 'Утверждено':'КП выбрано', 'Отклонено':'Отклонено', 'Отозвано':'Отозвано'};
function dateLabel(value) {
  if (!value) return 'Не указано';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 'Не указано' : date.toLocaleString('ru-RU');
}
export default function SupplierRequestRegistry({requests=[], offers=[], onOpen, selectedId, C, busy=false}) {
  const grouped = new Map();
  offers.forEach(offer => {
    const id = String(offer.requestId);
    if (!grouped.has(id)) grouped.set(id, []);
    grouped.get(id).push(offer);
  });
  const rows = requests.filter(request => grouped.has(String(request.id)));
  return <section className="supplier-registry" aria-label="Реестр заявок" style={{color:C.text,background:C.bgCard,borderColor:C.border}}>
    <div className="supplier-registry-heading"><h2>Входящие заявки</h2><span>{rows.length}</span></div>
    <table><thead><tr><th>Заявка / заказчик</th><th>Материалы / объект</th><th>Запрос КП получен</th><th>Состояние КП</th><th><span className="supplier-sr-only">Открыть</span></th></tr></thead>
      <tbody>{rows.map(request => {
        const quotes = grouped.get(String(request.id));
        const dates = quotes.map(q => q.requestedAt).filter(value => value && !Number.isNaN(new Date(value).getTime()));
        dates.sort((a,b)=>new Date(a)-new Date(b));
        let items = request.itemsJson || request.items || [];
        if (typeof items === 'string') { try { items = JSON.parse(items); } catch { items = []; } }
        if (!Array.isArray(items)) items = [];
        const material = items.map(item=>item?.materialName || item?.name).filter(Boolean).join(', ') || request.materialName || 'Материалы не указаны';
        const statuses = [...new Set(quotes.map(q=>labels[q.status] || q.status || 'Статус неизвестен'))].join(' · ');
        return <tr key={request.id} aria-selected={String(selectedId)===String(request.id)}>
          <td data-label="Заявка / заказчик"><strong>№{request.id}</strong><div>{request.companyName || (request.companyId ? 'Компания №'+request.companyId : 'Заказчик не указан')}</div></td>
          <td data-label="Материалы / объект"><strong>{material}</strong><div>{request.project || 'Объект не указан'}</div></td>
          <td data-label="Запрос КП получен">{dateLabel(dates[0])}</td>
          <td data-label="Состояние КП">{statuses}</td>
          <td><button type="button" disabled={busy} onClick={()=>onOpen(request.id)} aria-label={'Открыть заявку №'+request.id}>Открыть →</button></td>
        </tr>;
      })}</tbody>
    </table>
    {!rows.length && <p className="supplier-registry-empty">Запросов нет. Здесь появятся заявки, направленные вашей компании.</p>}
  </section>;
}
