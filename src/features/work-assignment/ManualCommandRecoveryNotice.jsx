import React from 'react';

export default function ManualCommandRecoveryNotice({pending,busy,onResume}) {
  if(!pending) return null;
  const payload=JSON.parse(pending.body);
  const name=payload.assignee?.brigadeName || payload.brigadeName;
  return <section aria-label="Сохранённая отправка бригады">
    <p>{pending.receipt ? 'Отправка сохранена. Осталось обновить список.' : 'Результат предыдущей отправки пока не подтверждён.'}</p>
    <p>Бригада: {name}{Array.isArray(payload.items)?` · работ: ${payload.items.length}`:''}.</p>
    {Array.isArray(payload.items) && <details><summary>Сохранённые работы и цены</summary><ul>
      {payload.items.map((item,index)=><li key={index}>{item.name} · {item.expectedSource?.quantity} {item.unit}
        {' · цена: '}{Number(item.manualPrice ?? ((item.expectedSource?.priceSmeta || 0)*(item.coefficient ?? payload.coefficient))).toLocaleString('ru-RU')} ₽</li>)}
    </ul></details>}
    <p>Будут использованы сохранённые данные. Новая отправка доступна после завершения этой.</p>
    <button type="button" disabled={busy} onClick={onResume}>{busy?'Проверяем…':pending.receipt?'Обновить список':'Повторить сохранённую отправку'}</button>
  </section>;
}
