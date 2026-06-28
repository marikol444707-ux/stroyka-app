import React from 'react';
import { SOURCE_COLUMNS, getSourceCell, getStageStatusTone } from './directorMapRules';

export default function DirectorMapLinksTable({ items }) {
  return (
    <section className="dm-section dm-links-table">
      <div className="dm-section-head">
        <div>
          <h2>Цепочка связей</h2>
          <p>Модуль показывает будущие связи, но в песочнице ничего не проводит.</p>
        </div>
      </div>
      <div className="dm-table-wrap">
        <table>
          <thead>
            <tr>
              <th>Этап</th>
              {SOURCE_COLUMNS.map(column => <th key={column.id}>{column.label}</th>)}
              <th>Решение</th>
            </tr>
          </thead>
          <tbody>
            {items.map(item => (
              <tr key={item.id}>
                <td data-label="Этап">
                  <b>{item.title}</b>
                  <span className={`dm-pill dm-tone-${getStageStatusTone(item)}`}>{item.status}</span>
                </td>
                {SOURCE_COLUMNS.map(column => {
                  const cell = getSourceCell(item.sourceRefs[column.id], item);
                  return (
                    <td key={column.id} data-label={column.label}>
                      <span className={`dm-pill dm-tone-${cell.tone}`}>{cell.text}</span>
                    </td>
                  );
                })}
                <td data-label="Решение">
                  {item.signals[0]?.nextAction?.label || (item.reviewState === 'needs_review' ? 'Проверить связь' : 'Наблюдать')}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
