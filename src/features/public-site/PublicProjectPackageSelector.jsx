import React from 'react';
import { Check } from 'lucide-react';

export const PublicProjectPackageSelector = ({ packages, selectedValue, onSelect }) => (
  <section className="public-project-packages" aria-labelledby="public-project-packages-title">
    <div className="public-project-packages-head">
      <div>
        <span id="public-project-packages-title">Выберите комплектацию</span>
        <small>Ориентир пересчитается для текущего проекта</small>
      </div>
    </div>
    <div className="public-project-package-list" role="radiogroup" aria-label="Комплектация дома">
      {packages.map((item) => {
        const selected = item.value === selectedValue;
        return (
          <button
            className={selected ? 'public-project-package active' : 'public-project-package'}
            type="button"
            role="radio"
            aria-checked={selected}
            key={item.value}
            onClick={() => onSelect(item)}
          >
            <span className="public-project-package-main">
              <b>{item.label}</b>
              <strong>{item.estimateFrom}</strong>
              <small>{item.duration}</small>
              <em>{item.description}</em>
            </span>
            <span className="public-project-package-includes">
              {item.includes.map((includedItem) => (
                <small key={includedItem}><Check size={14} />{includedItem}</small>
              ))}
            </span>
          </button>
        );
      })}
    </div>
    <p>Фундамент, внешние сети и особенности участка уточняются отдельно и учитываются калькулятором.</p>
  </section>
);
