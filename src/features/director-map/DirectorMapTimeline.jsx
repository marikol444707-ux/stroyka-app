import React from 'react';
import { CalendarDays } from 'lucide-react';
import { filterDirectorMapItems, getItemTone, getStageStatusTone } from './directorMapRules';

export default function DirectorMapTimeline({
  items,
  activeFilter,
  selectedId,
  onSelect,
}) {
  const visibleItems = filterDirectorMapItems(items, activeFilter);

  return (
    <section className="dm-section dm-timeline-section">
      <div className="dm-section-head">
        <div>
          <h2>График работ с сигналами</h2>
          <p>Красная строка означает приоритет просмотра, а не запрет работы.</p>
        </div>
        <div className="dm-legend" aria-label="Легенда">
          <span><i className="dm-dot dm-tone-success" />норма</span>
          <span><i className="dm-dot dm-tone-warning" />риск</span>
          <span><i className="dm-dot dm-tone-danger" />критично</span>
        </div>
      </div>

      <div className="dm-timeline-list">
        {visibleItems.map(item => {
          const itemTone = getItemTone(item);
          const statusTone = getStageStatusTone(item);
          const isSelected = item.id === selectedId;
          return (
            <button
              key={item.id}
              type="button"
              className={`dm-work-row ${isSelected ? 'is-selected' : ''}`}
              onClick={() => onSelect(item.id)}
            >
              <span className="dm-work-title">
                <strong>{item.title}</strong>
                <span>{item.workPackage} · {item.zone} · {item.responsible}</span>
              </span>
              <span className="dm-bar-wrap" aria-label="Срок и прогресс">
                <span className="dm-today-line" style={{ left: '52%' }} />
                <span
                  className={`dm-bar-window dm-tone-${itemTone}`}
                  style={{
                    left: `${item.timeline.startPercent}%`,
                    width: `${item.timeline.widthPercent}%`,
                  }}
                >
                  {item.factProgress}%
                </span>
              </span>
              <span className="dm-row-status">
                <span className={`dm-pill dm-tone-${statusTone}`}>{item.status}</span>
                <small>
                  <CalendarDays size={12} aria-hidden="true" />
                  {item.signals.length ? `${item.signals.length} сигнала` : 'без критики'}
                </small>
              </span>
            </button>
          );
        })}
        {!visibleItems.length && (
          <div className="dm-empty-state">
            <strong>Нет строк по выбранному фильтру</strong>
            <span>По текущему объекту нет строк с таким сигналом.</span>
          </div>
        )}
      </div>
    </section>
  );
}
