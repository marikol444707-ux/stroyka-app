import React from 'react';
import { Check, GitCompare, X } from 'lucide-react';

export const PublicProjectComparisonPanel = ({ items, selectedCode, onSelect, onRemove }) => (
  <section className="public-project-comparison" aria-label="Сравнение проектов">
    <div className="public-project-comparison-head">
      <span><GitCompare size={17} /></span>
      <div>
        <h4>Сравнение проектов</h4>
        <p>{items.length < 2 ? 'Добавьте ещё один проект этого направления.' : 'Сравните основные параметры и выберите вариант для расчёта.'}</p>
      </div>
      <strong>{items.length} из 3</strong>
    </div>
    <div className="public-project-comparison-grid" style={{ '--comparison-count': items.length }}>
      {items.map((item) => (
        <article className={selectedCode === item.code ? 'selected' : ''} key={item.code}>
          <div className="public-project-comparison-title">
            <span>{item.code}</span>
            <button type="button" onClick={() => onRemove(item.code)} aria-label={`Убрать ${item.code} из сравнения`}>
              <X size={16} />
            </button>
          </div>
          <h5>{item.title}</h5>
          <dl>
            {item.facts.map(([label, value]) => (
              <div key={label}>
                <dt>{label}</dt>
                <dd>{value}</dd>
              </div>
            ))}
          </dl>
          <button className="public-project-comparison-select" type="button" onClick={() => onSelect(item.code)} aria-label={`Выбрать ${item.code} для расчёта`}>
            {selectedCode === item.code && <Check size={15} />}
            {selectedCode === item.code ? 'Выбран для расчёта' : 'Выбрать для расчёта'}
          </button>
        </article>
      ))}
    </div>
  </section>
);
