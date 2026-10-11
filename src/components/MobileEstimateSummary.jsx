import React, {useMemo} from 'react';

export function parseEstimateSummary(content) {
  const doc = new DOMParser().parseFromString(content, 'text/html');
  const table = doc.querySelector('.eps-table');
  if (!table) return null;
  const totals = [...doc.querySelectorAll('.eps-card')].map(card => ({label:card.querySelector('span')?.textContent, value:card.querySelector('b')?.textContent}));
  const groups = new Map();
  [...table.querySelectorAll('tr')].forEach(row => {
    const cells = [...row.querySelectorAll('td')].map(cell => cell.textContent);
    if (cells.length !== 10) return;
    const [, workPackage, section, name, reason, beforeQty, afterQty, beforeSum, afterSum, difference] = cells;
    const key = JSON.stringify([workPackage, section]);
    if (!groups.has(key)) groups.set(key, {key, workPackage, section, rows:[], difference:0});
    const group = groups.get(key);
    const amount = Number(difference.replace(/[^\d,+−-]/g, '').replace('−','-').replace(',','.'));
    group.difference += Number.isFinite(amount) ? amount : 0;
    group.rows.push({name,reason,beforeQty,afterQty,beforeSum,afterSum,difference,
      beforePrice:row.dataset.basePrice,afterPrice:row.dataset.nextPrice});
  });
  return {totals,groups:[...groups.values()],project:doc.querySelector('.eps-sub')?.textContent?.split(' · ')[0],balance:doc.querySelector('.eps-balance')?.textContent};
}

export default function MobileEstimateSummary({content}) {
  const data = useMemo(()=>parseEstimateSummary(content),[content]);
  if (!data) return null;
  return <div className="mobile-estimate-summary">
    <p>{data.project}</p>
    <div className="mobile-estimate-total"><span>Изменение суммы</span><strong>{data.totals[3]?.value}</strong>
      <small>{data.totals[2]?.value} позиций · {data.totals[1]?.value} пакетов с изменениями</small></div>
    <details><summary>Все итоги</summary><dl>{data.totals.filter((_,index)=>index!==3).map(item=><div key={item.label}><dt>{item.label}</dt><dd>{item.value}</dd></div>)}</dl>
      <p>{data.balance}</p></details>
    <h3>Изменения по разделам</h3>
    {!data.groups.length && <p>Изменённых позиций нет.</p>}
    {data.groups.map(group=><details className="mobile-estimate-section" key={group.key}>
      <summary><span>{group.section || 'Без раздела'}<small>{group.workPackage} · {group.rows.length} позиций</small></span>
        <strong>{group.difference>0?'+':''}{group.difference.toLocaleString('ru-RU',{maximumFractionDigits:2})} ₽</strong></summary>
      {group.rows.map((row,index)=><details className="mobile-estimate-position" key={index}>
        <summary><span>{row.name}</span><strong>{row.difference}</strong></summary>
        <p>{row.reason}</p><dl>
          <div><dt>Объём: было → стало</dt><dd>{row.beforeQty} → {row.afterQty}</dd></div>
          {row.beforePrice && row.afterPrice && <div><dt>Цена за единицу: было → стало</dt><dd>{row.beforePrice} → {row.afterPrice}</dd></div>}
          <div><dt>Сумма: было → стало</dt><dd>{row.beforeSum} → {row.afterSum}</dd></div>
        </dl>
      </details>)}
    </details>)}
  </div>;
}
