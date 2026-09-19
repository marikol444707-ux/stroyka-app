import React, { useMemo, useState } from 'react';
import { registryRows, filterRegistryRows, registryStatusLabels, registryDate, downloadRegistryCsv } from './supplierRegistryQuery';
import './supplierWorkspace.css';

const PAGE_SIZE=20;
export default function SupplierRequestRegistry({requests=[], offers=[], onOpen, selectedId, C, busy=false}) {
  const [filters,setFilters]=useState({query:'',company:'',status:''});
  const [page,setPage]=useState(1);
  const rows=useMemo(()=>registryRows(requests,offers),[requests,offers]);
  const filtered=useMemo(()=>filterRegistryRows(rows,filters),[rows,filters]);
  const companies=[...new Map(rows.filter(row=>row.company).map(row=>[row.company,row.companyName]))];
  const statuses=[...new Set(rows.flatMap(row=>row.statuses))];
  const pages=Math.max(1,Math.ceil(filtered.length/PAGE_SIZE));
  const currentPage=Math.min(page,pages);
  const visible=filtered.slice((currentPage-1)*PAGE_SIZE,currentPage*PAGE_SIZE);
  const change=(key,value)=>{setFilters(previous=>({...previous,[key]:value}));setPage(1);};
  return <section className="supplier-registry" aria-label="Реестр заявок" style={{color:C.text,background:C.bgCard,borderColor:C.border}}>
    <div className="supplier-registry-heading"><h2>Входящие заявки</h2><span>{rows.length}</span></div>
    <div className="supplier-registry-filters">
      <label>Поиск<input type="search" value={filters.query} placeholder="Номер, материал или объект" onChange={event=>change('query',event.target.value)}/></label>
      <label>Заказчик<select value={filters.company} onChange={event=>change('company',event.target.value)}><option value="">Все заказчики</option>{filters.company && !companies.some(([id])=>id===filters.company) && <option value={filters.company}>Заказчик больше не доступен</option>}{companies.map(([id,name])=><option key={id} value={id}>{name}</option>)}</select></label>
      <label>Состояние КП<select value={filters.status} onChange={event=>change('status',event.target.value)}><option value="">Все состояния</option>{filters.status && !statuses.includes(filters.status) && <option value={filters.status}>{registryStatusLabels[filters.status] || filters.status}</option>}{statuses.map(status=><option key={status} value={status}>{registryStatusLabels[status] || status}</option>)}</select></label>
      <button type="button" onClick={()=>{setFilters({query:'',company:'',status:''});setPage(1);}}>Сбросить фильтры</button>
      <button type="button" disabled={!filtered.length || busy} onClick={()=>downloadRegistryCsv(filtered)}>Выгрузить CSV</button>
    </div>
    <p className="supplier-registry-count" role="status">Найдено: {filtered.length} из {rows.length}</p>
    <table><thead><tr><th>Заявка / заказчик</th><th>Материалы / объект</th><th>Запрос КП получен</th><th>Состояние КП</th><th><span className="supplier-sr-only">Открыть</span></th></tr></thead>
      <tbody>{visible.map(row=><tr key={row.id} aria-selected={String(selectedId)===String(row.id)}>
        <td data-label="Заявка / заказчик"><strong>№{row.id}</strong><div>{row.companyName}</div></td>
        <td data-label="Материалы / объект"><strong>{row.material}</strong><div>{row.project}</div></td>
        <td data-label="Запрос КП получен">{registryDate(row.requestedAt)}</td>
        <td data-label="Состояние КП">{row.statusLabel}</td>
        <td><button type="button" disabled={busy} onClick={()=>onOpen(row.id)} aria-label={'Открыть заявку №'+row.id}>Открыть →</button></td>
      </tr>)}</tbody>
    </table>
    {!filtered.length && <p className="supplier-registry-empty">{rows.length ? 'По выбранным условиям заявок нет.' : 'Запросов нет. Здесь появятся заявки, направленные вашей компании.'}</p>}
    <nav className="supplier-registry-pagination" aria-label="Страницы заявок">
      <button type="button" disabled={currentPage===1} onClick={()=>setPage(currentPage-1)} aria-label="Предыдущая страница">← Назад</button>
      <span>Страница {currentPage} из {pages}</span>
      <button type="button" disabled={currentPage===pages} onClick={()=>setPage(currentPage+1)} aria-label="Следующая страница">Далее →</button>
    </nav>
  </section>;
}
