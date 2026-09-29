import React from 'react';
import { allocateWorkMaterialSources } from '../work-material-accounting/materialSources';

export default function AdditionalMaterials({ data, value, onChange, materialAvailabilityMapForWork }) {
  const available = Object.values(materialAvailabilityMapForWork?.(data.project, data.workPackage) || {});
  const selected = new Set(value.map(item => item.name));
  const options = available.filter(item => !selected.has(item.name));
  const change = (index, fields) => onChange(value.map((item, i) => i === index ? { ...item, ...fields } : item));
  return <section>
    <h4>Дополнительный расход</h4>
    <p>Укажите только материал, фактически израсходованный при доработке. Прежний расход уже сохранён.</p>
    {!value.length && <p>Дополнительный расход не указан.</p>}
    <label>Добавить материал<select value="" onChange={event => {
      const stock = options[Number(event.target.value)];
      if (stock) onChange([...value, { name: stock.name, unit: stock.unit, workPackage: data.workPackage,
        quantity: '', sourcePreference: 'auto' }]);
    }}><option value="">Выберите из доступных остатков</option>
      {options.map((item, i) => <option key={item.name} value={i}>{item.name} · {item.quantity} {item.unit}</option>)}
    </select></label>
    {!available.length && <p>Доступных остатков нет. Если материал использован, сначала оформите его поступление или выдачу.</p>}
    {value.map((item, i) => {
      const stock = available.find(row => row.name === item.name);
      const sources = allocateWorkMaterialSources(item, stock);
      return <article key={item.name}>
        <b>{item.name}</b>
        <div className="ledger-grid">
          <label>Расход ({item.unit})<input type="number" min="0.000001" step="0.000001" value={item.quantity} onChange={event => change(i, { quantity: event.target.value })} /></label>
          <label>Источник<select value={item.sourcePreference} onChange={event => change(i, { sourcePreference: event.target.value })}>
            <option value="auto">Сначала у мастера, затем склад</option><option value="personal">Остаток мастера</option><option value="warehouse">Склад объекта</option>
          </select></label>
        </div>
        <p>С остатка мастера: {sources.personalQuantity} {item.unit}. Со склада: {sources.warehouseQuantity} {item.unit}.</p>
        <button type="button" onClick={() => onChange(value.filter((_, index) => index !== i))}>Убрать {item.name}</button>
      </article>;
    })}
  </section>;
}
